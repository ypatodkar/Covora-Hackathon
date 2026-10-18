"""Outreach steps the campaign graph calls: arms, drafting batches, approval release, queueing."""

from uuid import UUID

from sqlalchemy import func, select

from covora.campaigns.models import Campaign
from covora.concurrency import bounded_gather
from covora.discovery.models import CampaignCompany
from covora.observability.tracing import RunContext
from covora.outreach.arms import arm_for, campaign_arms, create_arms
from covora.outreach.drafts import draft_email
from covora.outreach.models import EmailMessage
from covora.outreach.templates import sync_templates
from covora.qualification.models import Prospect
from covora.services import Services

CONCURRENCY = 4


async def set_arms(services: Services, campaign_id: UUID) -> int:
    async with services.sessionmaker() as s:
        campaign = await s.get(Campaign, campaign_id)
        arms = await campaign_arms(s, campaign_id)
        if not arms:
            await sync_templates(s, campaign.workspace_id)
            await create_arms(s, campaign, None)
            arms = await campaign_arms(s, campaign_id)
        keys = [arm.key for arm, _ in arms]
        prospects = list(
            (
                await s.execute(select(Prospect).where(Prospect.campaign_id == campaign_id, Prospect.arm_key.is_(None)))
            ).scalars()
        )
        for p in prospects:
            p.arm_key = arm_for(p.id, keys)
        await s.commit()
        return len(prospects)


async def primaries_in_order(services: Services, campaign_id: UUID) -> list[UUID]:
    """Primary prospects that have no cold email yet, best-ranked company first."""
    drafted = select(EmailMessage.prospect_id).where(
        EmailMessage.campaign_id == campaign_id, EmailMessage.kind == "cold"
    )
    stmt = (
        select(Prospect.id)
        .join(
            CampaignCompany,
            (CampaignCompany.company_id == Prospect.company_id) & (CampaignCompany.campaign_id == campaign_id),
        )
        .where(Prospect.campaign_id == campaign_id, Prospect.role == "primary", Prospect.id.not_in(drafted))
        .order_by(CampaignCompany.rank.nulls_last(), Prospect.created_at)
    )
    async with services.sessionmaker() as s:
        return list((await s.execute(stmt)).scalars())


async def draft_batch(services: Services, prospect_ids: list[UUID], *, ctx: RunContext) -> list[EmailMessage]:
    return await bounded_gather(
        [lambda pid=pid: draft_email(pid, ctx=ctx, services=services) for pid in prospect_ids], CONCURRENCY
    )


async def release(services: Services, campaign_id: UUID, decision: dict) -> dict[str, int]:
    approved = {UUID(i) for i in decision.get("approved", [])}
    rejected = {UUID(i) for i in decision.get("rejected", [])}
    counts = {"queued": 0, "rejected": 0}
    async with services.sessionmaker() as s:
        emails = (
            await s.execute(
                select(EmailMessage).where(
                    EmailMessage.campaign_id == campaign_id,
                    EmailMessage.kind == "cold",
                    EmailMessage.status.in_(("draft", "needs_review")),
                )
            )
        ).scalars()
        for email in emails:
            if email.id in rejected:
                email.status = "rejected"
                (await s.get(Prospect, email.prospect_id)).status = "skipped"
                counts["rejected"] += 1
            elif email.id in approved:
                email.status = "queued"
                (await s.get(Prospect, email.prospect_id)).status = "queued"
                counts["queued"] += 1
        await s.commit()
    return counts


async def queue_drafts(services: Services, campaign_id: UUID) -> int:
    """After the first batch is approved, later drafts go straight to the queue (spec §8.1)."""
    async with services.sessionmaker() as s:
        emails = (
            await s.execute(
                select(EmailMessage).where(
                    EmailMessage.campaign_id == campaign_id, EmailMessage.kind == "cold", EmailMessage.status == "draft"
                )
            )
        ).scalars()
        count = 0
        for email in emails:
            email.status = "queued"
            (await s.get(Prospect, email.prospect_id)).status = "queued"
            count += 1
        await s.commit()
    return count


async def status_after_release(services: Services, campaign_id: UUID) -> str:
    async with services.sessionmaker() as s:
        pending = (
            await s.execute(
                select(func.count()).where(
                    EmailMessage.campaign_id == campaign_id,
                    EmailMessage.direction == "out",
                    EmailMessage.status.in_(("queued", "sending")),
                )
            )
        ).scalar_one()
    return "sending" if pending else "complete"
