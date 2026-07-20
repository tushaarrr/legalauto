"""Populate the CRM by running the labeled sample intakes through the real API.

This is not fabricated data: each record is produced by the actual
/process -> /approve path, including a real LLM extraction and a real conflict
screen. It exists so the dashboard has something honest to show in a demo.

Requires the backend to be running.

    python -m scripts.seed_demo_intakes --api http://127.0.0.1:8010
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SAMPLES = BACKEND_ROOT / "samples" / "intakes.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8010")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    samples = json.loads(SAMPLES.read_text(encoding="utf-8"))
    if args.limit:
        samples = samples[: args.limit]

    ok = failed = 0
    with httpx.Client(timeout=120) as client:
        for i, s in enumerate(samples, 1):
            try:
                r = client.post(f"{args.api}/process", json={"text": s["text"]})
                r.raise_for_status()
                record = r.json()["record"]

                a = client.post(f"{args.api}/approve", json=record)
                a.raise_for_status()
                storage = a.json()["storage"]

                c = record.get("conflict") or {}
                print(f"[{i}/{len(samples)}] {s['id']:<38} "
                      f"{record['matter_type']:<17} conflict={c.get('status','?'):<9} "
                      f"{'(already saved)' if storage.get('already_saved') else 'saved'}")
                ok += 1
            except Exception as exc:
                print(f"[{i}/{len(samples)}] {s['id']:<38} FAILED: {type(exc).__name__}: {exc}")
                failed += 1

    print(f"\nseeded {ok} record(s), {failed} failure(s)")


if __name__ == "__main__":
    main()
