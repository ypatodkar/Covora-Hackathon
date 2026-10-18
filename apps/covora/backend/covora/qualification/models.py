import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from covora.db.base import Base, IdTimestampMixin


class Contact(IdTimestampMixin, Base):
    """A person named in a cited source. Emails only if found verbatim (spec §9.4–9.5)."""

    __tablename__ = "contact"
    __table_args__ = (UniqueConstraint("company_id", "name_key"),)

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("company.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    name_key: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    function: Mapped[str] = mapped_column(String(30))
    seniority: Mapped[str] = mapped_column(String(20))
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    source_urls: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    email: Mapped[str | None] = mapped_column(String(320))
    email_status: Mapped[str] = mapped_column(String(12), default="missing")  # verified | unverified | missing
    email_source_url: Mapped[str | None] = mapped_column(Text)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class Prospect(IdTimestampMixin, Base):
    """A contact picked for a campaign, as primary or backup."""

    __tablename__ = "prospect"
    __table_args__ = (UniqueConstraint("campaign_id", "contact_id"),)

    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaign.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("company.id", ondelete="CASCADE"))
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contact.id", ondelete="CASCADE"))
    short_id: Mapped[str] = mapped_column(String(8), unique=True)
    role: Mapped[str] = mapped_column(String(10))  # primary | backup
    pick_reason: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="selected")
    arm_key: Mapped[str | None] = mapped_column(String(2))
    assigned_rep_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    meeting_booked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meeting_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
