from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from covora.campaigns.models import DEFAULT_PROGRESS, Campaign
from covora.discovery.models import CampaignCompany
from covora.icp.models import IcpVersion
from covora.observability.models import WorkflowRun
from covora.qualification.models import Prospect
from covora.workspace.settings import Goals

FUNNEL_KEYS = ("candidates", "qualified", "rejected", "needs_review", "with_contacts", "prospects", "no_contact")


async def create_campaign(
    session: AsyncSession, *, workspace_id: UUID, icp: IcpVersion, name: str, goals: Goals, target_prospects: int
) -> Campaign:
    campaign = Campaign(
        workspace_id=workspace_id,
        name=name,
        icp_version_id=icp.id,
        version=1,
        config_snapshot={"icp": icp.structured, "icp_version": icp.version},
        goal=goals.model_dump(mode="json"),
        target_prospects=target_prospects,
        status="draft",
        progress=dict(DEFAULT_PROGRESS),
    )
    session.add(campaign)
    await session.flush()
    campaign.root_campaign_id = campaign.id
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def campaign_funnel(session: AsyncSession, campaign_id: UUID) -> dict[str, int]:
    statuses = dict(
        (
            await session.execute(
                select(CampaignCompany.status, func.count())
                .where(CampaignCompany.campaign_id == campaign_id)
                .group_by(CampaignCompany.status)
            )
        ).all()
    )
    primaries = (
        await session.execute(
            select(func.count())
            .select_from(Prospect)
            .where(Prospect.campaign_id == campaign_id, Prospect.role == "primary")
        )
    ).scalar_one()
    return {
        "candidates": sum(statuses.values()),
        "qualified": sum(statuses.get(k, 0) for k in ("qualified", "contact_selected", "no_contact")),
        "rejected": statuses.get("rejected", 0),
        "needs_review": statuses.get("needs_review", 0),
        "with_contacts": statuses.get("contact_selected", 0),
        "prospects": primaries,
        "no_contact": statuses.get("no_contact", 0),
    }


async def latest_run_id(session: AsyncSession, campaign_id: UUID) -> UUID | None:
    stmt = (
        select(WorkflowRun.id)
        .where(WorkflowRun.campaign_id == campaign_id)
        .order_by(WorkflowRun.started_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()
