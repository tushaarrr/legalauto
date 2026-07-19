"""OpenCorporates — company entity verification for a corporate opposing party.

Purpose: confirm the other side is a real, currently-registered entity. A
dissolved company, or no match at all for a name presented as a company, is worth
a human's attention before the firm commits.

This client is CONDITIONAL: it is only called when the party name actually looks
like an organisation. Firing a company-registry lookup at "Kate Hall" wastes a
request on a free tier and returns noise, so the heuristic below gates it and the
skip is recorded explicitly rather than silently.

OpenCorporates requires an API key (their open tier now 401s without one). With
no key configured the client self-reports `unavailable` without making a call.
"""

from __future__ import annotations

import re
import time

import httpx

from ..schema import SourceResult
from .base import DiskCache, env, request_with_retry, skipped, unavailable

SOURCE = "opencorporates"
BASE_URL = "https://api.opencorporates.com/v0.4/companies/search"
MAX_RESULTS = 5

_cache = DiskCache(SOURCE)

# Tokens that mark a name as an organisation rather than a person. Legal forms
# ("Inc", "LLC") plus the trading words that reliably indicate a business.
_COMPANY_TOKENS = {
    "inc", "incorporated", "llc", "llp", "lp", "ltd", "limited", "plc", "corp",
    "corporation", "co", "company", "pllc", "gmbh", "pty", "nv", "bv", "ag", "sa",
    "holdings", "group", "partners", "associates", "enterprises", "industries",
    "properties", "capital", "ventures", "solutions", "services", "systems",
    "logistics", "construction", "developments", "trust", "foundation", "bank",
}


def looks_like_company(name: str | None) -> bool:
    """Heuristic gate: is this name an organisation?

    Deliberately conservative — a false negative just means we skip a lookup,
    while a false positive spends a request and returns noise for a human to wade
    through. Matches on whole tokens so a surname like "Ltdridge" can't trigger it.
    """
    if not name:
        return False
    tokens = re.sub(r"[^\w\s]", " ", name.lower()).split()
    return any(t in _COMPANY_TOKENS for t in tokens)


def _summarize(payload: dict) -> dict:
    results = (payload.get("results") or {}).get("companies") or []
    companies = []
    for wrapper in results[:MAX_RESULTS]:
        c = wrapper.get("company", {})
        companies.append({
            "name": c.get("name"),
            "company_number": c.get("company_number"),
            "jurisdiction": c.get("jurisdiction_code"),
            "status": c.get("current_status"),
            "incorporation_date": c.get("incorporation_date"),
            "dissolved": bool(c.get("dissolution_date")),
            "url": c.get("opencorporates_url"),
        })
    return {
        "total_matches": (payload.get("results") or {}).get("total_count", 0),
        "returned": len(companies),
        "companies": companies,
    }


async def fetch(client: httpx.AsyncClient, party_name: str) -> SourceResult:
    """Look up `party_name` in the company registry. Never raises."""
    if not party_name:
        return skipped(SOURCE, "no party name to search")

    # The conditional call. Recorded as `skipped`, not `unavailable` — we chose
    # not to ask, which is different from asking and getting nothing.
    if not looks_like_company(party_name):
        return skipped(
            SOURCE,
            f'"{party_name}" does not look like a company; registry lookup not applicable',
            query=party_name,
        )

    api_key = env("OPENCORPORATES_API_KEY")
    if not api_key:
        return unavailable(SOURCE, "OPENCORPORATES_API_KEY is not set", party_name)

    cache_key = party_name.lower().strip()
    if (hit := _cache.get(cache_key)) is not None:
        return SourceResult(source=SOURCE, status="ok", data=hit,
                            query=party_name, cached=True)

    started = time.perf_counter()
    try:
        resp, attempts = await request_with_retry(
            client, BASE_URL, params={"q": party_name, "api_token": api_key}
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
