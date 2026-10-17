"""tool_call, search_cache, workspace.youcom_spend_usd

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tool_call",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("span_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("span.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("request_summary", sa.Text(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("est_cost_usd", sa.Float(), nullable=False),
    )
    op.create_index("ix_tool_call_span_id", "tool_call", ["span_id"])
    op.create_table(
        "search_cache",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("endpoint", sa.String(20), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column("workspace", sa.Column("youcom_spend_usd", sa.Float(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("workspace", "youcom_spend_usd")
    op.drop_table("search_cache")
    op.drop_table("tool_call")
