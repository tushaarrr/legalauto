"""Data model for LegalFlow.

The extracted record is the single source of truth that flows:
    LLM extraction -> human review/edit -> (on approval) CRM storage.

Two representations live here on purpose:
  * EXTRACTION_JSON_SCHEMA  -> handed to the LLM provider (currently OpenAI, see
                               llm.py) as a strict output contract (structured
                               outputs). The model is constrained to emit exactly
                               these fields/types.
  * ExtractedRecord (Pydantic) -> validated server-side after parsing. This is
                               the belt-and-suspenders check behind requirement
                               #1 (strict structured output): even if the model
                               call is later swapped for one WITHOUT structured
                               outputs, we still parse + validate + retry.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# Fixed matter-type taxonomy. The model may ONLY classify into this list;
# anything ambiguous must land in "Other" with low confidence (requirement #2:
# no invented categories).
MATTER_TYPES = [
    "Family",
    "Real Estate",
    "Employment",
    "Wills & Estates",
    "Civil Litigation",
    "Other",
]

# Contact/identity fields that must never be guessed. If absent from the intake
# they are null AND their name is reconciled into missing_fields server-side.
NULLABLE_FIELDS = ["client_name", "client_email", "client_phone", "jurisdiction"]


# --- Strict output contract handed to the LLM provider ------------------------
# Structured outputs require every property listed in `required` and
# `additionalProperties: false`. Nullable fields use the ["string", "null"] type
# union so the model can (and must) return null rather than hallucinating.
EXTRACTION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "client_name": {"type": ["string", "null"]},
        "client_email": {"type": ["string", "null"]},
        "client_phone": {"type": ["string", "null"]},
        "matter_type": {"type": "string", "enum": MATTER_TYPES},
        "jurisdiction": {"type": ["string", "null"]},
        "key_dates": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
        "missing_fields": {"type": "array", "items": {"type": "string"}},
        "matter_type_confidence": {"type": "string", "enum": ["high", "low"]},
    },
    "required": [
        "client_name",
        "client_email",
        "client_phone",
        "matter_type",
        "jurisdiction",
        "key_dates",
        "summary",
        "missing_fields",
        "matter_type_confidence",
    ],
    "additionalProperties": False,
}


class ExtractedRecord(BaseModel):
    """The structured fields the LLM pulls out of a raw intake."""

    client_name: Optional[str] = None
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    matter_type: Literal[
        "Family",
        "Real Estate",
        "Employment",
        "Wills & Estates",
        "Civil Litigation",
        "Other",
    ]
    jurisdiction: Optional[str] = None
    key_dates: List[str] = Field(default_factory=list)
    summary: str
    missing_fields: List[str] = Field(default_factory=list)
    matter_type_confidence: Literal["high", "low"]


class CRMRecord(ExtractedRecord):
    """Full record as it will be reviewed and (later) written to the CRM.

    Adds workflow/generated fields on top of the extracted ones. `status` starts
    at "needs_review" and only becomes "approved" after the human clicks Approve
    (requirement #4, the approval gate).
    """

    intake_id: str
    received_at: str
    status: Literal["needs_review", "approved"] = "needs_review"
    draft_reply: str


class ProcessRequest(BaseModel):
    text: str


class ProcessResponse(BaseModel):
    record: CRMRecord


class SaveResult(BaseModel):
    """Outcome of persisting an approved record to the CRM (see storage.py).

    Returned to the UI so it can show where the record landed. `already_saved`
    is True when an idempotent re-approve found the row already present.
    """

    backend: Literal["csv", "airtable"]
    location: str  # CSV file path, or "<base>/<table>" for Airtable
    record_id: str  # the record's intake_id
    approved_at: str
    external_ref: Optional[str] = None  # Airtable record id, when applicable
    already_saved: bool = False


class ApproveResponse(BaseModel):
    record: CRMRecord
    storage: SaveResult
