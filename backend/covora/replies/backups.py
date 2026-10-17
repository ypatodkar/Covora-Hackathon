"""Backup contacts: used when the primary bounces, says "wrong person", or doesn't reply in time (spec §11)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from covora.campaigns.models import Campaign
from covora.observability.tracing import RunContext, finish_run, start_run
from covora.outreach.drafts import draft_email
from covora.outreach.models import EmailMessage
from covora.qualification.models import Prospect
from covora.services import Services
from covora.workspace.models import Workspace
from covora.workspace.settings import get_workspace_settings


async def activate_backup(primary_id: UUID, *, ctx: RunContext, services: Services) -> UUID | None:
    async with services.sessionmaker() as s:
        primary = await s.get(Prospect, primary_id)
        backup = (
            (
                await s.execute(
                    select(Prospect).where(
                        Prospect.campaign_id == primary.campaign_id,
                        Prospect.company_id == primary.company_id,
                        Prospect.role == "backup",
                    )
                )
            )
            .scalars()
            .first()
        )
        if backup is None:
            return None
        already = (
            await s.execute(
                select(EmailMessage.id).where(EmailMessage.prospect_id == backup.id, EmailMessage.kind == "cold")
            )
        ).first()
        if already:
            return None  # once only
    email = await draft_email(backup.id, ctx=ctx, services=services)
    async with services.sessionmaker() as s:
        row = await s.get(EmailMessage, email.id)
        if row.status == "draft":
            row.status = "queued"
            (await s.get(Prospect, backup.id)).status = "queued"
        await s.commit()
    return email.id


async def activate_due_backups(services: Services) -> int:
    """Primaries with no reply after the workspace's window get their backup contacted."""
    async with services.sessionmaker() as s:
        rows = (
            await s.execute(
                select(Prospect, EmailMessage, Campaign)
                .join(EmailMessage, (EmailMessage.prospect_id == Prospect.id) & (EmailMessage.kind == "cold"))
                .join(Campaign, Campaign.id == Prospect.campaign_id)
                .where(Prospect.role == "primary", Prospect.status == "sent", EmailMessage.status == "sent")
            )
        ).all()
    activated = 0
    for prospect, email, campaign in rows:
        async with services.sessionmaker() as s:
            window = get_workspace_settings(
                await s.get(Workspace, campaign.workspace_id)
            ).sending.no_reply_window_minutes
            replied = (
                await s.execute(
                    select(EmailMessage.id).where(
                        EmailMessage.prospect_id == prospect.id, EmailMessage.direction == "in"
                    )
                )
            ).first()
        if replied or email.sent_at is None or email.sent_at > datetime.now(UTC) - timedelta(minutes=window):
            continue
        async with services.sessionmaker() as s:
            (await s.get(Prospect, prospect.id)).status = "no_reply"
            await s.commit()
        ctx = await start_run(
            services.sessionmaker,
            kind="reply",
            workspace_id=campaign.workspace_id,
            secrets=services.settings.secret_values(),
            campaign_id=campaign.id,
        )
        if await activate_backup(prospect.id, ctx=ctx, services=services):
            activated += 1
        await finish_run(ctx, status="succeeded")
    return activated
