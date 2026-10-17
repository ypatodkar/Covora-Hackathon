"""Goal-based campaign sizing (spec §5.2): prospects needed = goal ÷ expected rate, plus cost estimates."""

import math
from dataclasses import dataclass
from typing import Literal

from covora.workspace.settings import Goals


@dataclass(frozen=True)
class CostModel:
    """Research and model work per prospect. Defaults: 4 searches + 2 pages per qualified prospect, ×2 for misses."""

    searches_per_prospect: float = 8.0
    pages_per_prospect: float = 4.0
    model_calls_per_prospect: float = 6.0
    source: Literal["default", "measured"] = "default"


@dataclass
class SizingEstimate:
    rate_used: float
    prospects_needed: int
    prospects_planned: int
    companies_needed: int
    est_searches: int
    est_pages: int
    est_youcom_usd: float
    est_model_calls: int
    gmail_emails: int
    in_app_emails: int
    budget_remaining_usd: float
    fits_budget: bool
    max_affordable_prospects: int
    cost_model_source: str


def estimate_campaign(
    goals: Goals,
    *,
    prospect_limit: int | None,
    cost: CostModel,
    search_price: float,
    page_price: float,
    budget_remaining: float,
    daily_gmail_cap: int,
) -> SizingEstimate:
    rate = goals.expected_positive_rate
    if goals.goal_type == "meetings":
        rate *= goals.meetings_per_positive
    needed = math.ceil(round(goals.target / rate, 6))
    planned = min(needed, prospect_limit) if prospect_limit else needed
    searches = math.ceil(planned * cost.searches_per_prospect)
    pages = math.ceil(planned * cost.pages_per_prospect)
    usd = round(searches * search_price + pages * page_price, 2)
    per_prospect = cost.searches_per_prospect * search_price + cost.pages_per_prospect * page_price
    remaining = max(budget_remaining, 0.0)
    affordable = math.floor(round(remaining / per_prospect, 6)) if per_prospect > 0 else planned
    gmail = min(planned, daily_gmail_cap)
    return SizingEstimate(
        rate_used=rate,
        prospects_needed=needed,
        prospects_planned=planned,
        companies_needed=planned,
        est_searches=searches,
        est_pages=pages,
        est_youcom_usd=usd,
        est_model_calls=math.ceil(planned * cost.model_calls_per_prospect),
        gmail_emails=gmail,
        in_app_emails=planned - gmail,
        budget_remaining_usd=round(remaining, 2),
        fits_budget=usd <= remaining,
        max_affordable_prospects=affordable,
        cost_model_source=cost.source,
    )
