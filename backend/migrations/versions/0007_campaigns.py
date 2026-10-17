"""campaign

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaign",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("icp_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("icp_version.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("root_campaign_id", postgresql.UUID(as_uuid=True)),
        sa.Column("parent_campaign_id", postgresql.UUID(as_uuid=True)),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True)),
        sa.Column("config_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("goal", postgresql.JSONB(), nullable=False),
        sa.Column("target_prospects", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "progress",
            postgresql.JSONB(),
            server_default=sa.text("""'{"used_queries": [], "waves": 0, "stop_reason": null}'::jsonb"""),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text()),
    )
    op.create_index("ix_campaign_workspace_id", "campaign", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("campaign")
