"""Measure the conflict check: recall on planted conflicts, and false positives.

Recall is the number that matters. A missed adverse match can get the firm
disqualified; a false positive just costs a lawyer ten seconds to dismiss. So we
report both, and treat them as very different kinds of error.

Test cases are generated deterministically FROM the seeded history, which means
ground truth is known exactly rather than hand-labeled:

  planted conflicts — a real past party reused as the opposing side of a new
    intake, in four disguises: verbatim, corporate-suffix swap, nickname, and a
    single-character typo. All four are the same party and must be caught.
  planted returning clients — the new client is a FORMER CLIENT. Not adverse,
    so this must NOT be reported as a conflict. Catching these as conflicts is a
    correctness bug, not a safe over-flag.
  clear cases — plausible names assembled from the same name pools. Any flag
    here is a false positive, including near-collisions like two people sharing
    a surname. We do not filter those out; that would flatter the number.

    python -m scripts.eval_conflicts
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from app.conflicts import STRONG_MATCH, _normalize, check_conflicts, load_history
from scripts.seed_matter_history import COMPANY_HEAD, COMPANY_TAIL, FIRST, LAST, SUFFIX

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SEED = 4242

# Reverse of the nickname table: formal name -> a short form to disguise it with.
FORMAL_TO_NICK = {
    "robert": "Bob", "jonathan": "Jon", "william": "Bill", "michael": "Mike",
    "elizabeth": "Liz", "david": "Dave", "james": "Jim", "thomas": "Tom",
    "christopher": "Chris", "anthony": "Tony", "richard": "Rick",
    "stephen": "Steve", "susan": "Sue", "katherine": "Kate",
    "margaret": "Maggie", "patricia": "Pat", "sandra": "Sandy",
    "barbara": "Barb", "daniel": "Dan",
}
_CORP = ("Inc.", "LLC", "Ltd.", "Corp.", "LLP")


def _is_company(name: str) -> bool:
    return any(name.endswith(s) for s in _CORP) or any(
        h in name for h in COMPANY_HEAD
    )


def disguise(name: str, mode: str, rng: random.Random) -> str | None:
    """Return the same party written differently, or None if inapplicable."""
    if mode == "verbatim":
        return name
    if mode == "suffix_swap":
        for s in _CORP:
            if name.endswith(" " + s):
                base = name[: -len(s) - 1]
                alt = rng.choice([x for x in _CORP if x != s])
                return f"{base}, {alt}"
        return None
    if mode == "nickname":
        parts = name.split()
        if len(parts) == 2 and parts[0].lower() in FORMAL_TO_NICK:
            return f"{FORMAL_TO_NICK[parts[0].lower()]} {parts[1]}"
        return None
    if mode == "typo":
        # Drop one character from the longest token — a realistic transcription slip.
        parts = name.split()
        i = max(range(len(parts)), key=lambda k: len(parts[k]))
        word = parts[i]
        if len(word) < 5:
            return None
        cut = len(word) // 2
        parts[i] = word[:cut] + word[cut + 1 :]
        return " ".join(parts)
    return None


_KNOWN_NORM: set[str] = set()


def _is_same_entity_as_history(name: str) -> bool:
    """Is this name the SAME party as one already in the history?

    Compares on the normalized form, so "Crestwell Industries Corp." and
    "Crestwell Industries Inc." count as one entity. Cases like that must be kept
    out of the not-a-conflict pool: flagging them is correct behaviour, and
    scoring it as a false positive would be measuring the test's bug, not the
    system's. Names that merely share a token (two people named Chen) are NOT
    excluded — those are exactly the false positives worth counting.
    """
    return _normalize(name) in _KNOWN_NORM


def _fresh_person(rng: random.Random) -> str:
    for _ in range(200):
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        if not _is_same_entity_as_history(name):
            return name
    raise RuntimeError("could not generate a party absent from the history")


def _fresh_company(rng: random.Random) -> str:
    for _ in range(200):
        name = f"{rng.choice(COMPANY_HEAD)} {rng.choice(COMPANY_TAIL)} {rng.choice(SUFFIX)}".strip()
        if not _is_same_entity_as_history(name):
            return name
    raise RuntimeError("could not generate a party absent from the history")


def build_cases(history: tuple[dict, ...], rng: random.Random) -> list[dict]:
    cases: list[dict] = []
    _KNOWN_NORM.clear()
    for m in history:
        _KNOWN_NORM.add(_normalize(m["client_name"]))
        _KNOWN_NORM.add(_normalize(m["opposing_party"]))
    pool = rng.sample(list(history), k=min(20, len(history)))

    for matter in pool:
        for mode in ("verbatim", "suffix_swap", "nickname", "typo"):
            # Direction 1: the new opposing party is a former client.
            alt = disguise(matter["client_name"], mode, rng)
            if alt:
                cases.append({
                    "kind": "planted_conflict", "mode": mode,
                    "client_name": _fresh_person(rng),
                    "opposing_party": alt,
                    "expect_matter": matter["matter_id"],
                })
            # Direction 2: the new client is someone the firm was adverse to.
            alt2 = disguise(matter["opposing_party"], mode, rng)
            if alt2:
                cases.append({
                    "kind": "planted_conflict", "mode": mode,
                    "client_name": alt2,
                    "opposing_party": _fresh_person(rng),
                    "expect_matter": matter["matter_id"],
                })

    # Returning clients: former client comes back. Adverse? No. Must not flag.
    # A name that ALSO appears as an opposing party somewhere is genuinely
    # adverse, so it is excluded here — flagging it would be correct, and leaving
    # it in would score a right answer as wrong.
    all_opposing = {m["opposing_party"] for m in history}
    pure_clients = [m for m in history if m["client_name"] not in all_opposing]
    for matter in rng.sample(pure_clients, k=min(15, len(pure_clients))):
        cases.append({
            "kind": "returning_client", "mode": "verbatim",
            "client_name": matter["client_name"],
            # The counterparty must be someone the firm has never touched, or the
            # case is a real conflict wearing a "returning client" label.
            "opposing_party": _fresh_person(rng),
            "expect_matter": None,
        })

    # Clear cases: plausible names drawn from the same pools as the history, so
    # surname and word collisions still occur — those stay in and count against
    # us. Only same-entity duplicates are filtered out.
    for _ in range(40):
        if rng.random() < 0.35:
            name, other = _fresh_company(rng), _fresh_person(rng)
        else:
            name, other = _fresh_person(rng), _fresh_company(rng)
        cases.append({
            "kind": "clear", "mode": "n/a",
            "client_name": name, "opposing_party": other, "expect_matter": None,
        })

    return cases


def main() -> None:
    ap = argparse.ArgumentParser(description="Conflict-check recall / false-positive sweep.")
    ap.add_argument("--out", type=Path, default=BACKEND_ROOT / "eval_results")
    args = ap.parse_args()

    history = load_history()
    rng = random.Random(SEED)
    cases = build_cases(history, rng)

    by_mode: dict[str, list[bool]] = {}
    caught = missed = 0
    strict_caught = 0
    fp = tn = 0
    returning_ok = returning_bad = 0
    failures: list[dict] = []

    for c in cases:
        res = check_conflicts(c["client_name"], c["opposing_party"])
        flagged = res.status in ("CONFLICT", "POTENTIAL")

        if c["kind"] == "planted_conflict":
            hit = flagged and any(m.matter_id == c["expect_matter"] for m in res.matches)
            by_mode.setdefault(c["mode"], []).append(hit)
            if hit:
                caught += 1
                if res.status == "CONFLICT":
                    strict_caught += 1
            else:
                missed += 1
                failures.append({**c, "got": res.status,
                                 "matched": [m.matter_id for m in res.matches[:3]]})
        elif c["kind"] == "returning_client":
            if flagged:
                returning_bad += 1
                failures.append({**c, "got": res.status, "note": "returning client flagged as conflict"})
            else:
                returning_ok += 1
        else:
            if flagged:
                fp += 1
                failures.append({**c, "got": res.status,
                                 "matched": [m.reason for m in res.matches[:1]]})
            else:
                tn += 1

    planted = caught + missed
    clear_total = fp + tn
    pct = lambda a, b: f"{100.0 * a / b:.1f}%" if b else "n/a"

    print("=" * 66)
    print("CONFLICT CHECK — measured against the seeded matter history")
    print("=" * 66)
    print(f"History size                 : {len(history)} past matters")
    print(f"Test cases                   : {len(cases)}")
    print()
    print(f"RECALL on planted conflicts  : {pct(caught, planted)}  ({caught}/{planted})   <- the number that matters")
    print(f"  ...flagged CONFLICT (not just POTENTIAL): {pct(strict_caught, planted)}  ({strict_caught}/{planted})")
    for mode, hits in sorted(by_mode.items()):
        print(f"    - {mode:<12}: {pct(sum(hits), len(hits))}  ({sum(hits)}/{len(hits)})")
    print()
    print(f"False-positive rate (clear)  : {pct(fp, clear_total)}  ({fp}/{clear_total})")
    print(f"Returning clients handled    : {pct(returning_ok, returning_ok + returning_bad)}  "
          f"({returning_ok}/{returning_ok + returning_bad} correctly NOT called a conflict)")

    if failures:
        print(f"\nFirst few failures ({len(failures)} total):")
        for f in failures[:6]:
            print(f"  [{f['kind']}/{f['mode']}] client={f['client_name']!r} "
                  f"opposing={f['opposing_party']!r} -> {f['got']}")

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "history_size": len(history),
        "n_cases": len(cases),
        "strong_match_threshold": STRONG_MATCH,
        "recall": {"caught": caught, "total": planted, "pct": pct(caught, planted)},
        "recall_strict_conflict": {"caught": strict_caught, "total": planted,
                                   "pct": pct(strict_caught, planted)},
        "recall_by_disguise": {m: {"caught": sum(h), "total": len(h), "pct": pct(sum(h), len(h))}
                               for m, h in by_mode.items()},
        "false_positive_rate": {"fp": fp, "total": clear_total, "pct": pct(fp, clear_total)},
        "returning_clients": {"correct": returning_ok, "total": returning_ok + returning_bad},
        "failures": failures,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = args.out / f"conflicts_{stamp}.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nFull results written to {path}")


if __name__ == "__main__":
    main()
