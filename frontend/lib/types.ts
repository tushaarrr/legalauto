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

export type ConflictStatus = "CLEAR" | "POTENTIAL" | "CONFLICT";

// Mirror of the backend's ConflictMatch / ConflictResult (backend/app/schema.py).
export interface ConflictMatch {
  matter_id: string;
  score: number;
  kind: "opposing_party_is_former_client" | "client_is_former_opposing_party";
  reason: string;
  past_client: string;
  past_opposing: string;
  matter_type: string;
}

export interface ConflictResult {
  status: ConflictStatus;
  matches: ConflictMatch[];
  returning_client_matters: string[];
  checked_against: number;
  limitations: string[];
}

export interface CRMRecord {
  client_name: string | null;
  client_email: string | null;
  client_phone: string | null;
  opposing_party: string | null;
  conflict: ConflictResult | null;
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
