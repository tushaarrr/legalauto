"""GLEIF — company entity verification via the Global LEI index.

Replaces OpenCorporates, whose API now requires an approved key. GLEIF is the
Global Legal Entity Identifier Foundation: the registry behind the LEI codes
financial regulators require, assembled from official company registries
worldwide. It is free, needs no key, and is global rather than single-country.

Purpose: confirm the opposing party is a real, currently-registered entity, and
flag when it is not. A dissolved company, a lapsed registration, or a name with
no registry match at all is exactly what a lawyer wants to see before the firm
commits to acting against it.

Two-step lookup, because names arrive messy:
  1. exact match on the registered legal name
  2. if that finds nothing, GLEIF's own fuzzy completion endpoint, then fetch the
     candidate records. `matched_via` records which path produced the answer, so
     a fuzzy hit is never presented as a confirmed identity.

This client reports findings; it never decides. "INACTIVE" is surfaced as a flag
for a human, not turned into an automatic conflict.
"""

from __future__ import annotations

import re
import time

import httpx

from ..schema import SourceResult
from .base import DiskCache, request_with_retry, skipped, unavailable

SOURCE = "gleif"
BASE_URL = "https://api.gleif.org/api/v1/lei-records"
FUZZY_URL = "https://api.gleif.org/api/v1/fuzzycompletions"
MAX_RESULTS = 5
MAX_FUZZY_CANDIDATES = 3

_cache = DiskCache(SOURCE)

# Tokens that mark a name as an organisation rather than a person. Legal forms
# plus the trading words that reliably indicate a business.
_COMPANY_TOKENS = {
    "inc", "incorporated", "llc", "llp", "lp", "ltd", "limited", "plc", "corp",
    "corporation", "co", "company", "pllc", "gmbh", "pty", "nv", "bv", "ag", "sa",
    "ulc", "holdings", "group", "partners", "associates", "enterprises",
    "industries", "properties", "capital", "ventures", "solutions", "services",
    "systems", "logistics", "construction", "developments", "trust",
    "foundation", "bank",
    # Non-English legal forms — GLEIF is a global registry, so an opposing party
    # is as likely to be "... A/S" or "... S.p.A." as "... Inc."
    "as", "aps", "ab", "oy", "oyj", "srl", "spa", "sas", "sarl", "bhd", "sdn",
    "kk", "kg", "ohg", "ev", "asa", "nuf", "cv", "vof",
}


def _tokens(name: str) -> list[str]:
    """Split a party name into comparable tokens.

    Periods and slashes are stripped BEFORE splitting so punctuated legal forms
    survive as one token: "S.A." must become "sa" and "A/S" must become "as".
    Splitting first would shatter them into single letters, and a name like "HSH
    Nordbank Securities S.A." would then read as an individual.
    """
    collapsed = re.sub(r"[./]", "", name.lower())
    return re.sub(r"[^\w\s]", " ", collapsed).split()

# Legal-form suffixes only — NOT the trading words above. "Holdings" and
# "Properties" are part of a company's actual name; "LLC" and "Ltd" are the form
# it happens to take, and an intake often gets that part wrong.
_LEGAL_FORMS = {
    "inc", "incorporated", "llc", "llp", "lp", "ltd", "limited", "plc", "corp",
    "corporation", "co", "company", "pllc", "gmbh", "pty", "nv", "bv", "ag",
    "sa", "ulc",
}

# Entity/registration states that deserve a human's eye.
_INACTIVE_REGISTRATION = {"LAPSED", "RETIRED", "ANNULLED", "DUPLICATE"}


def _strip_legal_form(name: str) -> str:
    """Drop legal-form tokens, keeping the distinctive part of the name.

    GLEIF's fuzzy index matches against registered legal names, so a suffix the
    intake guessed wrong actively prevents a match: "Kestrel Properties LLC"
    returns nothing, while "Kestrel Properties" finds "KESTRAL PROPERTIES
    LIMITED". Measured against the live API, not assumed.
    """
    cleaned = re.sub(r"[^\w\s]", " ", name)
    kept = [t for t in cleaned.split() if t.lower() not in _LEGAL_FORMS]
    return " ".join(kept) or name


def looks_like_company(name: str | None) -> bool:
    """Heuristic gate: is this name an organisation?

    Deliberately conservative — a false negative only costs us a skipped lookup,
    while a false positive spends a request and hands a human noise to wade
    through. Matches whole tokens so a surname like "Ltdridge" can't trigger it.
    """
    if not name:
        return False
    return any(t in _COMPANY_TOKENS for t in _tokens(name))


def _flags_for(entity: dict, registration: dict) -> list[str]:
    """What about this record should a reviewing lawyer notice?"""
    flags: list[str] = []
    status = (entity.get("status") or "").upper()
    if status and status != "ACTIVE":
        flags.append(f"entity status is {status}, not ACTIVE")
    reg_status = (registration.get("status") or "").upper()
    if reg_status in _INACTIVE_REGISTRATION:
        flags.append(f"LEI registration is {reg_status}; registry data may be stale")
    if entity.get("successorEntity") or entity.get("successorEntities"):
        flags.append("entity has a successor on record (merged or absorbed)")
    if entity.get("expiration", {}) and (entity.get("expiration") or {}).get("date"):
        flags.append(f"entity has an expiration date: {entity['expiration']['date']}")
    return flags


def _record(item: dict) -> dict:
    a = item.get("attributes", {})
    entity = a.get("entity", {}) or {}
    registration = a.get("registration", {}) or {}
    address = entity.get("legalAddress", {}) or {}
    lei = a.get("lei")
    return {
        "name": (entity.get("legalName") or {}).get("name"),
        "lei": lei,
        "jurisdiction": entity.get("jurisdiction"),
        "status": entity.get("status"),
        "registration_status": registration.get("status"),
        "legal_form": (entity.get("legalForm") or {}).get("id"),
        # The company number in its home registry, when GLEIF has it.
        "registered_as": entity.get("registeredAs"),
        "creation_date": entity.get("creationDate"),
        "address": ", ".join(x for x in [address.get("city"), address.get("country")] if x),
        "flags": _flags_for(entity, registration),
        "url": f"https://search.gleif.org/#/record/{lei}" if lei else None,
    }


def _summarize(payload: dict, matched_via: str) -> dict:
    items = payload.get("data") or []
    companies = [_record(i) for i in items[:MAX_RESULTS]]
    total = ((payload.get("meta") or {}).get("pagination") or {}).get("total", len(items))
    return {
        "total_matches": total,
        "matched_via": matched_via,
        "returned": len(companies),
        "companies": companies,
        # Roll the per-record flags up so a caller doesn't have to dig for them.
        "flags": sorted({f for c in companies for f in c["flags"]}),
    }


async def _fuzzy_leis(client: httpx.AsyncClient, name: str) -> list[str]:
    """Ask GLEIF for the closest registered names, return their LEI codes."""
    resp, _ = await request_with_retry(
        client, FUZZY_URL, params={"field": "entity.legalName", "q": name}
    )
    if resp.status_code != 200:
        return []
    leis: list[str] = []
    for item in (resp.json().get("data") or [])[:MAX_FUZZY_CANDIDATES]:
        lei = (((item.get("relationships") or {}).get("lei-records") or {})
               .get("data") or {}).get("id")
        if lei:
            leis.append(lei)
    return leis


async def fetch(client: httpx.AsyncClient, party_name: str) -> SourceResult:
    """Verify `party_name` against the global LEI registry. Never raises."""
    if not party_name:
        return skipped(SOURCE, "no party name to search")

    # The conditional call. Recorded as `skipped` — choosing not to ask is a
    # different fact from asking and getting nothing.
    if not looks_like_company(party_name):
        return skipped(
            SOURCE,
            f'"{party_name}" does not look like a company; entity lookup not applicable',
            query=party_name,
        )

    cache_key = party_name.lower().strip()
    if (hit := _cache.get(cache_key)) is not None:
        return SourceResult(source=SOURCE, status="ok", data=hit,
                            query=party_name, cached=True)

    started = time.perf_counter()
    total_attempts = 0
    try:
        resp, attempts = await request_with_retry(
            client, BASE_URL,
            params={"filter[entity.legalName]": party_name, "page[size]": MAX_RESULTS},
        )
        total_attempts += attempts
        if resp.status_code != 200:
            elapsed = int((time.perf_counter() - started) * 1000)
            return unavailable(SOURCE, f"HTTP {resp.status_code}", party_name,
                               total_attempts, elapsed)

        payload = resp.json()
        data = _summarize(payload, "exact")

        # Nothing under the exact legal name — try GLEIF's fuzzy index before
        # concluding the entity doesn't exist.
        if not data["companies"]:
            leis = await _fuzzy_leis(client, _strip_legal_form(party_name))
            total_attempts += 1
            if leis:
                resp2, attempts2 = await request_with_retry(
                    client, BASE_URL, params={"filter[lei]": ",".join(leis)}
                )
                total_attempts += attempts2
                if resp2.status_code == 200:
                    data = _summarize(resp2.json(), "fuzzy")

        elapsed = int((time.perf_counter() - started) * 1000)
        _cache.set(cache_key, data)
        return SourceResult(source=SOURCE, status="ok", data=data, query=party_name,
                            latency_ms=elapsed, attempts=total_attempts)
    except Exception as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        return unavailable(SOURCE, f"{type(exc).__name__}: {exc}", party_name,
                           attempts=getattr(exc, "attempts", total_attempts),
                           latency_ms=elapsed)
