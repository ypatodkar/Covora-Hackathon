"""Read models for the Prospects page and exports."""

from uuid import UUID

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from covora.discovery.models import CampaignCompany, Company, Fact
from covora.qualification.models import Contact, Prospect

STATUS_ORDER = ["contact_selected", "qualified", "no_contact", "needs_review", "rejected", "candidate"]
SUMMARY_FIELDS = ("employee_count", "industry", "location")


async def facts_summaries(session: AsyncSession, company_ids: list[UUID]) -> dict[UUID, dict[str, str]]:
    if not company_ids:
        return {}
    rows = (
        await session.execute(
            select(Fact)
            .where(Fact.company_id.in_(company_ids), Fact.field.in_(SUMMARY_FIELDS))
            .order_by(Fact.retrieved_at.desc())
        )
    ).scalars()
    out: dict[UUID, dict[str, str]] = {}
    for fact in rows:
        out.setdefault(fact.company_id, {}).setdefault(fact.field, str(fact.value))
    return out


async def campaign_companies(session: AsyncSession, campaign_id: UUID) -> list[tuple[CampaignCompany, Company]]:
    order = case({s: i for i, s in enumerate(STATUS_ORDER)}, value=CampaignCompany.status, else_=len(STATUS_ORDER))
    stmt = (
        select(CampaignCompany, Company)
        .join(Company, Company.id == CampaignCompany.company_id)
        .where(CampaignCompany.campaign_id == campaign_id)
        .order_by(order, CampaignCompany.fit_score.desc().nulls_last(), Company.name)
    )
    return list((await session.execute(stmt)).all())


async def campaign_prospects(session: AsyncSession, campaign_id: UUID) -> list[tuple[Prospect, Contact, Company]]:
    stmt = (
        select(Prospect, Contact, Company)
        .join(Contact, Contact.id == Prospect.contact_id)
        .join(Company, Company.id == Prospect.company_id)
        .join(
            CampaignCompany, (CampaignCompany.company_id == Company.id) & (CampaignCompany.campaign_id == campaign_id)
        )
        .where(Prospect.campaign_id == campaign_id)
        .order_by(CampaignCompany.rank.nulls_last(), Company.name, case((Prospect.role == "primary", 0), else_=1))
    )
    return list((await session.execute(stmt)).all())
