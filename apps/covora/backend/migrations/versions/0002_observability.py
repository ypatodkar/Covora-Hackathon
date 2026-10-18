"""workflow_run, span, llm_call

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "workflow_run",
        *_base_columns(),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("thread_id", sa.String(200)),
    )
    op.create_index("ix_workflow_run_workspace_id", "workflow_run", ["workspace_id"])
    op.create_table(
        "span",
        *_base_columns(),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=False),
        sa.Column("parent_span_id", postgresql.UUID(as_uuid=True)),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("attributes", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("error", sa.Text()),
    )
    op.create_index("ix_span_run_id", "span", ["run_id"])
    op.create_index("ix_span_parent_span_id", "span", ["parent_span_id"])
    op.create_table(
        "llm_call",
        *_base_columns(),
        sa.Column("span_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("span.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task", sa.String(40), nullable=False),
        sa.Column("routing_mode", sa.String(20), nullable=False),
        sa.Column("requested_model", sa.String(200), nullable=False),
        sa.Column("actual_model", sa.String(200), nullable=False),
        sa.Column("routing_reason", sa.Text(), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("fallback_reason", sa.Text()),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("est_cost_usd", sa.Float()),
        sa.Column("output_valid", sa.Boolean(), nullable=False),
        sa.Column("retries", sa.Integer(), nullable=False),
        sa.Column("request_payload", postgresql.JSONB()),
        sa.Column("response_text", sa.Text()),
    )
    op.create_index("ix_llm_call_span_id", "llm_call", ["span_id"])


def downgrade() -> None:
    op.drop_table("llm_call")
    op.drop_table("span")
    op.drop_table("workflow_run")
