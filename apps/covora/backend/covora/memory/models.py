import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from covora.config import get_settings
from covora.db.base import Base, IdTimestampMixin


class MemoryItem(IdTimestampMixin, Base):
    """Long-term CoALA memory (spec §7.2): episodic experiences and semantic insights."""

    __tablename__ = "memory_item"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspace.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # episodic | semantic
    subtype: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(20))  # research | gmail_sim | in_app_sim | mock_sim
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    source_refs: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    outcome: Mapped[dict | None] = mapped_column(JSONB)
    evidence_level: Mapped[str | None] = mapped_column(String(20))
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    embedding: Mapped[list[float]] = mapped_column(Vector(get_settings().nemotron_embed_dim))


class MemoryRead(IdTimestampMixin, Base):
    """Which memories were loaded into working memory for one step (spec §7.1)."""

    __tablename__ = "memory_read"

    span_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("span.id", ondelete="CASCADE"), index=True)
    memory_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("memory_item.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(Text)
    rank: Mapped[int] = mapped_column(Integer)


class PromptVersion(IdTimestampMixin, Base):
    """Procedural memory: versioned prompts (spec §7.2)."""

    __tablename__ = "prompt_version"
    __table_args__ = (UniqueConstraint("name", "version"),)

    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
