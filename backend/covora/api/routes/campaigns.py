from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from covora.api.deps import Services, get_services, get_session
from covora.api.errors import ApiError
from covora.campaigns.models import Campaign
from covora.campaigns.service import campaign_funnel, create_campaign, latest_run_id
from covora.campaigns.sizing import CostModel, SizingEstimate, estimate_campaign, measured_cost_model
from covora.icp.models import IcpVersion
from covora.jobs.queue import enqueue
from covora.research.budget import spend
from covora.workspace.service import ensure_workspace
from covora.workspace.settings import Goals, get_workspace_settings

router = APIRouter()


class EstimateRequest(Goals):
    prospect_limit: int | None = Field(None, ge=1)


class CreateCampaignRequest(BaseModel):
    icp_version_id: UUID
    name: str = Field(min_length=1, max_length=200)
    goals: Goals = Goals()
    prospect_limit: int | None = Field(None, ge=1)


class CampaignOut(BaseModel):
    id: UUID
    name: str
    status: str
    icp_version_id: UUID
    goal: dict[str, Any]
    target_prospects: int
    progress: dict[str, Any]
    last_error: str | None
    created_at: datetime
    funnel: dict[str, int]
    latest_run_id: UUID | None


async def campaign_out(session: AsyncSession, c: Campaign) -> CampaignOut:
    return CampaignOut(
        id=c.id,
        name=c.name,
        status=c.status,
        icp_version_id=c.icp_version_id,
        goal=c.goal,
        target_prospects=c.target_prospects,
        progress=c.progress,
        last_error=c.last_error,
        created_at=c.created_at,
        funnel=await campaign_funnel(session, c.id),
        latest_run_id=await latest_run_id(session, c.id),
    )


async def _estimate(
    session: AsyncSession, services: Services, goals: Goals, prospect_limit: int | None
) -> SizingEstimate:
    ws = await ensure_workspace(session)
    remaining = services.settings.youcom_budget_usd - await spend(services.sessionmaker, ws.id)
    return estimate_campaign(
        goals,
        prospect_limit=prospect_limit,
        cost=await measured_cost_model(session, ws.id) or CostModel(),
        search_price=services.settings.youcom_search_price_usd,
        page_price=services.settings.youcom_contents_price_usd,
        budget_remaining=remaining,
        daily_gmail_cap=get_workspace_settings(ws).sending.daily_gmail_cap,
    )


async def get_campaign_or_404(session: AsyncSession, campaign_id: UUID) -> Campaign:
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        raise ApiError("not_found", "That campaign does not exist.", 404)
    return campaign


@router.post("/campaigns/estimate")
async def estimate(
    body: EstimateRequest, services: Services = Depends(get_services), session: AsyncSession = Depends(get_session)
) -> SizingEstimate:
    goals = Goals.model_validate(body.model_dump(exclude={"prospect_limit"}))
    return await _estimate(session, services, goals, body.prospect_limit)


@router.post("/campaigns")
async def create(
    body: CreateCampaignRequest,
    services: Services = Depends(get_services),
    session: AsyncSession = Depends(get_session),
) -> CampaignOut:
    ws = await ensure_workspace(session)
    icp = await session.get(IcpVersion, body.icp_version_id)
    if icp is None:
        raise ApiError("not_found", "That ICP version does not exist.", 404)
    sizing = await _estimate(session, services, body.goals, body.prospect_limit)
    campaign = await create_campaign(
        session,
        workspace_id=ws.id,
        icp=icp,
        name=body.name,
        goals=body.goals,
        target_prospects=sizing.prospects_planned,
    )
    return await campaign_out(session, campaign)


@router.get("/campaigns")
async def list_campaigns(session: AsyncSession = Depends(get_session)) -> list[CampaignOut]:
    ws = await ensure_workspace(session)
    rows = await session.execute(
        select(Campaign).where(Campaign.workspace_id == ws.id).order_by(Campaign.created_at.desc())
    )
    return [await campaign_out(session, c) for c in rows.scalars()]


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: UUID, session: AsyncSession = Depends(get_session)) -> CampaignOut:
    return await campaign_out(session, await get_campaign_or_404(session, campaign_id))


async def _enqueue_run(session: AsyncSession, campaign: Campaign, *, resume: bool) -> None:
    from covora.graphs.jobs import JOB_KIND  # local import: keeps the API importable without the graph

    campaign.status = "queued"
    campaign.last_error = None
    await session.commit()
    await enqueue(session, JOB_KIND, {"campaign_id": str(campaign.id), "resume": resume}, max_attempts=1)


@router.post("/campaigns/{campaign_id}/run")
async def run_campaign(campaign_id: UUID, session: AsyncSession = Depends(get_session)) -> CampaignOut:
    campaign = await get_campaign_or_404(session, campaign_id)
    if campaign.status != "draft":
        raise ApiError("invalid_state", f"A campaign can only be started from draft (it is {campaign.status}).", 409)
    await _enqueue_run(session, campaign, resume=False)
    return await campaign_out(session, campaign)


@router.post("/campaigns/{campaign_id}/retry")
async def retry_campaign(campaign_id: UUID, session: AsyncSession = Depends(get_session)) -> CampaignOut:
    campaign = await get_campaign_or_404(session, campaign_id)
    if campaign.status != "failed":
        raise ApiError("invalid_state", f"Only a failed campaign can be retried (it is {campaign.status}).", 409)
    await _enqueue_run(session, campaign, resume=True)
    return await campaign_out(session, campaign)
