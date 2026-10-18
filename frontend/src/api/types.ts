// Mirrors the backend's API schemas (backend/covora/api, covora/icp/schemas.py).

export type Origin = "stated" | "inferred";

export interface Tagged<T> {
  value: T;
  origin: Origin;
}

export interface Range {
  min: number | null;
  max: number | null;
}

export interface Location {
  country: string;
  regions: string[];
}

export interface SizeBand {
  employees: Range;
  primary_titles: string[];
  secondary_titles: string[];
  origin: Origin;
}

export interface BuyerMap {
  target_functions: Tagged<string>[];
  by_company_size: SizeBand[];
  skip_titles: Tagged<string>[];
}

export interface StructuredICP {
  summary: string;
  industries: Tagged<string>[];
  locations: Tagged<Location>[];
  employee_range: Tagged<Range> | null;
  revenue_range_usd: Tagged<Range> | null;
  other_criteria: Tagged<string>[];
  exclusions: Tagged<string>[];
  buyer_map: BuyerMap;
  assumptions: string[];
  search_queries: string[];
}

export type OfferingType = "sales_call" | "dealer";

export interface WorkspaceProfile {
  name: string;
  website: string | null;
  description: string | null;
  value_props: string[];
  offering_type: OfferingType;
}

export interface WorkspaceOut extends WorkspaceProfile {
  id: string;
}

export interface IcpVersionOut {
  id: string;
  version: number;
  prompt_text: string;
  structured: StructuredICP;
  parent_id: string | null;
  created_by: "user" | "agent";
  created_at: string;
}

export interface WorkingMemoryManifestItem {
  id: string;
  kind: string;
  subtype: string;
  reason: string;
  rank: number;
  score: number;
}

export interface ParseResponse {
  draft: StructuredICP;
  run_id: string;
  working_memory: WorkingMemoryManifestItem[];
}

export type RunStatus = "running" | "succeeded" | "failed";

export interface RunSummary {
  id: string;
  kind: string;
  status: RunStatus;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  error: string | null;
  llm_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  est_cost_usd: number | null;
}

export interface SpanOut {
  id: string;
  parent_span_id: string | null;
  name: string;
  kind: string;
  status: "running" | "ok" | "error";
  started_at: string;
  duration_ms: number | null;
  attributes: Record<string, unknown>;
  error: string | null;
}

export interface LlmCallOut {
  id: string;
  span_id: string;
  task: string;
  routing_mode: string;
  requested_model: string;
  actual_model: string;
  routing_reason: string;
  fallback_used: boolean;
  fallback_reason: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  latency_ms: number;
  est_cost_usd: number | null;
  output_valid: boolean;
  retries: number;
  response_text?: string | null;
  created_at: string;
}

export interface RunDetail {
  run: RunSummary;
  spans: SpanOut[];
  llm_calls: LlmCallOut[];
}

export interface WorkingMemoryItem {
  memory_item_id: string;
  kind: string;
  subtype: string;
  source: string;
  summary: string;
  evidence_level: string | null;
  reason: string;
  rank: number;
}

export type GoalType = "positive_replies" | "meetings";

export interface Goals {
  goal_type: GoalType;
  target: number;
  expected_positive_rate: number;
  meetings_per_positive: number;
}

export interface SendingSettings {
  daily_gmail_cap: number;
  first_batch_size: number;
  no_reply_window_minutes: number;
}

export interface SimulationSettings {
  profile: "realistic" | "accelerated";
  reply_delay_seconds: [number, number];
  seed: number;
}

export interface WorkspaceSettings {
  goals: Goals;
  sending: SendingSettings;
  simulation?: SimulationSettings;
}

export interface SizingEstimate {
  rate_used: number;
  prospects_needed: number;
  prospects_planned: number;
  companies_needed: number;
  est_searches: number;
  est_pages: number;
  est_youcom_usd: number;
  est_model_calls: number;
  gmail_emails: number;
  in_app_emails: number;
  budget_remaining_usd: number;
  fits_budget: boolean;
  max_affordable_prospects: number;
  cost_model_source: "default" | "measured";
}

export type CampaignStatus =
  | "draft"
  | "queued"
  | "running"
  | "awaiting_approval"
  | "sending"
  | "complete"
  | "failed";

export interface Funnel {
  candidates: number;
  qualified: number;
  rejected: number;
  needs_review: number;
  with_contacts: number;
  prospects: number;
  no_contact: number;
}

export interface CampaignOut {
  id: string;
  name: string;
  status: CampaignStatus;
  icp_version_id: string;
  goal: Goals;
  target_prospects: number;
  progress: {
    used_queries: string[];
    waves: number;
    stop_reason: string | null;
  };
  last_error: string | null;
  created_at: string;
  funnel: Funnel;
  latest_run_id: string | null;
  arms?: {
    key: string;
    template_id: string;
    template_name: string;
    length: string;
    cta: string;
  }[];
}

export type EvidenceLabel = "verified" | "unverified" | "unknown";
export type CriterionStatus = "met" | "not_met" | "unknown";

export interface CompanyRow {
  company_id: string;
  name: string;
  domain: string;
  status: string;
  fit_score: number | null;
  confidence: string | null;
  reason: string | null;
  wave: number;
  criteria: { name: string; status: CriterionStatus; fact_ids: string[] }[];
  synthetic: boolean;
  facts_summary: Record<string, string>;
}

export interface ContactOut {
  id: string;
  full_name: string;
  title: string;
  function: string;
  seniority: string;
  email: string | null;
  email_status: "verified" | "unverified" | "missing";
  linkedin_url: string | null;
  source_urls: string[];
  synthetic: boolean;
}

export interface ProspectRow {
  prospect_id: string;
  short_id: string;
  role: "primary" | "backup";
  status: string;
  confidence: string;
  pick_reason: string;
  company: { id: string; name: string; domain: string };
  contact: ContactOut;
  synthetic: boolean;
}

export interface FactOut {
  field: string;
  value: unknown;
  label: EvidenceLabel;
  source_url: string;
  quote: string;
  retrieved_at: string;
}

export interface CompanyDetail {
  company: { id: string; name: string; domain: string; synthetic: boolean };
  facts: FactOut[];
  contacts: ContactOut[];
  campaigns: {
    campaign_id: string;
    status: string;
    fit_score: number | null;
    reason: string | null;
  }[];
}

export interface ReviewDraft {
  id: string;
  prospect_id: string;
  arm_key: string | null;
  kind: string;
  status: string;
  subject: string;
  body: string;
  problems: string[];
  intended_to: string | null;
  contact: { full_name: string; title: string } | null;
  company: { name: string; domain: string } | null;
}

export interface SalesRep {
  id: string;
  name: string;
  email: string;
  booking_url: string | null;
  active: boolean;
}

export interface InboxContact {
  id: string;
  full_name: string;
  title: string;
  email: string | null;
  synthetic: boolean;
}

export interface InboxCompany {
  id: string;
  name: string;
  domain: string;
  synthetic: boolean;
}

export interface ThreadRow {
  prospect_id: string;
  campaign_id: string;
  contact: InboxContact;
  company: InboxCompany;
  status: string;
  meeting_booked: boolean;
  simulated: boolean;
  message_count: number;
  last_message_at: string;
  last_label: string | null;
}

export interface ThreadMessage {
  id: string;
  direction: "in" | "out";
  kind: string;
  subject: string;
  body: string;
  status: string;
  delivery: string | null;
  source: string | null;
  intended_to: string | null;
  actual_to: string | null;
  cc: string[];
  sent_at: string | null;
  received_at: string | null;
  created_at: string;
  error: string | null;
  label: string | null;
  confidence: number | null;
  summary: string | null;
}

export interface ThreadDetail {
  prospect: {
    id: string;
    campaign_id: string;
    role: string;
    status: string;
    arm_key: string | null;
    pick_reason: string;
    meeting_booked_at: string | null;
    meeting_synthetic: boolean;
  };
  contact: InboxContact;
  company: InboxCompany;
  rep: { name: string; email: string; booking_url: string | null } | null;
  messages: ThreadMessage[];
}
