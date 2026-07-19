// Mirror of the backend's CRMRecord (see backend/app/schema.py). Keeping this in
// one place means the review page edits a single, well-typed shape.

export const MATTER_TYPES = [
  "Family",
  "Real Estate",
  "Employment",
  "Wills & Estates",
  "Civil Litigation",
  "Other",
] as const;

export type MatterType = (typeof MATTER_TYPES)[number];
export type Confidence = "high" | "low";
export type Status = "needs_review" | "approved";

export interface CRMRecord {
  client_name: string | null;
  client_email: string | null;
  client_phone: string | null;
  matter_type: MatterType;
  jurisdiction: string | null;
  key_dates: string[];
  summary: string;
  missing_fields: string[];
  matter_type_confidence: Confidence;
  intake_id: string;
  received_at: string;
  status: Status;
  draft_reply: string;
}

export interface ProcessResponse {
  record: CRMRecord;
}

// Mirror of the backend's SaveResult (see backend/app/schema.py) — where an
// approved record landed in the CRM.
export interface SaveResult {
  backend: "csv" | "airtable";
  location: string;
  record_id: string;
  approved_at: string;
  external_ref: string | null;
  already_saved: boolean;
}

export interface ApproveResponse {
  record: CRMRecord;
  storage: SaveResult;
}
