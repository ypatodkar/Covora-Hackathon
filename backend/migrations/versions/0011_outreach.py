"""template, campaign_arm, email_message, reply_classification, sales_rep, rep_assignment, suppression; prospect.arm_key

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def _base() -> list[sa.Column]:
    return [
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def _fk(table: str, *, nullable: bool = False, cascade: bool = True) -> sa.ForeignKey:
    return sa.ForeignKey(f"{table}.id", ondelete="CASCADE" if cascade else None)


def upgrade() -> None:
    op.create_table(
        "template",
        *_base(),
        sa.Column("workspace_id", UUID, _fk("workspace"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("angle", sa.String(20), nullable=False),
        sa.Column("length", sa.String(10), nullable=False),
        sa.Column("tone", sa.String(10), nullable=False),
        sa.Column("cta", sa.String(20), nullable=False),
        sa.Column("subject_template", sa.Text(), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("offering_types", JSONB, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_table(
        "campaign_arm",
        *_base(),
        sa.Column("campaign_id", UUID, _fk("campaign"), nullable=False, index=True),
        sa.Column("key", sa.String(2), nullable=False),
        sa.Column("template_id", UUID, sa.ForeignKey("template.id"), nullable=False),
        sa.Column("config", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.create_table(
        "email_message",
        *_base(),
        sa.Column("campaign_id", UUID, _fk("campaign"), nullable=False, index=True),
        sa.Column("prospect_id", UUID, _fk("prospect"), nullable=False, index=True),
        sa.Column("arm_key", sa.String(2)),
        sa.Column("direction", sa.String(3), nullable=False),
        sa.Column("kind", sa.String(15), nullable=False),
        sa.Column("status", sa.String(15), nullable=False),
        sa.Column("intended_to", sa.String(320)),
        sa.Column("actual_to", sa.String(320)),
        sa.Column("cc", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("template_id", UUID),
        sa.Column("personalization", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("delivery", sa.String(10)),
        sa.Column("source", sa.String(15)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("received_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
    )
    op.create_index("ix_email_message_status", "email_message", ["status", "direction"])
    op.create_table(
        "reply_classification",
        sa.Column("email_message_id", UUID, _fk("email_message"), primary_key=True),
        sa.Column("label", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("model", sa.String(200)),
        sa.Column("referral", JSONB),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("rule_override", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "sales_rep",
        *_base(),
        sa.Column("workspace_id", UUID, _fk("workspace"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("booking_url", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("last_assigned_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "rep_assignment",
        *_base(),
        sa.Column("prospect_id", UUID, _fk("prospect"), nullable=False, index=True),
        sa.Column("sales_rep_id", UUID, _fk("sales_rep"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
    )
    op.create_table(
        "suppression",
        sa.Column("email_normalized", sa.String(320), primary_key=True),
        sa.Column("workspace_id", UUID, _fk("workspace"), nullable=False),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("source_email_id", UUID),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column("prospect", sa.Column("arm_key", sa.String(2)))


def downgrade() -> None:
    op.drop_column("prospect", "arm_key")
    for table in (
        "suppression",
        "rep_assignment",
        "sales_rep",
        "reply_classification",
        "email_message",
        "campaign_arm",
        "template",
    ):
        op.drop_table(table)
