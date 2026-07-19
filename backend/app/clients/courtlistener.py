"""CourtListener — prior-litigation lookup for a named party.

Free, official API from the Free Law Project. A token raises the rate limit but
is NOT required for search, so this source works out of the box; when
COURTLISTENER_TOKEN is set we send it.

Purpose in the pipeline: surface whether a party has appeared in litigation
before. This is context for the reviewing lawyer, not a verdict — a common name
will match unrelated people, so results are returned verbatim with their court
and date for a human to judge. Nothing here feeds an automatic decision.
"""

from __future__ import annotations

import time

import httpx

from ..schema import SourceResult
from .base import DEFAULT_TIMEOUT, DiskCache, env, request_with_retry, unavailable

SOURCE = "courtlistener"
BASE_URL = "https://www.courtlistener.com/api/rest/v4/search/"
MAX_RESULTS = 5

_cache = DiskCache(SOURCE)


def _summarize(payload: dict) -> dict:
    """Keep the handful of fields a lawyer would actually read."""
    cases = []
    for item in (payload.get("results") or [])[:MAX_RESULTS]:
        cases.append({
            "case_name": item.get("caseName"),
            "court": item.get("court"),
            "date_filed": item.get("dateFiled"),
            "docket_number": item.get("docketNumber"),
            "url": (f"https://www.courtlistener.com{item['absolute_url']}"
                    if item.get("absolute_url") else None),
        })
    return {
        "total_matches": payload.get("count", 0),
        "returned": len(cases),
        "cases": cases,
    }


async def fetch(client: httpx.AsyncClient, party_name: str) -> SourceResult:
    """Search court records for `party_name`. Never raises."""
    if not party_name:
        from .base import skipped
        return skipped(SOURCE, "no party name to search")

    cache_key = party_name.lower().strip()
    if (hit := _cache.get(cache_key)) is not None:
        return SourceResult(source=SOURCE, status="ok", data=hit,
                            query=party_name, cached=True)

    headers = {"User-Agent": "LegalFlowBot/0.1 (synthetic-data demo)"}
    if token := env("COURTLISTENER_TOKEN"):
        headers["Authorization"] = f"Token {token}"

    started = time.perf_counter()
    try:
        resp, attempts = await request_with_retry(
            client, BASE_URL,
            # type=r searches RECAP dockets — federal filings, where a party
            # name is most likely to appear as an actual litigant.
            params={"q": party_name, "type": "r"},
            headers=headers,
        )
        elapsed = int((time.perf_counter() - started) * 1000)
        if resp.status_code != 200:
            return unavailable(SOURCE, f"HTTP {resp.status_code}", party_name, attempts, elapsed)
        data = _summarize(resp.json())
        _cache.set(cache_key, data)
        return SourceResult(source=SOURCE, status="ok", data=data, query=party_name,
                            latency_ms=elapsed, attempts=attempts)
    except Exception as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        return unavailable(SOURCE, f"{type(exc).__name__}: {exc}", party_name,
                           attempts=getattr(exc, "attempts", 0), latency_ms=elapsed)
