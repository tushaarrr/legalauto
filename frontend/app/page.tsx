"use client";

import { useState } from "react";
import { approveIntake, processIntake } from "@/lib/api";
import { SAMPLES } from "@/lib/samples";
import {
  ConflictResult,
  CRMRecord,
  MATTER_TYPES,
  MatterType,
  SaveResult,
} from "@/lib/types";
import { Card, EmptyState } from "@/components/charts";
import {
  AlertTriangle,
  Check,
  Copy,
  OctagonAlert,
  ShieldAlert,
  ShieldCheck,
} from "@/components/icons";

export default function ReviewPage() {
  const [intakeText, setIntakeText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The editable record from /process. Held in state so the reviewer can correct
  // any field before approving.
  const [record, setRecord] = useState<CRMRecord | null>(null);

  // The approval gate. `saveResult` is set only after the backend has written to
  // the CRM — nothing is persisted before that.
  const [approving, setApproving] = useState(false);
  const [saveResult, setSaveResult] = useState<SaveResult | null>(null);
  const [approveError, setApproveError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const approved = saveResult !== null;

  async function handleProcess() {
    if (!intakeText.trim()) return;
    setLoading(true);
    setError(null);
    setSaveResult(null);
    setApproveError(null);
    setRecord(null);
    try {
      const { record } = await processIntake(intakeText);
      setRecord(record);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  function update<K extends keyof CRMRecord>(key: K, value: CRMRecord[K]) {
    setRecord((r) => (r ? { ...r, [key]: value } : r));
  }

  async function handleApprove() {
    if (!record) return;
    setApproving(true);
    setApproveError(null);
    try {
      const { record: saved, storage } = await approveIntake(record);
      setRecord(saved);
      setSaveResult(storage);
    } catch (e) {
      setApproveError(e instanceof Error ? e.message : "Could not save the record.");
    } finally {
      setApproving(false);
    }
  }

  async function copyReply() {
    if (!record) return;
    await navigator.clipboard.writeText(record.draft_reply);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const lowConfidence = record?.matter_type_confidence === "low";

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      <div className="mb-5">
        <h1 className="font-display text-[26px] font-bold tracking-tight text-heading">
          Intake review
        </h1>
        <p className="mt-1 text-sm text-ink-secondary">
          Paste a client inquiry, review what was extracted and screened, then approve.
          Nothing is saved or sent until you do.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        {/* ---------------- LEFT: raw intake ---------------- */}
        <div className="lg:sticky lg:top-20 lg:self-start">
          <Card title="Raw intake" subtitle="Paste an inquiry or load a synthetic sample">
            <label
              htmlFor="sample"
              className="mb-1.5 block text-sm font-medium text-ink-secondary"
            >
              Sample intake
            </label>
            <select
              id="sample"
              className="mb-4 w-full cursor-pointer rounded-lg border border-line bg-surface px-3 py-2.5 text-sm text-ink-primary transition-colors duration-200 hover:border-line-strong"
              defaultValue=""
              onChange={(e) => {
                const s = SAMPLES.find((x) => x.label === e.target.value);
                if (s) setIntakeText(s.text);
              }}
            >
              <option value="" disabled>
                Choose a sample…
              </option>
              {SAMPLES.map((s) => (
                <option key={s.label} value={s.label}>
                  {s.label}
                </option>
              ))}
            </select>

            <label
              htmlFor="intake"
              className="mb-1.5 block text-sm font-medium text-ink-secondary"
            >
              Intake text
            </label>
            <textarea
              id="intake"
              className="h-56 w-full resize-y rounded-lg border border-line bg-surface px-3 py-2.5 text-sm leading-relaxed text-ink-primary transition-colors duration-200 placeholder:text-ink-muted hover:border-line-strong"
              placeholder="Paste the client's email or contact-form message here…"
              value={intakeText}
              onChange={(e) => setIntakeText(e.target.value)}
            />

            <button
              onClick={handleProcess}
              disabled={loading || !intakeText.trim()}
              className="mt-4 inline-flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-on-brand transition-colors duration-200 hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading && (
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-on-brand/30 border-t-on-brand" />
              )}
              {loading ? "Processing…" : "Process intake"}
            </button>

            {error && (
              <p
                role="alert"
                className="mt-3 flex items-start gap-2 rounded-lg bg-crit-bg px-3 py-2 text-sm text-crit"
              >
                <AlertTriangle className="mt-0.5 h-4 w-4" />
                {error}
              </p>
            )}
          </Card>
        </div>

        {/* ---------------- RIGHT: extracted record ---------------- */}
        <div className="space-y-4">
          {!record ? (
            <Card title="Extracted record">
              <EmptyState>
                Process an intake to see the structured record, the conflict screen, and
                the draft reply.
              </EmptyState>
            </Card>
          ) : (
            <>
              <ConflictBanner conflict={record.conflict} />

              <Card title="Extracted record" subtitle="Every field is editable before approval">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <Field label="Client name" value={record.client_name} onChange={(v) => update("client_name", v)} />
                  <Field label="Email" type="email" value={record.client_email} onChange={(v) => update("client_email", v)} />
                  <Field label="Phone" type="tel" value={record.client_phone} onChange={(v) => update("client_phone", v)} />
                  <Field label="Jurisdiction" value={record.jurisdiction} onChange={(v) => update("jurisdiction", v)} />
                  <div className="sm:col-span-2">
                    <Field
                      label="Opposing party"
                      value={record.opposing_party}
                      onChange={(v) => update("opposing_party", v)}
                      help="Drives the conflict screen"
                    />
                  </div>
                </div>

                <div className="mt-4">
                  <label htmlFor="matter" className="mb-1.5 block text-sm font-medium text-ink-secondary">
                    Matter type
                  </label>
                  <div className="flex flex-wrap items-center gap-2">
                    <select
                      id="matter"
                      className="min-w-0 flex-1 cursor-pointer rounded-lg border border-line bg-surface px-3 py-2.5 text-sm text-ink-primary transition-colors duration-200 hover:border-line-strong"
                      value={record.matter_type}
                      onChange={(e) => update("matter_type", e.target.value as MatterType)}
                    >
                      {MATTER_TYPES.map((m) => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>
                    <select
                      className="cursor-pointer rounded-lg border border-line bg-surface px-3 py-2.5 text-sm text-ink-secondary transition-colors duration-200 hover:border-line-strong"
                      value={record.matter_type_confidence}
                      onChange={(e) =>
                        update("matter_type_confidence", e.target.value as "high" | "low")
                      }
                      aria-label="Model confidence in the classification"
                    >
                      <option value="high">high confidence</option>
                      <option value="low">low confidence</option>
                    </select>
                  </div>
                  {lowConfidence && (
                    <p className="mt-2 flex items-start gap-2 rounded-lg bg-warn-bg px-3 py-2 text-sm text-warn">
                      <AlertTriangle className="mt-0.5 h-4 w-4" />
                      <span>
                        The model was unsure of this classification. Verify the matter type
                        before approving.
                      </span>
                    </p>
                  )}
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div>
                    <label htmlFor="dates" className="mb-1.5 block text-sm font-medium text-ink-secondary">
                      Key dates <span className="font-normal text-ink-muted">(one per line)</span>
                    </label>
                    <textarea
                      id="dates"
                      className="h-20 w-full resize-y rounded-lg border border-line bg-surface px-3 py-2.5 text-sm text-ink-primary transition-colors duration-200 hover:border-line-strong"
                      value={record.key_dates.join("\n")}
                      onChange={(e) =>
                        update(
                          "key_dates",
                          e.target.value.split("\n").map((s) => s.trim()).filter(Boolean),
                        )
                      }
                    />
                  </div>
                  <div>
                    <label htmlFor="summary" className="mb-1.5 block text-sm font-medium text-ink-secondary">
                      Summary
                    </label>
                    <textarea
                      id="summary"
                      className="h-20 w-full resize-y rounded-lg border border-line bg-surface px-3 py-2.5 text-sm text-ink-primary transition-colors duration-200 hover:border-line-strong"
                      value={record.summary}
                      onChange={(e) => update("summary", e.target.value)}
                    />
                  </div>
                </div>

                <div className="mt-4">
                  <span className="mb-1.5 block text-sm font-medium text-ink-secondary">
                    Missing fields
                  </span>
                  {record.missing_fields.length === 0 ? (
                    <p className="text-sm text-ink-muted">
                      None — all key details were provided.
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {record.missing_fields.map((f) => (
                        <span
                          key={f}
                          className="inline-flex items-center gap-1.5 rounded-full border border-warn/30 bg-warn-bg px-2.5 py-1 text-xs font-medium text-warn"
                        >
                          {f}
                          <button
                            aria-label={`Remove ${f} from missing fields`}
                            className="cursor-pointer rounded-full leading-none opacity-70 transition-opacity duration-150 hover:opacity-100"
                            onClick={() =>
                              update(
                                "missing_fields",
                                record.missing_fields.filter((x) => x !== f),
                              )
                            }
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </Card>

              <Card
                title="Draft reply"
                subtitle="Logistics only — the drafter is barred from giving legal advice"
              >
                <textarea
                  aria-label="Draft reply"
                  className="h-44 w-full resize-y rounded-lg border border-line bg-surface px-3 py-2.5 text-sm leading-relaxed text-ink-primary transition-colors duration-200 hover:border-line-strong"
                  value={record.draft_reply}
                  onChange={(e) => update("draft_reply", e.target.value)}
                />

                {approved && saveResult ? (
                  <div className="mt-4 rounded-lg border border-good/30 bg-good-bg p-4">
                    <p className="flex items-center gap-2 text-sm font-semibold text-good">
                      <ShieldCheck />
                      {saveResult.already_saved ? "Already saved" : "Approved & saved"}
                    </p>
                    <p className="mt-1 text-sm text-ink-secondary">
                      <span className="tnum">{record.intake_id}</span> written to the{" "}
                      <span className="font-medium">{saveResult.backend}</span> CRM.
                    </p>
                    <button
                      onClick={copyReply}
                      className="mt-3 inline-flex cursor-pointer items-center gap-2 rounded-lg border border-line bg-surface px-4 py-2 text-sm font-semibold text-ink-primary transition-colors duration-200 hover:bg-surface-2"
                    >
                      {copied ? <Check /> : <Copy />}
                      {copied ? "Copied" : "Copy reply"}
                    </button>
                    {/* No send button by design — replies are never auto-sent. */}
                  </div>
                ) : (
                  <div className="mt-4">
                    <button
                      onClick={handleApprove}
                      disabled={approving}
                      className="inline-flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-on-brand transition-colors duration-200 hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {approving && (
                        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-on-brand/30 border-t-on-brand" />
                      )}
                      {approving ? "Saving…" : "Approve & save to CRM"}
                    </button>
                    {approveError && (
                      <p
                        role="alert"
                        className="mt-3 flex items-start gap-2 rounded-lg bg-crit-bg px-3 py-2 text-sm text-crit"
                      >
                        <AlertTriangle className="mt-0.5 h-4 w-4" />
                        {approveError}
                      </p>
                    )}
                  </div>
                )}
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/*
  The conflict screen result. Deliberately the loudest element on the page: a
  conflict can bar the firm from taking the client at all, so it outranks every
  other field. The matched matters are listed because a verdict a lawyer can't
  inspect is a verdict they can't overrule.
*/
function ConflictBanner({ conflict }: { conflict: ConflictResult | null }) {
  if (!conflict) return null;

  const style = {
    CONFLICT: {
      wrap: "border-crit/40 bg-crit-bg",
      text: "text-crit",
      Icon: OctagonAlert,
      label: "Conflict of interest — do not accept without review",
    },
    POTENTIAL: {
      wrap: "border-warn/40 bg-warn-bg",
      text: "text-warn",
      Icon: ShieldAlert,
      label: "Potential conflict — needs a human decision",
    },
    CLEAR: {
      wrap: "border-good/30 bg-good-bg",
      text: "text-good",
      Icon: ShieldCheck,
      label: "No conflict found",
    },
  }[conflict.status];

  const { Icon } = style;

  return (
    <section className={`rounded-xl border p-4 ${style.wrap}`} aria-live="polite">
      <div className="flex items-start gap-2.5">
        <Icon className={`mt-0.5 h-4 w-4 ${style.text}`} />
        <div className="min-w-0 flex-1">
          <p className={`text-sm font-semibold ${style.text}`}>{style.label}</p>
          <p className="mt-0.5 text-xs text-ink-secondary">
            Screened against{" "}
            <span className="tnum">{conflict.checked_against}</span> past matters
          </p>

          {conflict.matches.length > 0 && (
            <ul className="mt-2.5 space-y-1.5">
              {conflict.matches.map((m) => (
                <li
                  key={`${m.matter_id}-${m.kind}`}
                  className="flex gap-2 text-sm text-ink-primary"
                >
                  {/* self-start: without it this stretches to the full height
                      of a wrapped reason line and reads as a tall empty box. */}
                  <span className="tnum mt-0.5 shrink-0 self-start rounded bg-surface px-1.5 py-0.5 text-xs text-ink-secondary">
                    {m.score.toFixed(2)}
                  </span>
                  <span className="leading-relaxed">{m.reason}</span>
                </li>
              ))}
            </ul>
          )}

          {conflict.returning_client_matters.length > 0 && (
            <p className="mt-2 text-sm text-ink-secondary">
              Returning client — previously acted for them in{" "}
              <span className="tnum">{conflict.returning_client_matters.join(", ")}</span>. Not
              a conflict.
            </p>
          )}

          {/* A CLEAR result that could only see one side is not really clear. */}
          {conflict.limitations.map((l) => (
            <p
              key={l}
              className="mt-2 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs leading-relaxed text-ink-secondary"
            >
              <span className="font-semibold text-ink-primary">Limitation: </span>
              {l}
            </p>
          ))}
        </div>
      </div>
    </section>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  help,
}: {
  label: string;
  value: string | null;
  onChange: (v: string | null) => void;
  type?: string;
  help?: string;
}) {
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-ink-secondary">
        {label}
      </label>
      <input
        id={id}
        type={type}
        className="w-full rounded-lg border border-line bg-surface px-3 py-2.5 text-sm text-ink-primary transition-colors duration-200 placeholder:text-ink-muted hover:border-line-strong"
        value={value ?? ""}
        placeholder="Not provided"
        onChange={(e) => onChange(e.target.value === "" ? null : e.target.value)}
      />
      {help && <p className="mt-1 text-xs text-ink-muted">{help}</p>}
    </div>
  );
}
