from sqlalchemy import Boolean, Float, String, Text, text, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from covora.db.base import Base, IdTimestampMixin


class Workspace(IdTimestampMixin, Base):
    """The single local workspace (spec §18). `singleton` is unique so a second row can't exist."""

    __tablename__ = "workspace"

    singleton: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    website: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    value_props: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    offering_type: Mapped[str] = mapped_column(String(20), default="sales_call", server_default="sales_call")
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    youcom_spend_usd: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
