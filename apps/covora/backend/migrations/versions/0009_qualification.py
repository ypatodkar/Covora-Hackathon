"""contact, prospect

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def _base() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "contact",
        *_base(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("name_key", sa.String(200), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("function", sa.String(30), nullable=False),
        sa.Column("seniority", sa.String(20), nullable=False),
        sa.Column("linkedin_url", sa.Text()),
        sa.Column("source_urls", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("email", sa.String(320)),
        sa.Column("email_status", sa.String(12), nullable=False),
        sa.Column("email_source_url", sa.Text()),
        sa.Column("synthetic", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("company_id", "name_key"),
    )
    op.create_index("ix_contact_company_id", "contact", ["company_id"])
    op.create_table(
        "prospect",
        *_base(),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaign.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contact.id", ondelete="CASCADE"), nullable=False),
        sa.Column("short_id", sa.String(8), nullable=False, unique=True),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("pick_reason", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("assigned_rep_id", postgresql.UUID(as_uuid=True)),
        sa.Column("meeting_booked_at", sa.DateTime(timezone=True)),
        sa.Column("meeting_synthetic", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("campaign_id", "contact_id"),
    )
    op.create_index("ix_prospect_campaign_id", "prospect", ["campaign_id"])


def downgrade() -> None:
    op.drop_table("prospect")
    op.drop_table("contact")
