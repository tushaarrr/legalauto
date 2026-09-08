"""Conflict-of-interest checking against the firm's matter history.

This is the most legally-specific piece of the pipeline, so the rule it encodes
is worth stating plainly:

    A conflict is an ADVERSE relationship, not a familiar name.

    * new opposing party ~= a FORMER CLIENT   -> conflict. The firm has
      confidential information about the party it would now be against.
    * new client ~= a FORMER OPPOSING PARTY   -> conflict. The firm was
      previously adverse to the person now asking it for help.
    * new client ~= a former CLIENT           -> NOT a conflict. That is a
      returning client, reported separately as a dedup/context signal.

Missing an adverse match can get the firm disqualified; over-flagging is merely
annoying. The thresholds below are therefore deliberately asymmetric — we would
rather surface a POTENTIAL for a human to dismiss than silently clear a match.

Matching is fuzzy because names arrive messy: legal suffixes ("Pacific Holdings
Inc." vs "Pacific Holdings, LLC"), nicknames ("Bob Chen" vs "Robert Chen"), and
punctuation all have to collapse to the same key.

The history is a JSON file standing in for the firm's matter database. Like
storage.py, everything source-specific is isolated here, so swapping in Postgres
means rewriting this module's loader and nothing else.
"""

from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

from .schema import ConflictMatch, ConflictResult

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY = BACKEND_ROOT / "samples" / "matter_history.json"

# A match at or above STRONG is reported as a definite CONFLICT; between WEAK and
# STRONG it is a POTENTIAL for a human to adjudicate. Below WEAK we ignore it.
STRONG_MATCH = 0.92
WEAK_MATCH = 0.82

# Corporate suffixes and personal titles carry no identifying signal — strip them
# so "Pacific Holdings Inc." and "Pacific Holdings, LLC" compare equal.
# Legal-form suffixes ONLY. Words like "Holdings", "Group" or "Partners" look
# like boilerplate but are part of the distinctive name — stripping them collapses
# "Kestrel Holdings" to "Kestrel", which then matches every unrelated Kestrel
# entity in the history.
_SUFFIXES = {
    "inc", "llc", "ltd", "limited", "corp", "corporation", "co", "company",
    "plc", "llp", "lp", "pllc", "gmbh", "pty",
}
_TITLES = {"mr", "mrs", "ms", "miss", "dr", "prof", "sir", "madam", "mx"}

# Common short forms, mapped to the formal name. A conflict check that misses
# "Bob" vs "Robert" is not doing its job.
_NICKNAMES = {
    "bob": "robert", "bobby": "robert", "rob": "robert",
    "jon": "jonathan", "johnny": "john", "jack": "john",
    "bill": "william", "billy": "william", "will": "william",
    "mike": "michael", "mick": "michael",
    "liz": "elizabeth", "beth": "elizabeth", "betty": "elizabeth", "eliza": "elizabeth",
    "dave": "david", "jim": "james", "jimmy": "james",
    "tom": "thomas", "tommy": "thomas",
    "chris": "christopher", "tony": "anthony",
    "rick": "richard", "dick": "richard", "rich": "richard",
    "steve": "stephen", "steven": "stephen",
    "sue": "susan", "susie": "susan",
    "kate": "katherine", "katie": "katherine", "kathy": "katherine",
    "cathy": "catherine", "peggy": "margaret", "maggie": "margaret",
    "pat": "patricia", "patty": "patricia",
    "sandy": "sandra", "barb": "barbara", "lin": "linda",
    "matt": "matthew", "dan": "daniel", "danny": "daniel",
    "ben": "benjamin", "sam": "samuel", "alex": "alexander",
    "nick": "nicholas", "greg": "gregory", "andy": "andrew",
}


# Words that describe someone's ROLE rather than identify them. An intake saying
# "my employer" names nobody, and a conflict check cannot screen a role.
_GENERIC_ROLES = {
    "employer", "employee", "landlord", "tenant", "spouse", "husband", "wife",
    "partner", "company", "business", "driver", "neighbor", "neighbour",
    "contractor", "builder", "insurer", "insurance", "bank", "lender", "seller",
    "buyer", "defendant", "plaintiff", "party", "side", "boss", "manager",
    "supervisor", "firm", "organization", "organisation", "agency", "school",
    "hospital", "doctor", "someone", "somebody", "unknown", "na", "none",
    "landlords", "employers", "father", "mother", "brother", "sister", "sibling",
    "son", "daughter", "family", "relative", "estate", "council", "government",
}
# Determiners and qualifiers that carry no identifying information on their own.
_FILLER = {
    "my", "the", "our", "his", "her", "their", "a", "an", "this", "that",
    "other", "opposing", "former", "previous", "ex", "current", "of", "s",
}


def is_generic_party_reference(name: str | None) -> bool:
    """True when a "name" identifies nobody — "my employer", "the other driver".

    The extraction prompt already asks the model to return null in this case, but
    a prompt is a request, not a guarantee: the model does sometimes hand back the
    literal phrase. That is worse than a null, because a non-null opposing party
    silently suppresses the "only one side was screened" limitation and turns an
    unscreened intake into a confident CLEAR. So the rule is enforced in code.
    """
    if not name:
        return False
    # Literal placeholders a model reaches for when it has nothing. Checked
    # before tokenizing, since "n/a" would otherwise split into meaningless parts.
    if name.strip().lower() in {"n/a", "na", "none", "unknown", "tbd", "-", "--", "?", "not specified", "not stated"}:
        return True
    tokens = [t for t in re.sub(r"[^\w\s]", " ", name.lower()).split()]
    meaningful = [t for t in tokens if t not in _FILLER]
    if not meaningful:
        return True  # e.g. "the other"
    return all(t in _GENERIC_ROLES for t in meaningful)


def _normalize(name: str) -> str:
    """Lowercase, strip punctuation, drop titles and corporate suffixes."""
    text = re.sub(r"[^\w\s]", " ", (name or "").lower())
    tokens = [t for t in text.split() if t and t not in _TITLES and t not in _SUFFIXES]
    return " ".join(tokens)


def _canon_tokens(normalized: str) -> frozenset[str]:
    """Token set with nicknames folded to their formal form."""
    return frozenset(_NICKNAMES.get(t, t) for t in normalized.split())


@lru_cache(maxsize=8192)
def similarity(a: str, b: str) -> float:
    """How likely are these two strings the same party? 0.0 - 1.0.

    Deliberately generous on name variants (suffixes, nicknames, word order) and
    strict on genuinely different names — "James Ivanov" and "James Silva" share a
    token but must not match.
    """
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0

    ta, tb = _canon_tokens(na), _canon_tokens(nb)
    if ta == tb:
        return 0.98  # same parts, different order/nickname/suffix
    if ta and tb and (ta <= tb or tb <= ta):
        # One name is a strict subset of the other ("Pacific" vs "Pacific
        # Freight"). Genuinely ambiguous — could be the same entity or two
        # unrelated ones sharing a word — so this scores into POTENTIAL for a
        # human to settle, deliberately below the automatic-CONFLICT threshold.
        return 0.88

    ratio = SequenceMatcher(None, na, nb).ratio()
    overlap = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    # Blend character-level and token-level agreement; character similarity alone
    # rates "Ivanov"/"Silva" too highly when the first name matches.
    return max(ratio * 0.9, (ratio + overlap) / 2)


@lru_cache(maxsize=4)
def load_history(path: str | None = None) -> tuple[dict, ...]:
    """Load the firm's past matters. Cached — the file is read once per path."""
    target = Path(path or os.environ.get("MATTER_HISTORY_PATH") or DEFAULT_HISTORY)
    if not target.is_absolute():
        target = BACKEND_ROOT / target
    if not target.exists():
        raise FileNotFoundError(
            f"Matter history not found at {target}. Run: python -m scripts.seed_matter_history"
        )
    return tuple(json.loads(target.read_text(encoding="utf-8")))


def check_conflicts(
    client_name: str | None,
    opposing_party: str | None,
    history_path: str | None = None,
) -> ConflictResult:
    """Screen a new intake against every past matter.

    Returns CONFLICT / POTENTIAL / CLEAR plus the specific matters that triggered
    it, so the reviewing lawyer sees *why* rather than a bare verdict.
    """
    # A role identifies nobody, so it cannot be screened. llm.py applies this to
    # the model's output, but the reviewer can type "my employer" straight into
    # the field — so the guard belongs here, where every caller routes through.
    # Without it a role-shaped string reads as a screened party and suppresses
    # the "only one side was checked" limitation below.
    if is_generic_party_reference(opposing_party):
        opposing_party = None
    if is_generic_party_reference(client_name):
        client_name = None

    history = load_history(history_path)
    matches: list[ConflictMatch] = []
    returning: list[str] = []

    for matter in history:
        past_client = matter["client_name"]
        past_opposing = matter["opposing_party"]

        # Adverse direction 1: the party we'd now be against is a former client.
        if opposing_party:
            score = similarity(opposing_party, past_client)
            if score >= WEAK_MATCH:
                matches.append(ConflictMatch(
                    matter_id=matter["matter_id"], score=round(score, 3),
                    kind="opposing_party_is_former_client",
                    reason=(f"Opposing party \"{opposing_party}\" matches former client "
                            f"\"{past_client}\" ({matter['matter_id']}, {matter['matter_type']})"),
                    past_client=past_client, past_opposing=past_opposing,
                    matter_type=matter["matter_type"],
                ))

        # Adverse direction 2: this prospective client is someone we opposed.
        if client_name:
            score = similarity(client_name, past_opposing)
            if score >= WEAK_MATCH:
                matches.append(ConflictMatch(
                    matter_id=matter["matter_id"], score=round(score, 3),
                    kind="client_is_former_opposing_party",
                    reason=(f"Prospective client \"{client_name}\" matches opposing party "
                            f"\"{past_opposing}\" in {matter['matter_id']} "
                            f"({matter['matter_type']}), where the firm acted for {past_client}"),
                    past_client=past_client, past_opposing=past_opposing,
                    matter_type=matter["matter_type"],
                ))

            # Not adverse — a returning client. Context, not a conflict.
            if similarity(client_name, past_client) >= STRONG_MATCH:
                returning.append(matter["matter_id"])

    matches.sort(key=lambda m: m.score, reverse=True)

    if any(m.score >= STRONG_MATCH for m in matches):
        status = "CONFLICT"
    elif matches:
        status = "POTENTIAL"
    else:
        status = "CLEAR"

    # A clear result is only as trustworthy as the names it had to work with.
    limitations: list[str] = []
    if not opposing_party:
        limitations.append(
            "No opposing party was identified in the intake, so only one side "
            "could be screened. This check is INCOMPLETE — confirm the opposing "
            "party before relying on a CLEAR result."
        )
    if not client_name:
        limitations.append("No client name was identified in the intake.")

    return ConflictResult(
        status=status,
        matches=matches[:10],
        returning_client_matters=returning[:10],
        checked_against=len(history),
        limitations=limitations,
    )
