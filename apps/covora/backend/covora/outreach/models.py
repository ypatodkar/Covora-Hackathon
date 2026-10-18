import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from covora.db.base import Base, IdTimestampMixin


class Template(IdTimestampMixin, Base):
    __tablename__ = "template"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspace.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    angle: Mapped[str] = mapped_column(String(20))  # pain | roi | social-proof | curiosity | partnership | referral-ask
    length: Mapped[str] = mapped_column(String(10))  # short | medium
    tone: Mapped[str] = mapped_column(String(10))  # direct | warm | formal
    cta: Mapped[str] = mapped_column(String(20))  # question | booking-link | soft
    subject_template: Mapped[str] = mapped_column(Text)
    body_template: Mapped[str] = mapped_column(Text)
    offering_types: Mapped[list] = mapped_column(JSONB, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class CampaignArm(IdTimestampMixin, Base):
    __tablename__ = "campaign_arm"

    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaign.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(2))
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("template.id"))
    config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))


class EmailMessage(IdTimestampMixin, Base):
    __tablename__ = "email_message"

    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaign.id", ondelete="CASCADE"), index=True)
    prospect_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prospect.id", ondelete="CASCADE"), index=True)
    arm_key: Mapped[str | None] = mapped_column(String(2))
    direction: Mapped[str] = mapped_column(String(3))  # out | in
    kind: Mapped[str] = mapped_column(String(15))  # cold | handoff | manual_reply | inbound
    status: Mapped[str] = mapped_column(String(15))
    intended_to: Mapped[str | None] = mapped_column(String(320))
    actual_to: Mapped[str | None] = mapped_column(String(320))
    cc: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    subject: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    personalization: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    delivery: Mapped[str | None] = mapped_column(String(10))  # gmail | in_app
    source: Mapped[str | None] = mapped_column(String(15))  # in_app_sim | gmail_sim | mock_sim
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class ReplyClassification(Base):
    __tablename__ = "reply_classification"

    email_message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("email_message.id", ondelete="CASCADE"), primary_key=True
    )
    label: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[float] = mapped_column(Float)
    model: Mapped[str | None] = mapped_column(String(200))
    referral: Mapped[dict | None] = mapped_column(JSONB)
    summary: Mapped[str] = mapped_column(Text, default="")
    rule_override: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class SalesRep(IdTimestampMixin, Base):
    __tablename__ = "sales_rep"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspace.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    booking_url: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RepAssignment(IdTimestampMixin, Base):
    __tablename__ = "rep_assignment"

    prospect_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prospect.id", ondelete="CASCADE"), index=True)
    sales_rep_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sales_rep.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(Text)


class Suppression(Base):
    __tablename__ = "suppression"

    email_normalized: Mapped[str] = mapped_column(String(320), primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspace.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(String(40))
    source_email_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
