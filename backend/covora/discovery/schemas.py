from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from covora.text import clean_strings, clean_text


class QueryPlan(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=10)

    @field_validator("queries", mode="before")
    @classmethod
    def _clean(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        cleaned = [clean_text(q) for q in value if isinstance(q, str)]
        return [q for q in cleaned if 3 <= len(q) <= 200]


class ExtractedCompany(BaseModel):
    name: str
    domain: str
    source_url: str

    @field_validator("name", mode="before")
    @classmethod
    def _clean_name(cls, value: Any) -> Any:
        return clean_text(value) if isinstance(value, str) else value


class ExtractedCompanies(BaseModel):
    companies: list[ExtractedCompany]

    @model_validator(mode="before")
    @classmethod
    def _tolerate_missing(cls, data: Any) -> Any:
        return {"companies": []} if data == {} else clean_strings_except(data, {"domain", "source_url"})


def clean_strings_except(data: Any, keep: set[str]) -> Any:
    """clean_strings, but leave the named keys verbatim (URLs, domains, quotes, emails)."""
    if isinstance(data, dict):
        return {k: (v if k in keep else clean_strings_except(v, keep)) for k, v in data.items()}
    if isinstance(data, list):
        return [clean_strings_except(v, keep) for v in data]
    return clean_strings(data)


FactField = Literal[
    "employee_count", "revenue_usd", "industry", "location", "description", "founded_year", "recent_event"
]


class ExtractedFact(BaseModel):
    field: FactField
    value: str
    source_url: str
    quote: str = ""
    label: Literal["verified", "unverified"]

    @field_validator("value", mode="before")
    @classmethod
    def _value_text(cls, value: Any) -> Any:
        return clean_text(str(value)) if isinstance(value, int | float | str) else value


class FactSlot(BaseModel):
    value: str
    source_url: str
    quote: str = ""
    label: Literal["verified", "unverified"]

    @field_validator("value", mode="before")
    @classmethod
    def _value_text(cls, value: Any) -> Any:
        return clean_text(str(value)) if isinstance(value, int | float | str) else value


_SLOT_HELP = {
    "employee_count": "Number of employees, only if a page states it (just the number)",
    "revenue_usd": "Annual revenue in US dollars, only if a page states it (just the number)",
    "industry": "What the company makes or does, from its own website (e.g. 'metal fabrication')",
    "location": "Where the company is based (city, state or country)",
    "description": "One sentence on what the company does",
    "founded_year": "Year founded, only if a page states it",
    "recent_event": "A recent, dated event (expansion, acquisition, new product), if any",
}


class ExtractedFacts(BaseModel):
    """One slot per fact type, each filled from the pages or null, so none is skipped by accident."""

    employee_count: FactSlot | None = Field(None, description=_SLOT_HELP["employee_count"])
    revenue_usd: FactSlot | None = Field(None, description=_SLOT_HELP["revenue_usd"])
    industry: FactSlot | None = Field(None, description=_SLOT_HELP["industry"])
    location: FactSlot | None = Field(None, description=_SLOT_HELP["location"])
    description: FactSlot | None = Field(None, description=_SLOT_HELP["description"])
    founded_year: FactSlot | None = Field(None, description=_SLOT_HELP["founded_year"])
    recent_event: FactSlot | None = Field(None, description=_SLOT_HELP["recent_event"])

    @property
    def facts(self) -> list[ExtractedFact]:
        out = []
        for name in _SLOT_HELP:
            slot = getattr(self, name)
            if slot is not None:
                out.append(ExtractedFact(field=name, **slot.model_dump()))
        return out


class CriterionJudgment(BaseModel):
    criterion: str
    status: Literal["met", "not_met", "unknown"]
    fact_ids: list[str] = []


class FitJudgment(BaseModel):
    criteria: list[CriterionJudgment]
    confidence: Literal["high", "medium", "low"]
    reason: str = Field(max_length=400)

    @field_validator("reason", mode="before")
    @classmethod
    def _clean_reason(cls, value: Any) -> Any:
        return clean_text(value)[:400] if isinstance(value, str) else value
