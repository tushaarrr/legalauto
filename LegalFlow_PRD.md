# LegalFlow — Client Intake to CRM Automation

**One-line:** An approval-first automation that turns a raw client intake (email or form) into a structured CRM record and a ready-to-send confirmation reply, with a human in the loop before anything goes out.

**Why this exists (for the Clio application):** Clio's Workflow Consultant role is about configuring software to translate messy client workflows into clean, efficient ones, with AI assisting legal work responsibly. This project is a small, working proof of that exact loop: intake comes in, AI structures it, a human approves, the record and reply are created. It demonstrates workflow design, AI-assisted drafting, CRM configuration thinking, and the "human always reviews AI output" principle Clio explicitly states it follows.

---

## 1. Problem

Small law firms receive new client inquiries as unstructured text: an email, a contact-form submission, a voicemail transcript. Someone reads each one, figures out the matter type, copies details into a case-management system, checks for conflicts, and drafts a reply asking for missing information. This is slow, inconsistent, and easy to get wrong under volume.

## 2. Goal

Automate the tedious middle of that process while keeping a human in control of anything that leaves the building.

**In scope:**
- Ingest a raw intake (paste text, or a simple form)
- Extract structured fields with an LLM
- Flag missing or ambiguous information
- Classify the matter type
- Create a structured record (Airtable or Google Sheets as the stand-in CRM)
- Draft a confirmation / follow-up reply
- Require explicit human approval before the record is saved and the reply is marked ready

**Explicitly out of scope (say this openly, it shows judgment):**
- No legal advice is generated. The tool organizes and drafts logistics only.
- No auto-send. Every outbound reply is drafted, never sent automatically.
- No real client data. Demo runs on synthetic intakes only.

## 3. Users

- **Primary:** a legal assistant or small-firm operator processing new inquiries.
- **Secondary (the real audience):** a Clio interviewer looking at the repo.

## 4. Core user flow

1. User pastes an intake (or picks a synthetic sample from a dropdown).
2. System extracts: client name, contact info, matter type, jurisdiction, key dates, a one-line summary, and a list of missing fields.
3. System classifies matter type into a fixed taxonomy (e.g. Family, Real Estate, Employment, Wills & Estates, Civil Litigation, Other).
4. System drafts a confirmation reply: thanks the client, confirms what was received, and asks for the flagged missing items.
5. **Approval gate:** the user sees the structured record and the draft side by side, edits anything, then clicks Approve.
6. On approve: record is written to the CRM sheet, and the draft is marked "ready to send" (copy button, no auto-send).

## 5. Data model (the CRM record)

| Field | Type | Source |
|---|---|---|
| intake_id | string | generated |
| received_at | datetime | generated |
| client_name | string | extracted |
| client_email | string | extracted |
| client_phone | string | extracted |
| matter_type | enum | classified |
| jurisdiction | string | extracted |
| key_dates | list | extracted |
| summary | string | extracted |
| missing_fields | list | derived |
| status | enum (needs_review, approved) | workflow |
| draft_reply | text | generated |

## 6. Architecture

Two ways to build it. Pick based on what you want to show.

**Option A — Full-stack app (recommended for the portfolio):**
- Frontend: Next.js + TypeScript. One page: input on the left, extracted record + draft on the right, an Approve button.
- Backend: Python (FastAPI) endpoint that takes raw text, calls the LLM, returns structured JSON + draft.
- Storage: Airtable API or Google Sheets API as the CRM.
- LLM: your existing stack (Claude/OpenAI) with a strict JSON-output prompt.

**Option B — n8n workflow (faster, shows automation-tool fluency):**
- Trigger: webhook or Gmail node.
- LLM node: extract + classify + draft.
- Airtable/Sheets node: create record.
- Manual approval: n8n's "Wait for approval" or a simple review step.
- This maps directly to the Clio bonus line about building automation with Slack workflows / scripting.

**Best for standing out:** build Option B as the working automation, and put a thin Next.js review UI on top for the approval gate. That shows both the automation fluency and the "human reviews AI" product instinct.

## 7. The AI layer (what makes it not fragile)

- **Strict structured output:** the LLM must return valid JSON matching the data model. Reject and retry on parse failure.
- **Missing-field detection:** don't hallucinate values. If a field isn't in the intake, it goes to `missing_fields`, not filled with a guess.
- **Confidence / ambiguity flags:** if matter_type is unclear, mark it and surface it to the human rather than committing.
- **No advice guardrail:** a system-prompt rule that the draft never contains legal opinions or advice, only logistics and requests for information.

## 8. What to measure (gives you numbers for the resume)

Run it on 15-20 synthetic intakes and record:
- Field extraction accuracy (how often each field is correctly pulled)
- Matter-type classification accuracy vs. your hand-labels
- Time from raw intake to approved record (vs. a manual baseline you time yourself)
- % of intakes where missing fields were correctly flagged

These give honest, defensible numbers. Do not invent them; measure them.

## 9. Build phases

- **Phase 1 (core, ~1 day):** intake text → LLM → structured JSON + draft, shown in a UI. No storage yet.
- **Phase 2 (~half day):** approval gate + write to Airtable/Sheets.
- **Phase 3 (optional, later):** court-form PDF auto-fill from the approved record. This is the harder, most Clio-relevant extension.

## 10. Honesty checklist (before it goes on the resume)

- [ ] It actually runs end to end.
- [ ] It's on public GitHub with a README and a short demo GIF.
- [ ] Every number on the resume was measured, not guessed.
- [ ] The README states clearly: synthetic data, no legal advice, no auto-send.
- [ ] You can demo it live in an interview and explain every design choice.
