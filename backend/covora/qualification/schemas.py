from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from covora.discovery.schemas import clean_strings_except
from covora.text import clean_text

Function = Literal[
    "executive", "operations", "partnerships", "sales", "marketing", "finance", "engineering", "hr", "other"
]
Seniority = Literal["owner", "c_level", "vp", "director", "manager", "individual"]
_VERBATIM = {"email", "linkedin_url", "source_url", "contact_id"}


class ExtractedPerson(BaseModel):
    full_name: str
    title: str
    function: Function = "other"
    seniority: Seniority = "individual"
    source_url: str
    email: str | None = None
    linkedin_url: str | None = None


class ExtractedPeople(BaseModel):
    people: list[ExtractedPerson]

    @model_validator(mode="before")
    @classmethod
    def _clean(cls, data: Any) -> Any:
        return clean_strings_except(data, _VERBATIM)


class Pick(BaseModel):
    contact_id: str
    reason: str = Field(max_length=300)
    confidence: Literal["high", "medium", "low"]

    @field_validator("reason", mode="before")
    @classmethod
    def _clean_reason(cls, value: Any) -> Any:
        return clean_text(value)[:300] if isinstance(value, str) else value


class ContactSelection(BaseModel):
    primary: Pick | None = None
    backup: Pick | None = None
    no_suitable_contact: bool = False
