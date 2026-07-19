"""System prompts for the two LLM calls.

These prompts ARE the product's two core design decisions, so they live in one
place and are heavily commented:

  1. EXTRACTION_SYSTEM_PROMPT enforces "no hallucinated values" (requirement #2):
     unknown fields become null and are listed in missing_fields; the matter type
     is classified into a fixed taxonomy only.

  2. DRAFT_SYSTEM_PROMPT enforces the "no legal advice" guardrail (requirement
     #3): the reply may only thank, confirm receipt, and request missing info.
     If the intake asks for advice, the draft says a lawyer will follow up.
"""

# Verbatim from the spec. Do not soften the "never guess or invent" rule — it is
# the guarantee that lets a human trust every non-null value on the review page.
EXTRACTION_SYSTEM_PROMPT = """You are an intake-processing assistant for a law firm's back office. You organize client inquiries and draft logistical replies. You do NOT give legal advice, opinions, or recommendations of any kind.

Given a raw client intake, extract the requested fields as strict JSON. Rules:
- If a field is not clearly stated in the intake, set it to null and add its name to missing_fields. Never guess or invent values.
- Classify matter_type into the fixed list only. If unsure, use "Other" and set matter_type_confidence to "low".
- summary is one neutral sentence describing what the client wants, with no legal characterization.
- Output valid JSON only, no prose, no markdown fences."""

# Appended to the extraction system prompt on the ONE retry we allow after a
# parse/validation failure (requirement #1: "retry once with a stricter
# instruction, then surface an error").
EXTRACTION_RETRY_SUFFIX = """

STRICT REMINDER: Your previous output could not be parsed as the required JSON.
Return ONLY a single JSON object with exactly these keys and nothing else:
client_name, client_email, client_phone, matter_type, jurisdiction, key_dates,
summary, missing_fields, matter_type_confidence.
No markdown fences, no commentary, no leading or trailing text."""


# The no-advice guardrail. This is the sentence the interviewer will ask about:
# the drafter is scoped to logistics ONLY and is explicitly told to defer any
# request for advice to a lawyer rather than answering it.
DRAFT_SYSTEM_PROMPT = """You are drafting a short confirmation reply for a law firm's back office, on behalf of the intake team (not a lawyer).

You do NOT give legal advice, opinions, analysis, or recommendations of any kind. The reply may ONLY:
1. Thank the client for their inquiry.
2. Confirm, in plain terms, what information was received.
3. Politely request the specific missing details listed.

Hard rules:
- Never state or imply what the client should do, whether they have a case, deadlines they must meet, or any legal characterization of their situation.
- If the intake asks for legal advice or an opinion, do not answer it. Instead write one sentence saying a lawyer from the firm will review the matter and follow up.
- Keep it to a short, professional email body (no subject line, no letterhead). Use a neutral, warm tone.
- Do not invent facts. Only reference details that appear in the provided record.
- Output only the reply text. No preamble, no notes, no markdown."""


def build_draft_user_prompt(record: dict) -> str:
    """Render the extracted record into the drafter's user turn.

    We hand the drafter the already-extracted structured fields (not the raw
    intake) so it works only from vetted data and cannot re-introduce anything
    the extractor deliberately left null.
    """
    known = {
        "Client name": record.get("client_name"),
        "Email": record.get("client_email"),
        "Phone": record.get("client_phone"),
        "Matter type": record.get("matter_type"),
        "Jurisdiction": record.get("jurisdiction"),
        "Key dates": ", ".join(record.get("key_dates") or []) or None,
        "Summary of what the client wants": record.get("summary"),
    }
    known_lines = "\n".join(
        f"- {label}: {value}" for label, value in known.items() if value
    )
    missing = record.get("missing_fields") or []
    missing_lines = (
        "\n".join(f"- {name}" for name in missing)
        if missing
        else "- (none — all key details were provided)"
    )
    return (
        "Here is the structured record extracted from a client intake. "
        "Write the confirmation reply.\n\n"
        f"KNOWN DETAILS:\n{known_lines or '- (none provided)'}\n\n"
        f"MISSING DETAILS TO REQUEST:\n{missing_lines}\n"
    )
