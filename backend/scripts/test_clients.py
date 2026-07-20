"""Exercise each enrichment client in isolation — before any pipeline wiring.

Covers the paths that matter: a live call with real data, the conditional skip,
the missing-credential path, a forced failure with retries, and the cache.

    python -m scripts.test_clients
"""

from __future__ import annotations

import asyncio
import json
import os
import time

import httpx

from app.clients import courtlistener, firecrawl, gleif
from app.clients.base import DEFAULT_TIMEOUT
from app.clients.gleif import looks_like_company


def show(label: str, r) -> None:
    icon = {"ok": "OK  ", "skipped": "SKIP", "unavailable": "DOWN"}[r.status]
    print(f"  [{icon}] {label}")
    print(f"         source={r.source} status={r.status} latency={r.latency_ms}ms "
          f"attempts={r.attempts} cached={r.cached}")
    if r.error:
        print(f"         reason: {r.error}")
    if r.data:
        body = json.dumps(r.data, indent=2)
        for line in body.splitlines()[:14]:
            print(f"         {line}")
    print()


async def main() -> None:
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
        print("=" * 72)
        print("1. COMPANY HEURISTIC (gates the GLEIF entity lookup)")
        print("=" * 72)
        for name in ["Pacific Holdings Ltd", "Kestrel Properties LLC", "Acme Industries",
                     "Kate Hall", "Nadia Bergstrom", "Wendell Farthing"]:
            print(f"  {'COMPANY' if looks_like_company(name) else 'PERSON '}  {name}")
        print()

        print("=" * 72)
        print("2. COURTLISTENER — live call, real public data")
        print("=" * 72)
        r = await courtlistener.fetch(client, "Pacific Holdings Ltd")
        show("company party, first call (uncached)", r)

        t0 = time.perf_counter()
        r2 = await courtlistener.fetch(client, "Pacific Holdings Ltd")
        cached_ms = (time.perf_counter() - t0) * 1000
        print(f"  cache check: cached={r2.cached}, served in {cached_ms:.1f}ms "
              f"(vs {r.latency_ms}ms live)\n")

        r3 = await courtlistener.fetch(client, "Kate Hall")
        show("individual party (CourtListener still applies)", r3)

        print("=" * 72)
        print("3. GLEIF — live entity verification (no key), conditional skip")
        print("=" * 72)
        show("individual -> must SKIP (registry lookup not applicable)",
             await gleif.fetch(client, "Kate Hall"))
        show("company, exact legal-name match", await gleif.fetch(client, "Pacific Holdings Ltd"))
        show("company, misspelled -> falls back to GLEIF fuzzy index",
             await gleif.fetch(client, "Kestrel Properties LLC"))

        print("=" * 72)
        print("4. FIRECRAWL — gates: key, target, robots.txt")
        print("=" * 72)
        show("no key configured", await firecrawl.fetch(client, "Pacific Holdings Ltd"))

        os.environ["FIRECRAWL_API_KEY"] = "fake-key-for-gate-test"
        show("key set, but no target configured -> SKIP",
             await firecrawl.fetch(client, "Pacific Holdings Ltd"))

        # A target that robots.txt disallows must be skipped, not scraped.
        os.environ["FIRECRAWL_TARGET_URL"] = "https://www.google.com/search?q={query}"
        show("target configured but robots.txt DISALLOWS -> SKIP, not scraped",
             await firecrawl.fetch(client, "Pacific Holdings Ltd"))
        os.environ.pop("FIRECRAWL_API_KEY", None)
        os.environ.pop("FIRECRAWL_TARGET_URL", None)

        print("=" * 72)
        print("5. GRACEFUL DEGRADATION — forced failure, with retries")
        print("=" * 72)
        real_url = courtlistener.BASE_URL
        courtlistener.BASE_URL = "https://courtlistener-does-not-exist.invalid/api/"
        t0 = time.perf_counter()
        bad = await courtlistener.fetch(client, "Unreachable Co")
        print(f"  (took {time.perf_counter() - t0:.2f}s including backoff)")
        show("unreachable host -> unavailable, no exception escaped", bad)
        courtlistener.BASE_URL = real_url

        print("=" * 72)
        print("6. HTTP 500 -> retried, then reported (httpbin)")
        print("=" * 72)
        courtlistener.BASE_URL = "https://httpbin.org/status/500"
        r500 = await courtlistener.fetch(client, "Five Hundred Co")
        show("server error -> unavailable after retries", r500)
        courtlistener.BASE_URL = real_url

        print("All client paths exercised. No exception escaped any client.")


if __name__ == "__main__":
    asyncio.run(main())
