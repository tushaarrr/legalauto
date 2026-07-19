# Build Prompt — paste into Cursor / Claude Code

You are helping me build a small, working full-stack project called **LegalFlow**. Build it incrementally, run it, and stop for me to check after each phase. Do not scaffold everything at once.

## What we're building
An approval-first legal intake automation. Raw client inquiry text goes in, an LLM extracts structured fields and drafts a confirmation reply, a human reviews and approves, then the record is saved to a CRM (Airtable or Google Sheets) and the reply is marked ready to send. Nothing is ever auto-sent, and no legal advice is ever generated.

## Stack
- Frontend: Next.js (App Router) + TypeScript + Tailwind. Single review page.
- Backend: Python FastAPI, one main endpoint `/process` that takes raw intake text and returns structured JSON + a draft reply.
- LLM: Anthropic API (claude). Use strict JSON output. If provider needs to change, keep the LLM call isolated in one module.
- Storage: Airtable API (preferred) or Google Sheets API as the "CRM". Keep storage isolated in one module so it can be swapped.

## Hard requirements
1. **Strict structured output.** The LLM returns JSON matching this schema exactly. Parse it; on failure, retry once with a stricter instruction, then surface an error.
   ```
   {
     "client_name": string | null,
     "client_email": string | null,
     "client_phone": string | null,
     "matter_type": one of ["Family","Real Estate","Employment","Wills & Estates","Civil Litigation","Other"],
     "jurisdiction": string | null,
     "key_dates": string[],
     "summary": string,
     "missing_fields": string[],
     "matter_type_confidence": "high" | "low"
   }
   ```
2. **No hallucinated values.** If a field is not present in the intake, it must be `null` and its name added to `missing_fields`. Never invent a name, email, or date.
3. **No legal advice.** The drafted reply must only: thank the client, confirm what was received, and request the missing fields. A system-prompt rule must forbid any legal opinion, recommendation, or advice. If the intake asks for legal advice, the draft politely says a lawyer will follow up.
4. **Approval gate.** The record is NOT written to storage until the user clicks Approve. Before approval, status is `needs_review`. After, `approved`.
5. **Human edits allowed.** The user can edit any extracted field and the draft before approving.

## LLM system prompt to use (embed this)
```
You are an intake-processing assistant for a law firm's back office. You organize client inquiries and draft logistical replies. You do NOT give legal advice, opinions, or recommendations of any kind.

Given a raw client intake, extract the requested fields as strict JSON. Rules:
- If a field is not clearly stated in the intake, set it to null and add its name to missing_fields. Never guess or invent values.
- Classify matter_type into the fixed list only. If unsure, use "Other" and set matter_type_confidence to "low".
- summary is one neutral sentence describing what the client wants, with no legal characterization.
- Output valid JSON only, no prose, no markdown fences.
```
Then a second call (or same call) drafts the reply from the structured record, under the same no-advice rule.

## UI
One page, two columns:
- Left: a textarea for raw intake + a dropdown of 5 synthetic sample intakes to load + a "Process" button.
- Right: the extracted fields (editable), matter_type with a visible low-confidence warning when applicable, the missing_fields list, and the editable draft reply. An "Approve & Save" button at the bottom.
- After approval: show a success state, the saved record id, and a "Copy reply" button. No send button.

## Build phases (stop after each)
**Phase 1:** FastAPI `/process` endpoint + the LLM extraction and draft, returning JSON. Test it from the terminal with 2-3 pasted intakes before any UI. Show me the raw JSON output.

**Phase 2:** Next.js review page wired to `/process`. Editable fields, draft, no storage yet.

**Phase 3:** Approval gate + Airtable/Sheets write. Status transitions. Copy-reply button.

**Phase 4:** A `samples/` folder with 15-20 synthetic intakes (varied matter types, some deliberately missing fields, some ambiguous). A small script that runs all of them and prints extraction + classification results so I can hand-check accuracy.

## Also generate
- A README with: what it is, the synthetic-data / no-advice / no-auto-send disclaimers stated up front, setup steps, and a place for a demo GIF.
- A `.env.example` (never commit real keys).
- Clear comments on the approval gate and the no-advice guardrail, since those are the two design decisions I want to talk about.

Start with Phase 1. Build it, run it, show me the output, then wait.
