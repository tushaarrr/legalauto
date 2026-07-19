# LegalFlow — Client Intake → CRM Automation

An **approval-first** automation that turns a raw client intake (a pasted email or
form message) into a structured CRM record, screens it for conflicts of interest
against the firm's matter history, and drafts a confirmation reply — with a human
reviewing and approving everything before it is saved or sent.

> ### Please read first
> - **Synthetic data only.** Every sample intake here is fictional. No real
>   client data is used or stored.
> - **No legal advice.** The tool organizes intake logistics and drafts
>   confirmation replies. It never gives legal opinions, analysis, or
>   recommendations — a system-prompt guardrail enforces this.
> - **No auto-send.** Replies are *drafted*, never sent. There is deliberately no
>   send button — only "copy".

---

## Why this exists

Small law firms receive new inquiries as unstructured text. Someone reads each
one, figures out the matter type, copies details into a case-management system,
notes what's missing, and drafts a reply. It's slow and inconsistent under
volume.

LegalFlow automates the tedious middle — extraction, classification,
missing-field detection, draft reply — while keeping a human in control of
anything that gets persisted or leaves the building. It's a small, working proof
of the "AI assists, a human always reviews" loop.

## Demo

![LegalFlow demo](docs/demo.gif)

<!-- Record a short GIF of: load a sample → Process → edit a field → Approve &
Save → Copy reply, and save it to docs/demo.gif. -->

## How it works

```
 Raw intake text
       │
       ▼
  POST /process ──►  LLM extract (strict JSON, 1 retry)  ─►  reconcile missing fields
       │                                                          │
       │            CONFLICT SCREEN vs the firm's matter history ◄─┤
       │            (deterministic, local, no LLM)                 │
       │                                                          │
       │            LLM draft reply (logistics only, no advice) ◄─┘
       ▼
  Reviewable record  (status: needs_review, conflict: CLEAR/POTENTIAL/CONFLICT)
       │                                              — NOT persisted
       │
       ▼
  Human reviews & edits in the UI  ── the approval gate ──►  clicks Approve
       │
       ▼
  POST /approve ──►  status forced to "approved"  ─►  write to CRM (CSV or Airtable)
```

Two endpoints, split by the approval gate. `/process` only reads and drafts and
persists nothing; `/approve` is the *only* path that writes to storage.

### The two design decisions worth talking about

1. **The approval gate.** The record returned by `/process` has
   `status: needs_review` and is never written anywhere. Persistence happens only
   when a human clicks Approve, which calls `/approve`; the server — not the
   client — forces the status to `approved` before the write. See
   [`backend/app/main.py`](backend/app/main.py) and the frontend handler in
   [`frontend/app/page.tsx`](frontend/app/page.tsx).

2. **The no-advice guardrail.** The draft reply may only thank the client,
   confirm what was received, and request the missing details. A system prompt
   forbids any legal opinion or recommendation, and if the intake asks for
   advice, the draft says a lawyer will follow up rather than answering. See
   `DRAFT_SYSTEM_PROMPT` in [`backend/app/prompts.py`](backend/app/prompts.py).

3. **The conflict screen.** Before a firm can take a client it must check whether
   it has ever acted against them, or for the party they're now opposing —
   missing one is an ethics violation that can get the firm disqualified. Every
   intake is screened against the firm's matter history
   ([`backend/app/conflicts.py`](backend/app/conflicts.py)). The rule it encodes
   is that **a conflict is an adverse relationship, not a familiar name**:

   - new opposing party ≈ a *former client* → conflict
   - new client ≈ a *former opposing party* → conflict
   - new client ≈ a former *client* → **not** a conflict, just a returning client

   Matching is fuzzy because names arrive messy — "Kestrel Properties LLC" must
   match the firm's record of "Kestrel Properties Corp.", and "Kate Hall" must
   match "Katherine Hall". Two dropdown samples are seeded to trigger exactly
   those cases. The check is deterministic and local: no LLM, no network, so it
   runs on every intake and returns the same answer every time.

   A `CLEAR` verdict also reports its own **limitations**. If the intake never
   named an opposing party, only one side was screened, and the result says so
   rather than implying a clean bill of health.

Two more guarantees back these up:

- **No hallucinated values.** If a field isn't clearly in the intake, the model
  returns `null` and lists it in `missing_fields`. The server *also* reconciles
  this independently, so a null identity field is always flagged even if the
  model forgets ([`backend/app/llm.py`](backend/app/llm.py)).
- **Strict structured output.** Extraction uses the provider's strict
  JSON-schema mode, and the result is re-validated with Pydantic; on a parse
  failure it retries once with a stricter instruction, then surfaces an error.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router) + TypeScript + Tailwind — one review page |
| Backend | Python + FastAPI — `/process` and `/approve` |
| LLM | **OpenAI** (`gpt-4o-mini` by default), isolated in one module so the provider can be swapped |
| Storage / CRM | Local **CSV** by default (zero config); **Airtable** when configured |

> **Provider note:** the original spec named Anthropic/Claude; this build runs on
> OpenAI. All provider-specific code is quarantined in
> [`backend/app/llm.py`](backend/app/llm.py), so switching back means rewriting
> that one file and nothing else.

## Setup

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then edit .env and add your OPENAI_API_KEY
uvicorn app.main:app --reload # serves http://localhost:8000
```

Quick smoke test (no server needed) — runs the pipeline on 3 pasted intakes and
prints the raw JSON:

```bash
python -m scripts.test_process
```

### 2. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # optional; only if the API isn't on :8000
npm run dev                        # serves http://localhost:3000
```

Open http://localhost:3000, load a synthetic sample (or paste your own), click
**Process**, edit anything, then **Approve & Save**.

### Storage / CRM configuration

By default, approved records are appended to `backend/data/crm.csv` — no setup
required, so the demo runs out of the box. To use Airtable instead, set these in
`backend/.env` (see [`.env.example`](backend/.env.example)):

```
STORAGE_BACKEND=airtable
AIRTABLE_API_KEY=pat...
AIRTABLE_BASE_ID=app...
AIRTABLE_TABLE_NAME=Intakes
```

With `STORAGE_BACKEND=auto` (the default), Airtable is used when those three
vars are present, otherwise the CSV. The storage layer is isolated in
[`backend/app/storage.py`](backend/app/storage.py).

## Measuring accuracy (Phase 4)

There are **18 hand-labeled synthetic intakes** in
[`backend/samples/intakes.json`](backend/samples/intakes.json), three per matter
type, with a deliberate mix of complete, missing-field, and advice-seeking cases.
The sweep runs the pipeline over all of them and scores the output against the
labels:

```bash
cd backend
python -m scripts.eval_samples          # full sweep (makes real, paid LLM calls)
python -m scripts.eval_samples --limit 5   # cheap subset while iterating
```

It reports matter-type classification accuracy, per-field extraction accuracy,
the share of intakes whose missing fields were flagged exactly right, how many
classification errors the model self-flagged as low confidence, and average
pipeline latency — then writes a full JSON to `backend/eval_results/`.

### Results

Measured on all 18 labeled intakes, `gpt-4o-mini`, 2026-07-19. These are actual
sweep output, not estimates; re-run the command above to reproduce.

| Metric | Result | Sample size |
|---|---|---|
| Field extraction accuracy (overall) | **100%** (72/72) | 18 × 4 fields |
| — client_name / client_email / client_phone / jurisdiction | 100% each (18/18) | 18 |
| Missing-field flagging accuracy | **100%** (18/18) | 18 |
| Matter-type classification accuracy | **83%** (15/18) | 18 |
| — accuracy when the model reported *high* confidence | **100%** (12/12) | 12 |
| — classification errors self-flagged *low* confidence | **100%** (3/3) | 3 |
| Avg. pipeline latency per intake | **2.2s** (median 2.1s, max 3.0s) | 18 |

**What the misses were, honestly:** all three came from the same failure mode —
the model fell back to `Other` on boundary cases (a prenuptial agreement, a
property-line dispute with a neighbour, and a dispute with a contractor) where I
had labeled the specific category. Notably, **it marked all three low confidence**,
so every error surfaced in the UI with the amber "verify this" warning rather
than passing silently, and every prediction it was confident about was correct.
That is the behaviour you want from a human-in-the-loop system: it fails toward
asking rather than toward guessing.

**Caveats worth stating:** n=18 is a small sample; the labels are my own
judgment, and a couple of the misses are genuinely arguable (a prenup sits
between Family and Contract). Field-extraction matching normalizes phone digits
and is lenient on name/jurisdiction phrasing — see `field_match()` in the script.

### Conflict-check results

Recall is the number that matters here: a missed adverse match can disqualify the
firm, while a false positive costs a lawyer ten seconds to dismiss. Test cases are
generated deterministically *from* the seeded history, so ground truth is known
exactly rather than hand-labeled.

```bash
python -m scripts.seed_matter_history   # 100 synthetic past matters (reproducible)
python -m scripts.eval_conflicts        # no LLM calls, no API key needed, free
```

Measured over 159 cases against 100 past matters:

| Metric | Result |
|---|---|
| **Recall on planted conflicts** | **100%** (104/104) |
| — caught as `CONFLICT` rather than `POTENTIAL` | 62.5% (65/104) |
| — by disguise: verbatim / suffix swap / nickname / typo | 100% each |
| **False-positive rate on clear intakes** | **0%** (0/40) |
| Returning clients correctly *not* called a conflict | 100% (15/15) |

Planted conflicts are real past parties reused as the other side of a new intake
in four disguises — verbatim, corporate-suffix swap ("Inc." → "LLC"), nickname
("Robert" → "Bob"), and a single-character typo. All four are caught. The 62.5%
figure is not a miss rate: typo'd names land in `POTENTIAL` rather than
`CONFLICT`, which is the correct response to a genuinely uncertain match — they
still surface to the reviewer.

**Why the 0% false-positive rate is meaningful, and where it's thin.** The clear
cases are built from the same name pools as the history, so surname and word
collisions occur and are deliberately left in — every one of the 40 scores above
0.60 similarity to some real party, and 12 come within 0.10 of the flag
threshold. But the margin is narrow: the closest non-conflict scored 0.783
against a 0.82 threshold. The separation holds on this data; a different name
distribution could produce false positives, and the honest read is "well
separated on 159 cases", not "solved".

## Data model

| Field | Type | Source |
|---|---|---|
| intake_id | string | generated |
| received_at | datetime | generated |
| client_name | string \| null | extracted |
| client_email | string \| null | extracted |
| client_phone | string \| null | extracted |
| opposing_party | string \| null | extracted (drives the conflict screen) |
| conflict | CLEAR \| POTENTIAL \| CONFLICT + matched matters + limitations | screened |
| matter_type | enum (Family, Real Estate, Employment, Wills & Estates, Civil Litigation, Other) | classified |
| matter_type_confidence | enum (high, low) | classified |
| jurisdiction | string \| null | extracted |
| key_dates | string[] | extracted |
| summary | string | extracted |
| missing_fields | string[] | derived |
| status | enum (needs_review, approved) | workflow |
| draft_reply | text | generated |

## Project structure

```
backend/
  app/
    main.py       FastAPI app: /process (read+draft+screen) and /approve (persist)
    llm.py        the only module that talks to the LLM provider
    conflicts.py  the only module that screens against the matter history
    prompts.py    the extraction + no-advice draft system prompts
    schema.py     Pydantic models + the strict JSON output contract
    storage.py    the only module that writes to the CRM (CSV / Airtable)
  samples/
    intakes.json         18 hand-labeled synthetic intakes
    matter_history.json  100 synthetic past matters (generated, reproducible)
  scripts/
    test_process.py         quick 3-intake smoke test
    eval_samples.py         extraction + classification accuracy sweep
    seed_matter_history.py  regenerates the synthetic matter history
    eval_conflicts.py       conflict recall / false-positive sweep
frontend/
  app/page.tsx    the single review page (input | record + draft | approve)
  lib/            api client, shared types, dropdown samples
```

## What is not built yet

The longer-term design is an event-triggered pipeline: an inbound email fires the
run, external sources enrich it, and artifacts (calendar holds, a lawyer brief)
are prepared before the same human gate. What exists today is the intake →
extract → conflict screen → review → approve → CRM loop, driven from the UI.

Not yet built, and honestly blocked on infrastructure rather than design:

| Piece | Status |
|---|---|
| Email trigger (run on inbound mail, not a button) | needs a Gmail/webhook integration + OAuth |
| External enrichment (company registry, court records) | needs n8n/Firecrawl and API credentials |
| Calendar holds + Slack lawyer brief | needs Google Calendar / Slack OAuth |
| Matter history in Postgres rather than a JSON file | `conflicts.py` isolates the loader, so this is a one-module change |
| Run dashboard + full audit log table | the CSV already records conflict status and matched matters per approval |

The conflict screen was built first deliberately: it is the most legally specific
part, it needs no external service, and it is the piece whose failure is most
expensive.

## Honesty checklist

- [x] Runs end to end: intake → extract → review → approve → CRM write.
- [x] Synthetic data, no legal advice, no auto-send — stated above and enforced
      in code.
- [x] Every number in the results table measured by an actual `eval_samples` run
      (2026-07-19), not guessed. Raw output is in `backend/eval_results/`.
- [ ] Public GitHub repo with a recorded `docs/demo.gif`.
