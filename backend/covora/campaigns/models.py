import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from covora.db.base import Base, IdTimestampMixin

DEFAULT_PROGRESS = {"used_queries": [], "waves": 0, "stop_reason": None}


class Campaign(IdTimestampMixin, Base):
    """One campaign version (spec §18). Status: draft → queued → running → complete | failed."""

    __tablename__ = "campaign"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspace.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    icp_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("icp_version.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    root_campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    parent_campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    config_snapshot: Mapped[dict] = mapped_column(JSONB)
    goal: Mapped[dict] = mapped_column(JSONB)
    target_prospects: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    progress: Mapped[dict] = mapped_column(
        JSONB,
        default=lambda: dict(DEFAULT_PROGRESS),
        server_default=text("""'{"used_queries": [], "waves": 0, "stop_reason": null}'::jsonb"""),
    )
    last_error: Mapped[str | None] = mapped_column(Text)
