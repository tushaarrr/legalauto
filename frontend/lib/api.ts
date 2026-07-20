import type { ApproveResponse, CRMRecord, ProcessResponse, Stats } from "./types";

// The FastAPI backend. Override via NEXT_PUBLIC_API_BASE_URL in .env.local if you
// run uvicorn on a non-default port (e.g. http://localhost:8010).
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function postJSON<T>(path: string, payload: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    // FastAPI returns { detail: string } on HTTPException.
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* non-JSON error body; keep the generic message */
    }
    throw new Error(detail);
  }

  return res.json();
}

export function processIntake(text: string): Promise<ProcessResponse> {
  return postJSON<ProcessResponse>("/process", { text });
}

// The approval gate: sends the (edited) record to the backend, which flips
// status to "approved" and writes it to the CRM. Nothing is persisted until this
// is called.
export function approveIntake(record: CRMRecord): Promise<ApproveResponse> {
  return postJSON<ApproveResponse>("/approve", record);
}

// Dashboard aggregates, computed from approved records only.
export async function fetchStats(): Promise<Stats> {
  const res = await fetch(`${API_BASE}/stats`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Could not load stats (${res.status})`);
  return res.json();
}
