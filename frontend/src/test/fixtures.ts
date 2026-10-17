import type { IcpVersionOut, ParseResponse, RunDetail, StructuredICP, WorkspaceSettings } from "../api/types";

// Mirrors backend/tests/fixtures_icp.py.
export const EXAMPLE_ICP: StructuredICP = {
  summary: "US manufacturers, 5–25 employees, $5–20M revenue; ops and partnerships leaders",
  industries: [{ value: "manufacturing", origin: "stated" }],
  locations: [{ value: { country: "US", regions: [] }, origin: "stated" }],
  employee_range: { value: { min: 5, max: 25 }, origin: "stated" },
  revenue_range_usd: { value: { min: 5000000, max: 20000000 }, origin: "stated" },
  other_criteria: [],
  exclusions: [],
  buyer_map: {
    target_functions: [
      { value: "operations", origin: "stated" },
      { value: "business partnerships", origin: "stated" },
    ],
    by_company_size: [
      {
        employees: { min: 1, max: 50 },
        primary_titles: ["Owner", "CEO", "President", "COO", "Operations Manager"],
        secondary_titles: ["Plant Manager", "Head of Partnerships"],
        origin: "inferred",
      },
    ],
    skip_titles: [{ value: "Recruiter", origin: "inferred" }],
  },
  assumptions: ["Read 'business partnerships' as BD/partnerships roles"],
  search_queries: ["US metal fabrication companies 10-25 employees", "small contract manufacturers Ohio"],
};

export const EXAMPLE_ICP_WITH_INFERRED_SIZE: StructuredICP = {
  ...EXAMPLE_ICP,
  employee_range: { value: { min: 5, max: 25 }, origin: "inferred" },
};

export const VAGUE_ICP: StructuredICP = {
  summary: "Companies (no criteria given)",
  industries: [],
  locations: [],
  employee_range: null,
  revenue_range_usd: null,
  other_criteria: [],
  exclusions: [],
  buyer_map: { target_functions: [], by_company_size: [], skip_titles: [] },
  assumptions: ["No industry, size, or location was given"],
  search_queries: [],
};

export const PARSED: ParseResponse = { draft: EXAMPLE_ICP_WITH_INFERRED_SIZE, run_id: "r1", working_memory: [] };

export const VERSION: IcpVersionOut = {
  id: "v1",
  version: 1,
  prompt_text: "US manufacturers",
  structured: EXAMPLE_ICP,
  parent_id: null,
  created_by: "user",
  created_at: "2026-10-17T12:00:00Z",
};

const SUPER_MODEL = "nvidia/nemotron-3-super-120b-a12b";

export const RUN_DETAIL: RunDetail = {
  run: {
    id: "r1",
    kind: "icp",
    status: "succeeded",
    started_at: "2026-10-17T12:00:00Z",
    ended_at: "2026-10-17T12:00:01.200Z",
    duration_ms: 1200,
    error: null,
    llm_calls: 1,
    prompt_tokens: 900,
    completion_tokens: 400,
    est_cost_usd: null,
  },
  spans: [
    {
      id: "s-agent",
      parent_span_id: null,
      name: "icp:icp_parsing",
      kind: "agent",
      status: "ok",
      started_at: "2026-10-17T12:00:00Z",
      duration_ms: 1150,
      attributes: {},
      error: null,
    },
    {
      id: "s-llm",
      parent_span_id: "s-agent",
      name: "llm:icp_parsing",
      kind: "llm",
      status: "ok",
      started_at: "2026-10-17T12:00:00.050Z",
      duration_ms: 1100,
      attributes: {},
      error: null,
    },
  ],
  llm_calls: [
    {
      id: "c1",
      span_id: "s-llm",
      task: "icp_parsing",
      routing_mode: "fixed",
      requested_model: SUPER_MODEL,
      actual_model: SUPER_MODEL,
      routing_reason: "fixed: icp_parsing → super",
      fallback_used: false,
      fallback_reason: null,
      prompt_tokens: 900,
      completion_tokens: 400,
      latency_ms: 1100,
      est_cost_usd: null,
      output_valid: true,
      retries: 0,
      created_at: "2026-10-17T12:00:01Z",
    },
  ],
};

export const FAILED_RUN_DETAIL: RunDetail = {
  run: { ...RUN_DETAIL.run, id: "r2", status: "failed", error: "Every model attempt failed" },
  spans: [
    {
      id: "s-fail",
      parent_span_id: null,
      name: "llm:icp_parsing",
      kind: "llm",
      status: "error",
      started_at: "2026-10-17T12:00:00Z",
      duration_ms: 900,
      attributes: {},
      error: "503 Service Unavailable",
    },
  ],
  llm_calls: [],
};

export const SETTINGS: WorkspaceSettings = {
  goals: { goal_type: "positive_replies", target: 10, expected_positive_rate: 0.01, meetings_per_positive: 0.5 },
  sending: { daily_gmail_cap: 100, first_batch_size: 10, no_reply_window_minutes: 10 },
};
