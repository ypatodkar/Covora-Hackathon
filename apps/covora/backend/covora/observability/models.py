import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from covora.db.base import Base, IdTimestampMixin


class WorkflowRun(IdTimestampMixin, Base):
    __tablename__ = "workflow_run"

    kind: Mapped[str] = mapped_column(String(20))  # icp | campaign | reply | learning | eval
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspace.id", ondelete="CASCADE"), index=True)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | succeeded | failed
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    thread_id: Mapped[str | None] = mapped_column(String(200))


class Span(IdTimestampMixin, Base):
    __tablename__ = "span"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_run.id", ondelete="CASCADE"), index=True)
    trace_id: Mapped[str] = mapped_column(String(64))
    parent_span_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))  # stage | agent | llm | tool | http | db | memory
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | ok | error
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    error: Mapped[str | None] = mapped_column(Text)


class LlmCall(IdTimestampMixin, Base):
    __tablename__ = "llm_call"

    span_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("span.id", ondelete="CASCADE"), index=True)
    task: Mapped[str] = mapped_column(String(40))
    routing_mode: Mapped[str] = mapped_column(String(20))
    requested_model: Mapped[str] = mapped_column(String(200))
    actual_model: Mapped[str] = mapped_column(String(200))
    routing_reason: Mapped[str] = mapped_column(Text)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback_reason: Mapped[str | None] = mapped_column(Text)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    est_cost_usd: Mapped[float | None] = mapped_column(Float)
    output_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    request_payload: Mapped[list | dict | None] = mapped_column(JSONB)
    response_text: Mapped[str | None] = mapped_column(Text)
