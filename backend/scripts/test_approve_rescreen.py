"""Check that /approve re-screens conflicts instead of trusting the client.

Usage (from backend/):
    python -m scripts.test_approve_rescreen

No network, no LLM, no API key — the conflict screen is deterministic and local,
and /approve is called as a plain function. Writes to a throwaway CSV.
"""

from __future__ import annotations

import os
import tempfile

os.environ["STORAGE_BACKEND"] = "csv"
os.environ["CRM_CSV_PATH"] = os.path.join(tempfile.mkdtemp(), "crm.csv")

from app.conflicts import check_conflicts, load_history  # noqa: E402
from app.main import approve  # noqa: E402
from app.schema import CRMRecord  # noqa: E402


def _adverse_pair() -> tuple[str, str]:
    """A (client, opposing) pair the history says is adverse: we opposed them."""
    for matter in load_history():
        name = matter["opposing_party"]
        if check_conflicts(name, None).status == "CONFLICT":
            return name, matter["client_name"]
    raise AssertionError("matter_history.json has no screenable opposing party")


def _record(**overrides) -> CRMRecord:
    base = dict(
        intake_id="LF-test0001", received_at="2026-01-01T00:00:00+00:00",
        status="needs_review", draft_reply="", matter_type="Other",
        matter_type_confidence="low", summary="test",
        client_name=None, opposing_party=None, conflict=None,
    )
    return CRMRecord(**{**base, **overrides})


def main() -> None:
    adverse_client, _ = _adverse_pair()

    # 1. A CLEAR verdict posted alongside names that are actually adverse — the
    #    stale-edit case — must be overruled by the server's own screen.
    stale = check_conflicts("Nobody Whatsoever", None)
    assert stale.status == "CLEAR", stale.status
    out = approve(_record(client_name=adverse_client, conflict=stale))
    assert out.record.conflict.status == "CONFLICT", out.record.conflict.status
    assert out.record.status == "approved"

    # 2. A record with no conflict block at all must still get screened, not
    #    land in the CRM as NOT_CHECKED.
    out = approve(_record(intake_id="LF-test0002", client_name=adverse_client))
    assert out.record.conflict is not None
    assert out.record.conflict.status == "CONFLICT", out.record.conflict.status

    # 3. A role is not a party: it cannot screen anything, so the one-sided
    #    limitation must survive a reviewer typing it into the field.
    out = approve(_record(intake_id="LF-test0003", client_name="Priya Menon",
                          opposing_party="my employer"))
    assert out.record.conflict.status == "CLEAR", out.record.conflict.status
    assert out.record.conflict.limitations, "role-shaped party suppressed the limitation"

    print("ok — /approve re-screens; client-supplied verdicts are not trusted")


if __name__ == "__main__":
    main()
