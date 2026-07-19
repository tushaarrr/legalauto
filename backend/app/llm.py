"""The ONLY module that talks to the LLM provider.

Everything provider-specific (the SDK client, model id, structured-output
config, retry logic) is quarantined here so the rest of the app depends on plain
Python objects. Swapping providers means rewriting this file and nothing else —
this OpenAI implementation replaced an Anthropic one with zero changes to
schema.py, prompts.py, or main.py.

Flow for one intake:
    extract_fields()  -> strict JSON, parsed + validated, one stricter retry
    draft_reply()     -> logistics-only confirmation email
    process_intake()  -> orchestrates both and reconciles missing_fields
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Load backend/.env regardless of the process's working directory so the API key
# and optional LLM_MODEL are available whether launched via uvicorn or a script.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from .prompts import (
    DRAFT_SYSTEM_PROMPT,
    EXTRACTION_RETRY_SUFFIX,
    EXTRACTION_SYSTEM_PROMPT,
    build_draft_user_prompt,
)
from .schema import (
    EXTRACTION_JSON_SCHEMA,
    NULLABLE_FIELDS,
    ExtractedRecord,
)

# Default to a cheap, widely-available model that supports strict Structured
# Outputs. Override via env — e.g. LLM_MODEL=gpt-4o for higher classification
# accuracy on the Phase 4 sweep.
MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")

# Lazily-constructed module-level client. The zero-arg constructor resolves
# OPENAI_API_KEY from the environment.
_client: OpenAI | None = None


class LLMError(RuntimeError):
    """Raised when the model refuses/truncates, or when extraction can't be
    parsed even after the one allowed stricter retry. Surfaced as a 502."""


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def _parse_and_validate(raw: str) -> ExtractedRecord:
    """Parse model output into a validated ExtractedRecord.

    Tolerates a stray ```json fence just in case a future model/config emits one,
    then validates against the Pydantic model (enums, types). Any failure raises
    and triggers the single stricter retry in extract_fields().
    """
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.lstrip().lower().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
        cleaned = cleaned.strip().rstrip("`").strip()
    data = json.loads(cleaned)  # raises json.JSONDecodeError on bad JSON
    return ExtractedRecord.model_validate(data)  # raises on schema mismatch


def _extract_once(text: str, system_prompt: str) -> ExtractedRecord:
    response = _get_client().chat.completions.create(
        model=MODEL,
        max_completion_tokens=2000,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        # Structured Outputs (strict): the strongest lever for requirement #1.
        # `strict: True` constrains the model to the exact JSON schema, so parse
        # failures are rare — but we still validate + retry below in case this is
        # swapped for a model/config without it.
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "intake_extraction",
                "strict": True,
                "schema": EXTRACTION_JSON_SCHEMA,
            },
        },
    )
    choice = response.choices[0]
    if getattr(choice.message, "refusal", None):
        raise LLMError(f"The model declined this intake: {choice.message.refusal}")
    if choice.finish_reason == "length":
        raise LLMError("Extraction was truncated before completing (hit token cap).")
    return _parse_and_validate(choice.message.content or "")


def extract_fields(text: str) -> ExtractedRecord:
    """Extract structured fields, retrying ONCE with a stricter instruction.

    Requirement #1: parse on failure, retry once stricter, then surface an error.
    """
    try:
        return _extract_once(text, EXTRACTION_SYSTEM_PROMPT)
    except (json.JSONDecodeError, ValueError):
        # One stricter retry before giving up.
        try:
            return _extract_once(
                text, EXTRACTION_SYSTEM_PROMPT + EXTRACTION_RETRY_SUFFIX
            )
        except (json.JSONDecodeError, ValueError) as exc:
            raise LLMError(
                f"Could not parse a valid structured record after a retry: {exc}"
            ) from exc


def _reconcile_missing_fields(record: ExtractedRecord) -> ExtractedRecord:
    """Guarantee every null identity field is flagged as missing.

    Enforces requirement #2 server-side, independent of the model: if a contact
    field came back null, its name MUST appear in missing_fields so the human
    reviewer sees the gap. Additive only — we never drop what the model flagged.
    """
    missing = list(record.missing_fields)
    for field in NULLABLE_FIELDS:
        if getattr(record, field) is None and field not in missing:
            missing.append(field)
    record.missing_fields = missing
    return record


def draft_reply(record: ExtractedRecord) -> str:
    """Draft the logistics-only confirmation reply under the no-advice guardrail."""
    response = _get_client().chat.completions.create(
        model=MODEL,
        max_completion_tokens=800,
        messages=[
            {"role": "system", "content": DRAFT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_draft_user_prompt(record.model_dump()),
            },
        ],
    )
    choice = response.choices[0]
    if getattr(choice.message, "refusal", None):
        raise LLMError(
            f"The model declined to draft a reply: {choice.message.refusal}"
        )
    return (choice.message.content or "").strip()


def process_intake(text: str) -> tuple[ExtractedRecord, str]:
    """Run the full extract -> reconcile -> draft pipeline for one intake."""
    record = _reconcile_missing_fields(extract_fields(text))
    reply = draft_reply(record)
    return record, reply
