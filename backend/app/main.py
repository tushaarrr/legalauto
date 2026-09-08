"""LegalFlow API.

Two endpoints, split by the approval gate:

  * POST /process — raw intake text -> structured, human-reviewable record +
    drafted reply. Persists NOTHING. Status comes back "needs_review".
  * POST /approve — takes the (possibly human-edited) record, forces its status
    to "approved", and writes it to the CRM. This is the ONLY path that persists.

Keeping the LLM call (/process) and the CRM write (/approve) as separate steps
is the approval gate: nothing reaches storage until a human has reviewed it and
clicked Approve.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .conflicts import check_conflicts
from .llm import LLMError, process_intake
from .schema import ApproveResponse, CRMRecord, ProcessRequest, ProcessResponse
from .stats import compute_stats
from .storage import StorageError, save_record

app = FastAPI(title="LegalFlow API", version="0.1.0")

# The Next.js review page (Phase 2) calls this API from the browser. Allow any
# localhost/127.0.0.1 port so the demo still works when Next falls back from a
# busy :3000 to :3001, etc. Local origins only — this is a synthetic-data demo,
# not a production service.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/stats")
def stats() -> dict:
    """Dashboard aggregates, derived only from records a human actually approved."""
    return compute_stats()


@app.post("/process", response_model=ProcessResponse)
def process(req: ProcessRequest) -> ProcessResponse:
    """Turn raw intake text into a reviewable record + draft reply.

    The record comes back with status="needs_review". It is NOT stored anywhere;
    persistence happens only after a human approves it (Phase 3).
    """
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Intake text is required.")

    try:
        extracted, reply = process_intake(text)
    except LLMError as exc:
        # Extraction/draft failed even after the stricter retry, or the model
        # refused. Surface it rather than returning a half-baked record.
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Screen against the firm's matter history. This is deterministic and local
    # (no LLM, no network), so it runs on every intake rather than conditionally.
    conflict = check_conflicts(extracted.client_name, extracted.opposing_party)

    record = CRMRecord(
        **extracted.model_dump(),
        intake_id=f"LF-{uuid.uuid4().hex[:8]}",
        received_at=datetime.now(timezone.utc).isoformat(),
        status="needs_review",  # approval gate: nothing is "approved" yet
        draft_reply=reply,
        conflict=conflict,
    )
    return ProcessResponse(record=record)


@app.post("/approve", response_model=ApproveResponse)
def approve(record: CRMRecord) -> ApproveResponse:
    """The approval gate. Persist a human-reviewed record to the CRM.

    The client sends back the record from /process, including any edits the
    reviewer made (requirement #5). We do NOT trust the incoming status — the
    server is the authority that flips it to "approved" — then hand it to the
    isolated storage layer. No LLM is involved; this step only persists.

    The conflict verdict is re-screened here for the same reason the status is
    re-forced: the reviewer is invited to correct client_name and opposing_party,
    and the verdict that arrives was computed from the names BEFORE those edits.
    Persisting it would file a CLEAR against names that now match a former
    client. The screen is deterministic and local, so re-running it is free.
    """
    approved = record.model_copy(update={
        "status": "approved",
        "conflict": check_conflicts(record.client_name, record.opposing_party),
    })
    try:
        result = save_record(approved)
    except StorageError as exc:
        # The write failed; report it so the record stays reviewable instead of
        # being silently dropped. The UI can let the user retry Approve.
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ApproveResponse(record=approved, storage=result)
