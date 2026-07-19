"""Phase 1 smoke test — run the pipeline on a few pasted intakes, print raw JSON.

Usage (from backend/, with the venv active and OPENAI_API_KEY set):
    python -m scripts.test_process

This deliberately calls the pipeline directly (no HTTP server needed) so you can
eyeball the structured output before any UI exists.
"""

from __future__ import annotations

import json

from app.llm import process_intake

# Three hand-picked intakes that stress the guarantees:
#  1. Complete-ish family matter (should be high confidence, few missing).
#  2. Sparse inquiry (most fields null -> flagged in missing_fields).
#  3. Explicitly asks for legal advice (draft must defer to a lawyer, not answer).
SAMPLES = [
    (
        "complete_family",
        """Hi, my name is Priya Menon, you can reach me at priya.menon@example.com
or (415) 555-0198. My husband and I are separating and we need help with the
divorce and custody of our two kids. We're in San Francisco, California. Our
mediation date is set for March 3, 2026. What are the next steps?""",
    ),
    (
        "sparse_inquiry",
        """Hello, I got hurt at work last month and my employer is giving me a hard
time. Can someone call me back?""",
    ),
    (
        "asks_for_advice",
        """This is David. My landlord in Austin, TX is trying to evict me and I
signed the lease on 01/15/2024. Do I have a case? Should I stop paying rent
until this is resolved? Please advise. My number is 512-555-7742.""",
    ),
]


def main() -> None:
    for name, text in SAMPLES:
        print("=" * 72)
        print(f"SAMPLE: {name}")
        print("-" * 72)
        record, reply = process_intake(text)
        print(json.dumps(record.model_dump(), indent=2))
        print("\nDRAFT REPLY:\n")
        print(reply)
        print()


if __name__ == "__main__":
    main()
