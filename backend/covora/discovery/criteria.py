"""ICP criteria and the fit score, computed in code so rankings are consistent and explainable (spec §9.2)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from covora.icp.schemas import StructuredICP

Status = Literal["met", "not_met", "unknown"]

_HARD_WEIGHT, _SOFT_WEIGHT = 2.0, 1.0
_POINTS = {"met": 1.0, "unknown": 0.5, "not_met": 0.0}
_HARD_MISS_CAP = 20  # a hard criterion (industry, location) not met
_STATED_MISS_CAP = 50  # a criterion the user stated (e.g. company size) not met


@dataclass(frozen=True)
class Criterion:
    name: str
    description: str
    hard: bool
    stated: bool
    kind: Literal["include", "exclude"]


def _range_text(r) -> str:
    low = "any" if r.min is None else f"{r.min:,}"
    high = "any" if r.max is None else f"{r.max:,}"
    return f"{low}–{high}"


def icp_criteria(icp: StructuredICP) -> list[Criterion]:
    out: list[Criterion] = []
    if icp.industries:
        names = ", ".join(t.value for t in icp.industries)
        stated = any(t.origin == "stated" for t in icp.industries)
        out.append(Criterion("industry", f"Industry is one of: {names}", True, stated, "include"))
    if icp.locations:
        places = "; ".join(
            t.value.country + (f" ({', '.join(t.value.regions)})" if t.value.regions else "") for t in icp.locations
        )
        stated = any(t.origin == "stated" for t in icp.locations)
        out.append(Criterion("location", f"Located in: {places}", True, stated, "include"))
    if icp.employee_range:
        text = f"Employees: {_range_text(icp.employee_range.value)}"
        out.append(Criterion("employee_range", text, False, icp.employee_range.origin == "stated", "include"))
    if icp.revenue_range_usd:
        text = f"Annual revenue (USD): {_range_text(icp.revenue_range_usd.value)}"
        out.append(Criterion("revenue_range", text, False, icp.revenue_range_usd.origin == "stated", "include"))
    for i, t in enumerate(icp.other_criteria):
        out.append(Criterion(f"other:{i}", t.value, False, t.origin == "stated", "include"))
    for i, t in enumerate(icp.exclusions):
        out.append(Criterion(f"exclusion:{i}", f"Exclude if: {t.value}", True, t.origin == "stated", "exclude"))
    return out


def fit_score(criteria: list[Criterion], statuses: Mapping[str, Status]) -> int:
    includes = [c for c in criteria if c.kind == "include"]
    if any(statuses.get(c.name) == "met" for c in criteria if c.kind == "exclude"):
        return 0
    if not includes:
        return 50
    total = sum(_HARD_WEIGHT if c.hard else _SOFT_WEIGHT for c in includes)
    earned = sum(
        (_HARD_WEIGHT if c.hard else _SOFT_WEIGHT) * _POINTS[statuses.get(c.name, "unknown")] for c in includes
    )
    score = round(100 * earned / total)
    if any(c.hard and statuses.get(c.name) == "not_met" for c in includes):
        score = min(score, _HARD_MISS_CAP)
    if any(not c.hard and c.stated and statuses.get(c.name) == "not_met" for c in includes):
        score = min(score, _STATED_MISS_CAP)
    return score
