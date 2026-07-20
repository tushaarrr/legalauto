"""Discover your Airtable base/table IDs and verify the schema matches.

Run this once you have AIRTABLE_API_KEY in backend/.env. It uses the token's
schema.bases:read scope to list your bases and tables, then checks each table
against the exact field names storage.py writes — so a typo in a field name is
caught here rather than showing up as a silently dropped column later.

    python -m scripts.airtable_setup
"""

from __future__ import annotations

import sys

import httpx

from app.clients.base import env
from app.storage import _CSV_COLUMNS

META = "https://api.airtable.com/v0/meta"

# storage.py sends every CSV column except approved_at's CSV-only ordering
# concerns — the Airtable payload uses these same names.
REQUIRED_FIELDS = [c for c in _CSV_COLUMNS]


def main() -> None:
    token = env("AIRTABLE_API_KEY")
    if not token:
        print("AIRTABLE_API_KEY is not set in backend/.env.")
        print("Add this line to backend/.env (NOT .env.example), then re-run:")
        print("    AIRTABLE_API_KEY=pat...")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=30, headers=headers) as client:
        resp = client.get(f"{META}/bases")
        if resp.status_code != 200:
            print(f"Could not list bases (HTTP {resp.status_code}): {resp.text[:300]}")
            print("\nCheck the token has the schema.bases:read scope and that the")
            print("base was added under 'Access' when you created the token.")
            sys.exit(1)

        bases = resp.json().get("bases", [])
        if not bases:
            print("The token can see no bases. Re-create it and add your base under 'Access'.")
            sys.exit(1)

        print(f"Bases this token can see ({len(bases)}):\n")
        for base in bases:
            base_id, name = base["id"], base["name"]
            print(f"  {name}")
            print(f"    AIRTABLE_BASE_ID={base_id}")

            t = client.get(f"{META}/bases/{base_id}/tables")
            if t.status_code != 200:
                print(f"    (could not read tables: HTTP {t.status_code})\n")
                continue

            tables = t.json().get("tables", [])
            if not tables:
                print("    (no tables)\n")
                continue

            for table in tables:
                fields = {f["name"] for f in table.get("fields", [])}
                missing = [c for c in REQUIRED_FIELDS if c not in fields]
                print(f"    table: {table['name']!r}  ({len(fields)} fields)")
                print(f"      AIRTABLE_TABLE_NAME={table['name']}")
                if missing:
                    print(f"      MISSING {len(missing)} required field(s):")
                    for m in missing:
                        print(f"        - {m}")
                else:
                    print("      ✓ schema matches — every field storage.py writes exists")
            print()

    print("Put the AIRTABLE_BASE_ID and AIRTABLE_TABLE_NAME lines above into")
    print("backend/.env, then restart the backend. Storage switches to Airtable")
    print("automatically once all three values are present.")


if __name__ == "__main__":
    main()
