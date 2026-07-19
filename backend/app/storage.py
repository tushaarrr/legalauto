"""The ONLY module that writes approved records to the "CRM".

Storage is isolated here (mirroring llm.py's provider isolation) so the CRM can
be swapped without touching the endpoint, schema, or UI. Two backends ship:

  * csv      — a local spreadsheet file. Zero config, always works, so the demo
               runs end-to-end out of the box. This is the Google-Sheets-style
               "stand-in CRM" the PRD allows.
  * airtable — the preferred CRM. Activates automatically when AIRTABLE_API_KEY,
               AIRTABLE_BASE_ID and AIRTABLE_TABLE_NAME are all set.

Selection is controlled by STORAGE_BACKEND ("auto" | "csv" | "airtable"):
  auto (default) -> airtable if its env vars are present, otherwise csv.

Nothing here is called until a human approves a record (the approval gate lives
in main.py's /approve endpoint). This module never talks to the LLM and never
decides *whether* to save — it only performs the write.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path

from .schema import CRMRecord, SaveResult

# backend/ root, so paths resolve no matter the process's working directory.
BACKEND_ROOT = Path(__file__).resolve().parents[1]

# Fixed column order for the CSV CRM. Lists are flattened with " | " so the file
# stays a plain, human-openable spreadsheet.
_CSV_COLUMNS = [
    "intake_id",
    "received_at",
    "approved_at",
    "status",
    "client_name",
    "client_email",
    "client_phone",
    "matter_type",
    "matter_type_confidence",
    "jurisdiction",
    "key_dates",
    "summary",
    "missing_fields",
    "draft_reply",
]

_LIST_SEP = " | "


class StorageError(RuntimeError):
    """Raised when the CRM write fails. Surfaced by /approve as a 502 so the
    record stays reviewable rather than silently lost."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _selected_backend() -> str:
    """Resolve which backend to use from env, honoring an explicit override."""
    choice = os.environ.get("STORAGE_BACKEND", "auto").strip().lower()
    if choice in ("csv", "airtable"):
        return choice
    # auto: prefer Airtable when it is fully configured, else the local CSV.
    if _airtable_config() is not None:
        return "airtable"
    return "csv"


# --- CSV backend -------------------------------------------------------------


def _csv_path() -> Path:
    raw = os.environ.get("CRM_CSV_PATH")
    path = Path(raw) if raw else BACKEND_ROOT / "data" / "crm.csv"
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    return path


def _csv_row(record: CRMRecord, approved_at: str) -> dict:
    data = record.model_dump()
    data["approved_at"] = approved_at
    data["key_dates"] = _LIST_SEP.join(record.key_dates)
    data["missing_fields"] = _LIST_SEP.join(record.missing_fields)
    return {col: data.get(col, "") for col in _CSV_COLUMNS}


def _existing_intake_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as fh:
        return {row.get("intake_id", "") for row in csv.DictReader(fh)}


def _save_csv(record: CRMRecord, approved_at: str) -> SaveResult:
    path = _csv_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Idempotent: approving the same intake twice must not duplicate the row.
        if record.intake_id in _existing_intake_ids(path):
            return SaveResult(
                backend="csv",
                location=str(path),
                record_id=record.intake_id,
                approved_at=approved_at,
                already_saved=True,
            )
        write_header = not path.exists() or path.stat().st_size == 0
        with path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=_CSV_COLUMNS)
            if write_header:
                writer.writeheader()
            writer.writerow(_csv_row(record, approved_at))
    except OSError as exc:
        raise StorageError(f"Could not write to the CSV CRM at {path}: {exc}") from exc
    return SaveResult(
        backend="csv",
        location=str(path),
        record_id=record.intake_id,
        approved_at=approved_at,
    )


# --- Airtable backend --------------------------------------------------------


def _airtable_config() -> dict | None:
    """Return Airtable creds if fully configured, else None."""
    key = os.environ.get("AIRTABLE_API_KEY")
    base = os.environ.get("AIRTABLE_BASE_ID")
    table = os.environ.get("AIRTABLE_TABLE_NAME")
    if key and base and table:
        return {"key": key, "base": base, "table": table}
    return None


def _save_airtable(record: CRMRecord, approved_at: str) -> SaveResult:
    cfg = _airtable_config()
    if cfg is None:
        raise StorageError(
            "STORAGE_BACKEND=airtable but AIRTABLE_API_KEY / AIRTABLE_BASE_ID / "
            "AIRTABLE_TABLE_NAME are not all set."
        )
    # httpx ships with the openai SDK; import lazily so the CSV path never needs it.
    import httpx

    url = f"https://api.airtable.com/v0/{cfg['base']}/{cfg['table']}"
    fields = {
        "intake_id": record.intake_id,
        "received_at": record.received_at,
        "approved_at": approved_at,
        "status": record.status,
        "client_name": record.client_name,
        "client_email": record.client_email,
        "client_phone": record.client_phone,
        "matter_type": record.matter_type,
        "matter_type_confidence": record.matter_type_confidence,
        "jurisdiction": record.jurisdiction,
        "key_dates": _LIST_SEP.join(record.key_dates),
        "summary": record.summary,
        "missing_fields": _LIST_SEP.join(record.missing_fields),
        "draft_reply": record.draft_reply,
    }
    try:
        resp = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {cfg['key']}",
                "Content-Type": "application/json",
            },
            # typecast lets Airtable coerce values into existing column types.
            json={"fields": fields, "typecast": True},
            timeout=20.0,
        )
        resp.raise_for_status()
        external_ref = resp.json().get("id")
    except httpx.HTTPStatusError as exc:
        raise StorageError(
            f"Airtable rejected the write ({exc.response.status_code}): "
            f"{exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise StorageError(f"Could not reach Airtable: {exc}") from exc
    return SaveResult(
        backend="airtable",
        location=f"{cfg['base']}/{cfg['table']}",
        record_id=record.intake_id,
        external_ref=external_ref,
        approved_at=approved_at,
    )


def save_record(record: CRMRecord) -> SaveResult:
    """Persist an approved record to the selected CRM backend.

    The caller (the /approve endpoint) is responsible for having set status to
    "approved" first — this function just stamps approved_at and writes.
    """
    approved_at = _now_iso()
    backend = _selected_backend()
    if backend == "airtable":
        return _save_airtable(record, approved_at)
    return _save_csv(record, approved_at)
