import type { IcpVersionOut, ParseResponse, StructuredICP } from "../api/types";

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
