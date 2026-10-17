import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from covora.db.base import Base, IdTimestampMixin


class ToolCall(IdTimestampMixin, Base):
    """One external research call (spec §16.1)."""

    __tablename__ = "tool_call"

    span_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("span.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20))  # youcom | mock
    operation: Mapped[str] = mapped_column(String(20))  # search | contents
    request_summary: Mapped[str] = mapped_column(Text)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20))  # ok | error | refused
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    est_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)


class SearchCache(Base):
    """Cached You.com responses, keyed by sha256(endpoint + canonical params)."""

    __tablename__ = "search_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    endpoint: Mapped[str] = mapped_column(String(20))
    params: Mapped[dict] = mapped_column(JSONB)
    response: Mapped[dict | list] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
