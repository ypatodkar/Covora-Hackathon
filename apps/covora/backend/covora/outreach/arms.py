"""A/B arms: each campaign version compares two templates; prospects are split by a stable hash (spec §14.4)."""

import hashlib
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from covora.campaigns.models import Campaign
from covora.outreach.models import CampaignArm, Template
from covora.outreach.templates import pick_default_templates
from covora.workspace.models import Workspace

ARM_KEYS = ["A", "B"]


def arm_for(prospect_id: UUID, keys: list[str]) -> str:
    digest = int(hashlib.sha256(str(prospect_id).encode()).hexdigest(), 16)
    return keys[digest % len(keys)]


async def create_arms(session: AsyncSession, campaign: Campaign, template_ids: list[UUID] | None) -> list[CampaignArm]:
    if template_ids:
        templates = [await session.get(Template, tid) for tid in template_ids]
        if any(t is None or t.workspace_id != campaign.workspace_id for t in templates):
            raise LookupError("unknown template")
    else:
        workspace = await session.get(Workspace, campaign.workspace_id)
        templates = await pick_default_templates(session, campaign.workspace_id, workspace.offering_type)
    arms = [
        CampaignArm(campaign_id=campaign.id, key=key, template_id=t.id)
        for key, t in zip(ARM_KEYS, templates, strict=True)
    ]
    session.add_all(arms)
    await session.commit()
    return arms


async def campaign_arms(session: AsyncSession, campaign_id: UUID) -> list[tuple[CampaignArm, Template]]:
    stmt = (
        select(CampaignArm, Template)
        .join(Template, Template.id == CampaignArm.template_id)
        .where(CampaignArm.campaign_id == campaign_id)
        .order_by(CampaignArm.key)
    )
    return list((await session.execute(stmt)).all())
