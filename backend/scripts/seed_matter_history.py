"""Generate the synthetic "firm matter history" the conflict check runs against.

Deterministic (fixed seed), so the file it writes is reproducible and the
conflict-recall numbers are re-derivable by anyone who clones the repo.

    python -m scripts.seed_matter_history

Writes samples/matter_history.json. Every name here is fabricated; any resemblance
to a real firm, client, or matter is coincidental.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
OUT = BACKEND_ROOT / "samples" / "matter_history.json"

SEED = 20260719
N_MATTERS = 100

FIRST = [
    "Robert", "Jonathan", "Katherine", "William", "Michael", "Elizabeth", "David",
    "James", "Thomas", "Christopher", "Anthony", "Richard", "Stephen", "Susan",
    "Margaret", "Patricia", "Linda", "Barbara", "Sandra", "Priya", "Sofia",
    "Grace", "Tomas", "Henry", "Rachel", "Victor", "Ana", "Brandon", "Marcus",
    "Ellen", "Aaron", "Daniel", "Beatrice", "Karen", "Nadia", "Omar", "Wei",
    "Yusuf", "Ingrid", "Mateo",
]
LAST = [
    "Chen", "Meyers", "Okonkwo", "Alvarez", "Nwosu", "Sokolova", "Pruitt", "Feld",
    "Hall", "Blythe", "Osei", "Stein", "Reyes", "Menon", "Lin", "Cole", "Vance",
    "Brennan", "Kowalski", "Ferreira", "Nakamura", "Haddad", "Bergstrom", "Ivanov",
    "Delgado", "Mwangi", "Petrov", "Rossi", "Dubois", "Silva",
]
COMPANY_HEAD = [
    "Pacific", "Northgate", "Silverline", "Harborview", "Redstone", "Blue Ridge",
    "Ironwood", "Crestwell", "Lakeshore", "Summit", "Kestrel", "Brightwater",
    "Copperfield", "Meridian", "Foxglove", "Stonebridge", "Cedarpoint", "Alderman",
]
COMPANY_TAIL = [
    "Holdings", "Properties", "Logistics", "Construction", "Capital", "Industries",
    "Developments", "Partners", "Systems", "Foods", "Media", "Freight",
]
SUFFIX = ["Inc.", "LLC", "Ltd.", "Corp.", "LLP", ""]

MATTER_TYPES = [
    "Family", "Real Estate", "Employment", "Wills & Estates", "Civil Litigation", "Other",
]
LAWYERS = [
    "A. Whitfield", "M. Castellanos", "R. Adeyemi", "S. Thornberry", "J. Lindqvist",
]


def person(rng: random.Random) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def company(rng: random.Random) -> str:
    name = f"{rng.choice(COMPANY_HEAD)} {rng.choice(COMPANY_TAIL)}"
    suffix = rng.choice(SUFFIX)
    return f"{name} {suffix}".strip()


def party(rng: random.Random) -> str:
    # Roughly a third of parties are entities rather than individuals.
    return company(rng) if rng.random() < 0.35 else person(rng)


def main() -> None:
    rng = random.Random(SEED)
    seen: set[tuple[str, str]] = set()
    matters = []
    start = date(2019, 1, 1)

    while len(matters) < N_MATTERS:
        client = party(rng)
        opposing = party(rng)
        if client == opposing:
            continue
        key = (client, opposing)
        if key in seen:
            continue
        seen.add(key)

        opened = start + timedelta(days=rng.randint(0, 2200))
        closed = opened + timedelta(days=rng.randint(45, 900))
        matters.append(
            {
                "matter_id": f"M-{len(matters) + 1:04d}",
                "client_name": client,
                "opposing_party": opposing,
                "matter_type": rng.choice(MATTER_TYPES),
                "opened": opened.isoformat(),
                "closed": closed.isoformat() if closed < date(2026, 7, 19) else None,
                "lawyer": rng.choice(LAWYERS),
            }
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(matters, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(matters)} synthetic matters to {OUT}")
    print(f"  entities as client   : {sum(1 for m in matters if any(s in m['client_name'] for s in ('Inc.','LLC','Ltd.','Corp.','LLP')))}")
    print(f"  open (unclosed)      : {sum(1 for m in matters if m['closed'] is None)}")


if __name__ == "__main__":
    main()
