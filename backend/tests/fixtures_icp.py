"""ICP fixtures: the spec §9.1 example, a variant with an inferred size, and a vague one."""

import copy

EXAMPLE_ICP = {
    "summary": "US manufacturers, 5–25 employees, $5–20M revenue; ops and partnerships leaders",
    "industries": [{"value": "manufacturing", "origin": "stated"}],
    "locations": [{"value": {"country": "US", "regions": []}, "origin": "stated"}],
    "employee_range": {"value": {"min": 5, "max": 25}, "origin": "stated"},
    "revenue_range_usd": {"value": {"min": 5000000, "max": 20000000}, "origin": "stated"},
    "other_criteria": [],
    "exclusions": [],
    "buyer_map": {
        "target_functions": [
            {"value": "operations", "origin": "stated"},
            {"value": "business partnerships", "origin": "stated"},
        ],
        "by_company_size": [
            {
                "employees": {"min": 1, "max": 50},
                "primary_titles": ["Owner", "CEO", "President", "COO", "Operations Manager"],
                "secondary_titles": ["Plant Manager", "Head of Partnerships"],
                "origin": "inferred",
            }
        ],
        "skip_titles": [{"value": "Recruiter", "origin": "inferred"}],
    },
    "assumptions": ["Read 'business partnerships' as BD/partnerships roles"],
    "search_queries": [
        "US metal fabrication companies 10-25 employees",
        "small contract manufacturers Ohio",
        "family-owned machine shops United States",
        "US plastics manufacturers under 25 employees",
        "independent food manufacturers US small",
    ],
}

EXAMPLE_ICP_WITH_INFERRED_SIZE = copy.deepcopy(EXAMPLE_ICP)
EXAMPLE_ICP_WITH_INFERRED_SIZE["employee_range"]["origin"] = "inferred"

VAGUE_ICP_JSON = {
    "summary": "Companies (no criteria given)",
    "industries": [],
    "locations": [],
    "employee_range": None,
    "revenue_range_usd": None,
    "other_criteria": [],
    "exclusions": [],
    "buyer_map": {"target_functions": [], "by_company_size": [], "skip_titles": []},
    "assumptions": ["No industry, size, or location was given"],
    "search_queries": [],
}
