"""Firecrawl — scrape a configured public listing that has no clean API.

Purpose: fill gaps the two structured APIs don't cover, e.g. a state tribunal or
registry whose only interface is a search page.

Three gates before anything is fetched, all of which record a reason:

  1. FIRECRAWL_API_KEY must be set.
  2. FIRECRAWL_TARGET_URL must be configured. There is no default target on
     purpose — silently scraping some hardcoded site is exactly the behaviour
     the spec rules out.
  3. The target's robots.txt must permit it. If robots disallows, or cannot be
     read, this source SKIPS and flags. It does not scrape anyway.

Gate 3 is the one worth arguing for: the polite thing and the correct thing agree
here, and a scraper that ignores robots.txt is a liability in a legal product.
"""

from __future__ import annotations

import time

import httpx

from ..schema import SourceResult
from .base import DiskCache, env, request_with_retry, robots_allows, skipped, unavailable

SOURCE = "firecrawl"
API_URL = "https://api.firecrawl.dev/v1/scrape"

_cache = DiskCache(SOURCE)


def _build_target(template: str, party_name: str) -> str:
    """Substitute the party into the configured target URL template."""
    from urllib.parse import quote_plus
    if "{query}" in template:
        return template.replace("{query}", quote_plus(party_name))
    return template


async def fetch(client: httpx.AsyncClient, party_name: str) -> SourceResult:
    """Scrape the configured target for `party_name`. Never raises."""
    if not party_name:
        return skipped(SOURCE, "no party name to search")

    api_key = env("FIRECRAWL_API_KEY")
    if not api_key:
        return unavailable(SOURCE, "FIRECRAWL_API_KEY is not set", party_name)

    template = env("FIRECRAWL_TARGET_URL")
    if not template:
        return skipped(
            SOURCE,
            "FIRECRAWL_TARGET_URL is not configured; no scrape target set "
            "(deliberate: this source has no default target)",
            query=party_name,
        )

    target = _build_target(template, party_name)

    # robots.txt gate — checked before any request to the target.
    allowed, reason = robots_allows(target)
    if not allowed:
        return skipped(SOURCE, f"robots.txt gate: {reason}", query=target)

    cache_key = target.lower()
    if (hit := _cache.get(cache_key)) is not None:
        return SourceResult(source=SOURCE, status="ok", data=hit,
                            query=target, cached=True)

    started = time.perf_counter()
    try:
        resp = await client.post(
            API_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"url": target, "formats": ["markdown"], "onlyMainContent": True},
        )
        elapsed = int((time.perf_counter() - started) * 1000)
        if resp.status_code != 200:
            return unavailable(SOURCE, f"HTTP {resp.status_code}", target, 1, elapsed)
        payload = resp.json()
        content = (payload.get("data") or {}).get("markdown") or ""
        data = {
            "target_url": target,
            "robots_check": reason,
            "content_chars": len(content),
            # Trimmed: this is a brief for a human, not a page dump.
            "excerpt": content[:1500],
        }
        _cache.set(cache_key, data)
        return SourceResult(source=SOURCE, status="ok", data=data, query=target,
                            latency_ms=elapsed, attempts=1)
    except Exception as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        return unavailable(SOURCE, f"{type(exc).__name__}: {exc}", target,
                           attempts=getattr(exc, "attempts", 1), latency_ms=elapsed)
