"""Phase 4 accuracy sweep.

Runs the extraction+draft pipeline over the hand-labeled synthetic intakes in
samples/intakes.json and scores the output against the labels, so the numbers on
the resume are MEASURED, not guessed (PRD sections 8 and 10).

It reports, in aggregate and per sample:
  * matter-type classification accuracy vs. the hand labels
  * field-extraction accuracy for each identity field (name/email/phone/
    jurisdiction), where "correct" means the right value OR a correct null
  * % of intakes where the missing identity fields were flagged exactly right
  * how many classification errors the model self-flagged as low confidence —
    i.e. how many were surfaced to the human reviewer instead of failing
    silently, which is the whole point of the confidence flag
  * average/median pipeline latency (the automated portion of "time to approved")

Usage (from backend/, venv active, OPENAI_API_KEY set):
    python -m scripts.eval_samples
    python -m scripts.eval_samples --limit 5          # quick, cheap subset
    python -m scripts.eval_samples --samples path.json --out eval_results/

NOTE: this makes ~2 real LLM calls per sample and therefore costs money. Nothing
here is invented — every figure comes from the model's actual output on this run.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from app.llm import LLMError, process_intake

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLES = BACKEND_ROOT / "samples" / "intakes.json"
DEFAULT_OUT_DIR = BACKEND_ROOT / "eval_results"

# The four "never guess" identity fields we score extraction + missing-flagging on.
IDENTITY_FIELDS = ["client_name", "client_email", "client_phone", "jurisdiction"]

# Distinct one-letter tags for the per-sample progress line (uppercase = correct).
FIELD_TAGS = {
    "client_name": "N",
    "client_email": "E",
    "client_phone": "P",
    "jurisdiction": "J",
}


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def field_match(field: str, gold, pred) -> bool:
    """Was this field extracted correctly against the hand label?

    A correct null counts as correct (the "don't hallucinate" guarantee). For
    present values we normalize before comparing, and match names/jurisdictions
    leniently (either contains the other) because phrasing varies; phones compare
    on digits only; emails compare exactly (case-insensitive).
    """
    if gold is None:
        return pred is None
    if pred is None:
        return False
    if field == "client_phone":
        return _digits(gold) == _digits(pred) and _digits(gold) != ""
    if field == "client_email":
        return _norm(gold) == _norm(pred)
    g, p = _norm(gold), _norm(pred)
    return g in p or p in g  # name / jurisdiction: lenient substring either way


def score_sample(sample: dict, record) -> dict:
    expected = sample["expected"]
    fields = {f: field_match(f, expected.get(f), getattr(record, f)) for f in IDENTITY_FIELDS}

    # Which identity fields SHOULD be flagged missing (the ones labeled absent),
    # and which the model actually left null (our server reconcile guarantees any
    # null identity field lands in missing_fields, so this reads them back).
    expected_missing = {f for f in IDENTITY_FIELDS if expected.get(f) is None}
    predicted_missing = {f for f in IDENTITY_FIELDS if getattr(record, f) is None}

    return {
        "id": sample["id"],
        "matter_type_expected": sample["matter_type"],
        "matter_type_predicted": record.matter_type,
        "matter_type_correct": record.matter_type == sample["matter_type"],
        "confidence": record.matter_type_confidence,
        "fields": fields,
        "missing_correct": predicted_missing == expected_missing,
        "expected_missing": sorted(expected_missing),
        "predicted_missing": sorted(predicted_missing),
    }


def _pct(n: int, d: int) -> str:
    return f"{(100.0 * n / d):.0f}%" if d else "n/a"


def run(samples: list[dict], limit: int | None) -> dict:
    if limit is not None:
        samples = samples[:limit]

    results: list[dict] = []
    errors: list[dict] = []
    latencies: list[float] = []

    for i, sample in enumerate(samples, 1):
        print(f"[{i}/{len(samples)}] {sample['id']} ... ", end="", flush=True)
        t0 = time.perf_counter()
        try:
            record, _reply = process_intake(sample["text"])
        except LLMError as exc:
            print(f"ERROR ({exc})")
            errors.append({"id": sample["id"], "error": str(exc)})
            continue
        dt = time.perf_counter() - t0
        latencies.append(dt)
        scored = score_sample(sample, record)
        scored["latency_s"] = round(dt, 2)
        results.append(scored)

        mt = "OK" if scored["matter_type_correct"] else "XX"
        field_flags = "".join(
            FIELD_TAGS[f] if scored["fields"][f] else FIELD_TAGS[f].lower()
            for f in IDENTITY_FIELDS
        )
        miss = "OK" if scored["missing_correct"] else "XX"
        print(
            f"matter[{mt}={scored['matter_type_predicted']}] "
            f"fields[{field_flags}] missing[{miss}] {dt:.1f}s"
        )

    return _aggregate(results, errors, latencies)


def _aggregate(results: list[dict], errors: list[dict], latencies: list[float]) -> dict:
    n = len(results)
    matter_correct = sum(r["matter_type_correct"] for r in results)
    missing_correct = sum(r["missing_correct"] for r in results)
    per_field = {
        f: sum(r["fields"][f] for r in results) for f in IDENTITY_FIELDS
    }
    field_total = n * len(IDENTITY_FIELDS)
    field_correct = sum(per_field.values())

    # The confidence flag only earns its place if it catches the errors. Split
    # accuracy by what the model claimed, and count how many of the misses were
    # self-flagged low (i.e. surfaced to the reviewer rather than failing quietly).
    high = [r for r in results if r["confidence"] == "high"]
    high_correct = sum(r["matter_type_correct"] for r in high)
    misses = [r for r in results if not r["matter_type_correct"]]
    misses_flagged = sum(r["confidence"] == "low" for r in misses)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_scored": n,
        "n_errors": len(errors),
        "matter_type_accuracy": {"correct": matter_correct, "total": n, "pct": _pct(matter_correct, n)},
        "field_extraction_accuracy": {
            "overall": {"correct": field_correct, "total": field_total, "pct": _pct(field_correct, field_total)},
            "per_field": {f: {"correct": per_field[f], "total": n, "pct": _pct(per_field[f], n)} for f in IDENTITY_FIELDS},
        },
        "missing_field_flagging_accuracy": {"correct": missing_correct, "total": n, "pct": _pct(missing_correct, n)},
        "confidence": {
            "high_confidence_accuracy": {
                "correct": high_correct, "total": len(high), "pct": _pct(high_correct, len(high)),
            },
            "errors_flagged_low_confidence": {
                "correct": misses_flagged, "total": len(misses), "pct": _pct(misses_flagged, len(misses)),
            },
        },
        "latency_seconds": {
            "avg": round(statistics.mean(latencies), 2) if latencies else None,
            "median": round(statistics.median(latencies), 2) if latencies else None,
            "max": round(max(latencies), 2) if latencies else None,
        },
        "results": results,
        "errors": errors,
    }
    return summary


def print_summary(summary: dict) -> None:
    print("\n" + "=" * 60)
    print("AGGREGATE  (measured this run — do not hand-edit)")
    print("=" * 60)
    mt = summary["matter_type_accuracy"]
    print(f"Matter-type classification : {mt['pct']:>5}  ({mt['correct']}/{mt['total']})")
    fe = summary["field_extraction_accuracy"]["overall"]
    print(f"Field extraction (overall) : {fe['pct']:>5}  ({fe['correct']}/{fe['total']})")
    for f, s in summary["field_extraction_accuracy"]["per_field"].items():
        print(f"    - {f:<15}      : {s['pct']:>5}  ({s['correct']}/{s['total']})")
    mf = summary["missing_field_flagging_accuracy"]
    print(f"Missing-field flagging     : {mf['pct']:>5}  ({mf['correct']}/{mf['total']})")
    hc = summary["confidence"]["high_confidence_accuracy"]
    ef = summary["confidence"]["errors_flagged_low_confidence"]
    print(f"Accuracy when 'high' conf  : {hc['pct']:>5}  ({hc['correct']}/{hc['total']})")
    print(f"Errors caught by low-conf  : {ef['pct']:>5}  ({ef['correct']}/{ef['total']} misses surfaced to reviewer)")
    lat = summary["latency_seconds"]
    if lat["avg"] is not None:
        print(f"Pipeline latency / intake  : avg {lat['avg']}s, median {lat['median']}s, max {lat['max']}s")
    if summary["n_errors"]:
        print(f"Errors                     : {summary['n_errors']} (see JSON)")


def main() -> None:
    parser = argparse.ArgumentParser(description="LegalFlow Phase 4 accuracy sweep.")
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLES, help="Path to the labeled intakes JSON.")
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N samples (cheap subset).")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help="Directory for the results JSON.")
    args = parser.parse_args()

    samples = json.loads(args.samples.read_text(encoding="utf-8"))
    print(f"Loaded {len(samples)} labeled intakes from {args.samples}\n")

    summary = run(samples, args.limit)
    print_summary(summary)

    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = args.out / f"eval_{stamp}.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    main()
