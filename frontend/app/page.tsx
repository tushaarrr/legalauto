"use client";

import { useState } from "react";
import { approveIntake, processIntake } from "@/lib/api";
import { SAMPLES } from "@/lib/samples";
import { CRMRecord, MATTER_TYPES, MatterType, SaveResult } from "@/lib/types";

export default function ReviewPage() {
  const [intakeText, setIntakeText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The editable record returned by /process. Held in state so the human can
  // correct any field before approving (requirement #5).
  const [record, setRecord] = useState<CRMRecord | null>(null);

  // The approval gate. `saveResult` is set only after the backend has written
  // the record to the CRM — nothing is persisted until then.
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

  // Generic field updater keeps every input controlled + editable.
  function update<K extends keyof CRMRecord>(key: K, value: CRMRecord[K]) {
    setRecord((r) => (r ? { ...r, [key]: value } : r));
  }

  async function handleApprove() {
    if (!record) return;
    // The approval gate: send the (edited) record to the backend, which flips
    // status to "approved" and writes it to the CRM. Only on success do we show
    // the approved state — nothing is persisted client-side.
    setApproving(true);
    setApproveError(null);
    try {
      const { record: saved, storage } = await approveIntake(record);
      setRecord(saved);
      setSaveResult(storage);
    } catch (e) {
      setApproveError(
        e instanceof Error ? e.message : "Could not save the record.",
      );
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
    <main className="min-h-screen">
      {/* Disclaimer banner — the three promises stated up front. */}
      <div className="bg-slate-900 text-slate-100 text-xs sm:text-sm px-4 py-2 text-center">
        Demo on <span className="font-semibold">synthetic data</span> · the tool{" "}
        <span className="font-semibold">never gives legal advice</span> · replies
        are drafted, <span className="font-semibold">never auto-sent</span>.
      </div>

      <div className="mx-auto max-w-6xl px-4 py-6">
        <header className="mb-6">
          <h1 className="text-2xl font-semibold tracking-tight">
            LegalFlow — Intake Review
          </h1>
          <p className="text-sm text-slate-500">
            Paste a client inquiry (or load a sample), extract the structured
            record, review &amp; edit, then approve.
          </p>
        </header>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* ---------------- LEFT: raw intake input ---------------- */}
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
              Raw intake
            </h2>

            <label className="mb-1 block text-sm font-medium text-slate-700">
              Load a sample
            </label>
            <select
              className="mb-4 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
              defaultValue=""
              onChange={(e) => {
                const s = SAMPLES.find((x) => x.label === e.target.value);
                if (s) setIntakeText(s.text);
              }}
            >
              <option value="" disabled>
                Choose a synthetic sample…
              </option>
              {SAMPLES.map((s) => (
                <option key={s.label} value={s.label}>
                  {s.label}
                </option>
              ))}
            </select>

            <label className="mb-1 block text-sm font-medium text-slate-700">
              Intake text
            </label>
            <textarea
              className="h-64 w-full resize-y rounded-lg border border-slate-300 px-3 py-2 text-sm leading-relaxed focus:border-slate-500 focus:outline-none"
              placeholder="Paste the client's email or contact-form message here…"
              value={intakeText}
              onChange={(e) => setIntakeText(e.target.value)}
            />

            <button
              onClick={handleProcess}
              disabled={loading || !intakeText.trim()}
              className="mt-4 w-full rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? "Processing…" : "Process"}
            </button>

            {error && (
              <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </p>
            )}
          </section>

          {/* ---------------- RIGHT: extracted record ---------------- */}
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
              Extracted record
            </h2>

            {!record ? (
              <p className="text-sm text-slate-400">
                Process an intake to see the structured record and draft reply.
              </p>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <TextField
                    label="Client name"
                    value={record.client_name}
                    onChange={(v) => update("client_name", v)}
                  />
                  <TextField
                    label="Email"
                    value={record.client_email}
                    onChange={(v) => update("client_email", v)}
                  />
                  <TextField
                    label="Phone"
                    value={record.client_phone}
                    onChange={(v) => update("client_phone", v)}
                  />
                  <TextField
                    label="Jurisdiction"
                    value={record.jurisdiction}
                    onChange={(v) => update("jurisdiction", v)}
                  />
                </div>

                {/* Matter type + confidence, with the low-confidence warning. */}
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">
                    Matter type
                  </label>
                  <div className="flex items-center gap-2">
                    <select
                      className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
                      value={record.matter_type}
                      onChange={(e) =>
                        update("matter_type", e.target.value as MatterType)
                      }
                    >
                      {MATTER_TYPES.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                    <select
                      className="rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm focus:border-slate-500 focus:outline-none"
                      value={record.matter_type_confidence}
                      onChange={(e) =>
                        update(
                          "matter_type_confidence",
                          e.target.value as "high" | "low",
                        )
                      }
                      title="Model confidence in the classification"
                    >
                      <option value="high">high confidence</option>
                      <option value="low">low confidence</option>
                    </select>
                  </div>
                  {lowConfidence && (
                    <p className="mt-2 flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
                      <span aria-hidden>⚠️</span>
                      <span>
                        Low-confidence classification — the model was unsure.
                        Please verify the matter type before approving.
                      </span>
                    </p>
                  )}
                </div>

                {/* Key dates — editable, one per line. */}
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">
                    Key dates{" "}
                    <span className="font-normal text-slate-400">
                      (one per line)
                    </span>
                  </label>
                  <textarea
                    className="h-16 w-full resize-y rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
                    value={record.key_dates.join("\n")}
                    onChange={(e) =>
                      update(
                        "key_dates",
                        e.target.value
                          .split("\n")
                          .map((s) => s.trim())
                          .filter(Boolean),
                      )
                    }
                  />
                </div>

                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">
                    Summary
                  </label>
                  <textarea
                    className="h-16 w-full resize-y rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
                    value={record.summary}
                    onChange={(e) => update("summary", e.target.value)}
                  />
                </div>

                {/* Missing fields — removable chips (edit before approving). */}
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">
                    Missing fields
                  </label>
                  {record.missing_fields.length === 0 ? (
                    <p className="text-sm text-slate-400">
                      None — all key details were provided.
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {record.missing_fields.map((f) => (
                        <span
                          key={f}
                          className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-800"
                        >
                          {f}
                          <button
                            aria-label={`Remove ${f}`}
                            className="text-amber-600 hover:text-amber-900"
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

                {/* Draft reply — editable. */}
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">
                    Draft reply{" "}
                    <span className="font-normal text-slate-400">
                      (logistics only — no legal advice)
                    </span>
                  </label>
                  <textarea
                    className="h-40 w-full resize-y rounded-lg border border-slate-300 px-3 py-2 text-sm leading-relaxed focus:border-slate-500 focus:outline-none"
                    value={record.draft_reply}
                    onChange={(e) => update("draft_reply", e.target.value)}
                  />
                </div>

                {/* Approval gate. */}
                {approved && saveResult ? (
                  <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
                    <p className="text-sm font-semibold text-emerald-800">
                      ✓ {saveResult.already_saved ? "Already saved" : "Approved & saved"}
                    </p>
                    <p className="mt-1 text-sm text-emerald-700">
                      Record{" "}
                      <span className="font-mono">{record.intake_id}</span> was
                      written to the{" "}
                      <span className="font-semibold">{saveResult.backend}</span>{" "}
                      CRM.
                    </p>
                    <p className="mt-1 break-all text-xs text-emerald-600">
                      {saveResult.backend === "airtable"
                        ? `Airtable ${saveResult.location}` +
                          (saveResult.external_ref
                            ? ` · ${saveResult.external_ref}`
                            : "")
                        : saveResult.location}
                    </p>
                    <button
                      onClick={copyReply}
                      className="mt-3 rounded-lg border border-emerald-300 bg-white px-4 py-2 text-sm font-semibold text-emerald-800 transition hover:bg-emerald-100"
                    >
                      {copied ? "Copied!" : "Copy reply"}
                    </button>
                    {/* Deliberately NO send button — replies are never auto-sent. */}
                  </div>
                ) : (
                  <div>
                    <button
                      onClick={handleApprove}
                      disabled={approving}
                      className="w-full rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {approving ? "Saving…" : "Approve & Save"}
                    </button>
                    {approveError && (
                      <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
                        {approveError}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}

// Small controlled text input that treats "" as null so cleared fields map back
// to the record's nullable shape.
function TextField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string | null;
  onChange: (v: string | null) => void;
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
        value={value ?? ""}
        placeholder="—"
        onChange={(e) => onChange(e.target.value === "" ? null : e.target.value)}
      />
    </div>
  );
}
