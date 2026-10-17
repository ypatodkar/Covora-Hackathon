import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from covora.db.base import Base, IdTimestampMixin


class IcpVersion(IdTimestampMixin, Base):
    """An immutable saved ICP (spec §18). Each save is a new version."""

    __tablename__ = "icp_version"
    __table_args__ = (UniqueConstraint("workspace_id", "version"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspace.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    prompt_text: Mapped[str] = mapped_column(Text)
    structured: Mapped[dict] = mapped_column(JSONB)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[str] = mapped_column(String(10))  # user | agent
