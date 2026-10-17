"""memory_item, memory_read, prompt_version

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from covora.config import get_settings

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# Exact cosine scan, no ANN index: pgvector's HNSW limit is 2000 dims and memory is small (Plan 1 decision).
EMBED_DIM = get_settings().nemotron_embed_dim


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "memory_item",
        *_base_columns(),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("subtype", sa.String(40), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("source_refs", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("outcome", postgresql.JSONB()),
        sa.Column("evidence_level", sa.String(20)),
        sa.Column("superseded_by", postgresql.UUID(as_uuid=True)),
        sa.Column("embedding", Vector(EMBED_DIM), nullable=False),
    )
    op.create_index("ix_memory_item_workspace_id", "memory_item", ["workspace_id"])
    op.create_index("ix_memory_item_kind_subtype", "memory_item", ["kind", "subtype"])
    op.create_table(
        "memory_read",
        *_base_columns(),
        sa.Column("span_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("span.id", ondelete="CASCADE"), nullable=False),
        sa.Column("memory_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("memory_item.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
    )
    op.create_index("ix_memory_read_span_id", "memory_read", ["span_id"])
    op.create_table(
        "prompt_version",
        *_base_columns(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("name", "version"),
    )


def downgrade() -> None:
    op.drop_table("prompt_version")
    op.drop_table("memory_read")
    op.drop_table("memory_item")
