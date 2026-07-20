"""Aggregate the approved-record log into dashboard insights.

Everything here is derived from records that actually went through the pipeline
and were approved by a human — nothing is estimated or projected. If a number
can't be computed from the log, it isn't reported.

The two metrics worth a firm's attention:

  * conflict exposure — what share of intakes hit an adverse match. This is the
    risk the manual process was missing.
  * missing-field frequency — which details clients most often leave out. That is
    directly actionable: it tells you what to add to the intake form, and every
    field fixed there is a follow-up email nobody has to send.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from .conflicts import load_history
from .storage import _LIST_SEP, _csv_path


def _split(value: str) -> list[str]:
    return [p.strip() for p in (value or "").split(_LIST_SEP.strip()) if p.strip()]


def _read_rows() -> list[dict]:
    path: Path = _csv_path()
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def compute_stats() -> dict:
    rows = _read_rows()
    total = len(rows)

    try:
        history_size = len(load_history())
    except FileNotFoundError:
        history_size = 0

    if total == 0:
        # Explicit empty state — the UI renders guidance, not a zeroed chart.
        return {
            "empty": True,
            "total_intakes": 0,
            "history_size": history_size,
            "conflict": {"CLEAR": 0, "POTENTIAL": 0, "CONFLICT": 0, "NOT_CHECKED": 0},
            "conflict_rate_pct": 0.0,
            "matter_types": [],
            "missing_fields": [],
            "confidence": {"high": 0, "low": 0},
            "incomplete_screens": 0,
            "recent": [],
        }

    conflict = Counter(r.get("conflict_status") or "NOT_CHECKED" for r in rows)
    matters = Counter(r.get("matter_type") or "Unknown" for r in rows)
    confidence = Counter(r.get("matter_type_confidence") or "unknown" for r in rows)

    missing: Counter = Counter()
    for r in rows:
        missing.update(_split(r.get("missing_fields", "")))

    # A screen that could only see one side of the matter. Counted separately
    # because a CLEAR result on an incomplete screen is not the same assurance
    # as a CLEAR on a fully-identified one.
    incomplete = sum(1 for r in rows if _split(r.get("conflict_limitations", "")))

    flagged = conflict.get("CONFLICT", 0) + conflict.get("POTENTIAL", 0)

    recent = [
        {
            "intake_id": r.get("intake_id"),
            "client_name": r.get("client_name") or "—",
            "matter_type": r.get("matter_type"),
            "conflict_status": r.get("conflict_status") or "NOT_CHECKED",
            "approved_at": r.get("approved_at"),
            "missing_count": len(_split(r.get("missing_fields", ""))),
        }
        for r in rows[::-1][:8]
    ]

    return {
        "empty": False,
        "total_intakes": total,
        "history_size": history_size,
        "conflict": {
            "CLEAR": conflict.get("CLEAR", 0),
            "POTENTIAL": conflict.get("POTENTIAL", 0),
            "CONFLICT": conflict.get("CONFLICT", 0),
            "NOT_CHECKED": conflict.get("NOT_CHECKED", 0),
        },
        "conflict_rate_pct": round(100.0 * flagged / total, 1),
        "matter_types": [{"name": k, "count": v} for k, v in matters.most_common()],
        "missing_fields": [{"field": k, "count": v} for k, v in missing.most_common(8)],
        "confidence": {
            "high": confidence.get("high", 0),
            "low": confidence.get("low", 0),
        },
        "low_confidence_pct": round(100.0 * confidence.get("low", 0) / total, 1),
        "incomplete_screens": incomplete,
        "recent": recent,
    }
