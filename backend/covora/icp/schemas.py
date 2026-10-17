"""Structured ICP (spec §9.1). Every tagged value records whether the user stated it or the model inferred it."""

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, model_validator

from covora.text import clean_strings

Origin = Literal["stated", "inferred"]
V = TypeVar("V")


class Tagged(BaseModel, Generic[V]):
    value: V
    origin: Origin


class Range(BaseModel):
    min: int | None = None
    max: int | None = None

    @model_validator(mode="after")
    def _ordered(self) -> "Range":
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min must be ≤ max")
        return self


class Location(BaseModel):
    country: str
    regions: list[str] = []


class SizeBand(BaseModel):
    employees: Range
    primary_titles: list[str]
    secondary_titles: list[str] = []
    origin: Origin


class BuyerMap(BaseModel):
    target_functions: list[Tagged[str]] = []
    by_company_size: list[SizeBand] = []
    skip_titles: list[Tagged[str]] = []


class StructuredICP(BaseModel):
    summary: str
    industries: list[Tagged[str]] = []
    locations: list[Tagged[Location]] = []
    employee_range: Tagged[Range] | None = None
    revenue_range_usd: Tagged[Range] | None = None
    other_criteria: list[Tagged[str]] = []
    exclusions: list[Tagged[str]] = []
    buyer_map: BuyerMap = BuyerMap()
    assumptions: list[str] = []
    search_queries: list[str] = []

    @model_validator(mode="before")
    @classmethod
    def _clean(cls, data: Any) -> Any:
        return clean_strings(data) if isinstance(data, dict) else data
