"""The send loop (spec §11): claim queued mail, enforce suppression, deliver, schedule simulated replies."""

import random
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from covora.campaigns.models import Campaign
from covora.jobs.queue import enqueue
from covora.outreach.delivery import IN_APP_ADDRESS, choose_delivery
from covora.outreach.models import EmailMessage
from covora.outreach.suppression import is_suppressed, normalize_email
from covora.qualification.models import Prospect
from covora.services import Services
from covora.workspace.models import Workspace
from covora.workspace.settings import get_workspace_settings

SIM_REPLY_JOB = "sim.reply"

_CLAIM = text(
    """
    UPDATE email_message SET status = 'sending', updated_at = now()
     WHERE id IN (
        SELECT id FROM email_message
         WHERE direction = 'out' AND status = 'queued'
         ORDER BY created_at
         FOR UPDATE SKIP LOCKED
         LIMIT :limit)
    RETURNING id
    """
)


async def send_due(services: Services, *, limit: int = 20) -> int:
    async with services.sessionmaker() as s:
        ids = list((await s.execute(_CLAIM, {"limit": limit})).scalars())
        await s.commit()
    sent = 0
    for email_id in ids:
        sent += await _deliver(services, email_id)
    if ids:
        await complete_finished_campaigns(services)
    return sent


async def _deliver(services: Services, email_id: UUID) -> int:
    async with services.sessionmaker() as s:
        email = await s.get(EmailMessage, email_id)
        campaign = await s.get(Campaign, email.campaign_id)
        workspace = await s.get(Workspace, campaign.workspace_id)
        prospect = await s.get(Prospect, email.prospect_id)
        if await is_suppressed(s, workspace.id, email.intended_to):
            email.status = "suppressed"
            if email.kind == "cold":
                prospect.status = "suppressed"
            await s.commit()
            return 0
        ws_settings = get_workspace_settings(workspace)
        email.delivery = choose_delivery(services.settings, ws_settings, sent_today_gmail=0)
        email.actual_to = IN_APP_ADDRESS  # never the prospect's real address
        email.source = "in_app_sim"
        email.status = "sent"
        email.sent_at = datetime.now(UTC)
        if email.kind == "cold":
            prospect.status = "sent"
        await s.commit()
        if email.kind == "cold":
            low, high = [*ws_settings.simulation.reply_delay_seconds, 0, 0][:2]
            delay = random.uniform(min(low, high), max(low, high))
            await enqueue(
                s, SIM_REPLY_JOB, {"email_id": str(email.id)}, run_after=datetime.now(UTC) + timedelta(seconds=delay)
            )
    return 1


async def complete_finished_campaigns(services: Services) -> int:
    async with services.sessionmaker() as s:
        pending = (
            select(EmailMessage.campaign_id)
            .where(EmailMessage.direction == "out", EmailMessage.status.in_(("queued", "sending")))
            .distinct()
        )
        result = await s.execute(
            update(Campaign)
            .where(Campaign.status == "sending", Campaign.id.not_in(pending))
            .values(status="complete")
            .returning(Campaign.id)
        )
        done = len(result.all())
        await s.commit()
    return done


async def cancel_queued_to(session: AsyncSession, workspace_id: UUID, email: str) -> int:
    campaigns = select(Campaign.id).where(Campaign.workspace_id == workspace_id)
    result = await session.execute(
        update(EmailMessage)
        .where(
            EmailMessage.campaign_id.in_(campaigns),
            EmailMessage.direction == "out",
            EmailMessage.status.in_(("draft", "needs_review", "queued")),
            func.lower(func.trim(EmailMessage.intended_to)) == normalize_email(email),
        )
        .values(status="cancelled")
        .returning(EmailMessage.id)
    )
    count = len(result.all())
    await session.commit()
    return count


async def count_queued(session: AsyncSession, campaign_id: UUID) -> int:
    stmt = select(func.count()).where(EmailMessage.campaign_id == campaign_id, EmailMessage.status == "queued")
    return (await session.execute(stmt)).scalar_one()
