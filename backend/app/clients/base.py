"""Shared machinery for the external enrichment clients.

Every client in this package returns a SourceResult and never raises into the
pipeline. That is the whole contract: enrichment is best-effort context, so a
dead or unconfigured source is a flag on the record, not a failed intake.

What lives here:
  * `request_with_retry` - exponential backoff on network errors and 5xx, with
    an extra attempt reserved for 429 so a rate limit doesn't burn the budget
    that transient failures need.
  * `DiskCache` - keyed by (source, query). Re-running the same intake while
    testing must not hammer a free public API; this is politeness, not just speed.
  * `robots_allows` - a real robots.txt check, used before any scrape.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import httpx

from ..schema import SourceResult

BACKEND_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = BACKEND_ROOT / ".cache" / "enrichment"
CACHE_TTL_SECONDS = 24 * 60 * 60

# 1 initial attempt + 2 retries. A 429 buys one additional attempt on top.
MAX_RETRIES = 2
BASE_BACKOFF = 0.5
DEFAULT_TIMEOUT = 20.0


class SourceRequestError(httpx.HTTPError):
    """A request that failed after exhausting retries, carrying the attempt count.

    Without this the audit log would record `attempts=0` for a source that in
    fact tried three times over several seconds — a run log that understates the
    work done is a run log you cannot trust.
    """

    def __init__(self, message: str, attempts: int) -> None:
        super().__init__(message)
        self.attempts = attempts


class DiskCache:
    """Tiny JSON cache so repeated test runs don't re-hit public APIs."""

    def __init__(self, namespace: str, ttl: int = CACHE_TTL_SECONDS) -> None:
        self.dir = CACHE_DIR / namespace
        self.ttl = ttl

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        return self.dir / f"{digest}.json"

    def get(self, key: str) -> dict | None:
        path = self._path(key)
        if not path.exists():
            return None
        if time.time() - path.stat().st_mtime > self.ttl:
            return None  # stale; treat as a miss and let it be refetched
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, key: str, value: dict) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            self._path(key).write_text(json.dumps(value), encoding="utf-8")
        except OSError:
            pass  # a cache that can't write is not a reason to fail the call


async def request_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
) -> tuple[httpx.Response, int]:
    """GET with backoff. Returns (response, attempts_made).

    Retries transport errors and 5xx. A 429 is retried too, with an extra
    allowance, because a rate limit means "later", not "broken". 4xx other than
    429 is returned immediately — retrying a 401 just wastes everyone's time.
    """
    attempts = 0
    extra_for_429 = 1
    last_exc: Exception | None = None

    while attempts <= MAX_RETRIES + extra_for_429:
        attempts += 1
        try:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code == 429 and extra_for_429 > 0:
                extra_for_429 -= 1
                delay = float(resp.headers.get("Retry-After") or BASE_BACKOFF * 2**attempts)
                await asyncio.sleep(min(delay, 10.0))
                continue
            if 500 <= resp.status_code < 600 and attempts <= MAX_RETRIES:
                await asyncio.sleep(BASE_BACKOFF * 2 ** (attempts - 1) + random.random() * 0.1)
                continue
            return resp, attempts
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempts > MAX_RETRIES:
                break
            await asyncio.sleep(BASE_BACKOFF * 2 ** (attempts - 1) + random.random() * 0.1)

    raise SourceRequestError(
        str(last_exc) if last_exc else f"{url} failed after {attempts} attempts",
        attempts,
    )


def robots_allows(url: str, user_agent: str = "LegalFlowBot") -> tuple[bool, str]:
    """Does this site's robots.txt permit fetching `url`?

    Returns (allowed, reason). A site we cannot ask (robots.txt unreachable) is
    treated as DISALLOWED: the spec says skip and flag rather than scrape anyway,
    and "I couldn't check" is not permission.
    """
    try:
        parts = urlparse(url)
        robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        parser.read()
        if parser.can_fetch(user_agent, url):
            return True, f"robots.txt at {robots_url} permits {user_agent}"
        return False, f"robots.txt at {robots_url} disallows {user_agent}"
    except Exception as exc:  # unreachable robots.txt, DNS failure, etc.
        return False, f"could not verify robots.txt ({type(exc).__name__}); treating as disallowed"


def skipped(source: str, reason: str, query: str | None = None) -> SourceResult:
    """A source we deliberately chose not to call."""
    return SourceResult(source=source, status="skipped", error=reason, query=query)


def unavailable(source: str, reason: str, query: str | None = None, attempts: int = 0,
                latency_ms: int = 0) -> SourceResult:
    """A source that was tried (or lacks credentials) and produced nothing."""
    return SourceResult(source=source, status="unavailable", error=reason,
                        query=query, attempts=attempts, latency_ms=latency_ms)


def env(name: str) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else None
