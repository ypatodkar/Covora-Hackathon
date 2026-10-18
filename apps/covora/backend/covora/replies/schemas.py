from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from covora.discovery.schemas import clean_strings_except

ReplyLabel = Literal["interested", "not_now", "not_interested", "wrong_person", "unsubscribe", "out_of_office", "other"]


class Referral(BaseModel):
    name: str
    title: str = ""


class ReplyClassificationOut(BaseModel):
    label: ReplyLabel
    confidence: float = Field(ge=0, le=1)
    referral: Referral | None = None
    summary: str = ""

    @model_validator(mode="before")
    @classmethod
    def _clean(cls, data: Any) -> Any:
        return clean_strings_except(data, {"label"})


class HandoffReply(BaseModel):
    body: str
