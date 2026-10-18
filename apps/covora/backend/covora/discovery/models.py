import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from covora.db.base import Base, IdTimestampMixin


class Company(IdTimestampMixin, Base):
    __tablename__ = "company"
    __table_args__ = (UniqueConstraint("workspace_id", "domain"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspace.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(300))
    domain: Mapped[str] = mapped_column(String(253))
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class CampaignCompany(IdTimestampMixin, Base):
    """A company in one campaign.

    Status: candidate → qualified | rejected | needs_review → contact_selected | no_contact.
    """

    __tablename__ = "campaign_company"
    __table_args__ = (UniqueConstraint("campaign_id", "company_id"),)

    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaign.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("company.id", ondelete="CASCADE"))
    wave: Mapped[int] = mapped_column(Integer)
    source_url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="candidate")
    criteria: Mapped[list] = mapped_column(JSONB, default=list)
    fit_score: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[str | None] = mapped_column(String(10))
    reason: Mapped[str | None] = mapped_column(Text)
    rank: Mapped[int | None] = mapped_column(Integer)


class Fact(IdTimestampMixin, Base):
    """Semantic memory about a company or contact, always with its source (spec §9.3)."""

    __tablename__ = "fact"

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("company.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    field: Mapped[str] = mapped_column(String(40))
    value: Mapped[str | int | float | dict | list] = mapped_column(JSONB)
    source_url: Mapped[str] = mapped_column(Text)
    quote: Mapped[str] = mapped_column(Text, default="")
    label: Mapped[str] = mapped_column(String(12))  # verified | unverified | unknown
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
