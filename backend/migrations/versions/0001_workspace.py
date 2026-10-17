"""workspace + pgvector extension

Revision ID: 0001
Revises:
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "workspace",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("singleton", sa.Boolean(), server_default=sa.true(), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("website", sa.String(500)),
        sa.Column("description", sa.Text()),
        sa.Column("value_props", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("offering_type", sa.String(20), server_default="sales_call", nullable=False),
        sa.Column("settings", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("workspace")
