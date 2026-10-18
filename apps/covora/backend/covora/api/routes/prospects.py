from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from covora.api.deps import get_session
from covora.api.errors import ApiError
from covora.api.routes.campaigns import get_campaign_or_404
from covora.discovery.models import CampaignCompany, Company, Fact
from covora.prospects_queries import campaign_companies, campaign_prospects, facts_summaries
from covora.qualification.models import Contact, Prospect

router = APIRouter()


class CompanyRow(BaseModel):
    company_id: UUID
    name: str
    domain: str
    status: str
    fit_score: int | None
    confidence: str | None
    reason: str | None
    wave: int
    criteria: list[dict[str, Any]]
    synthetic: bool
    facts_summary: dict[str, str]


class ContactOut(BaseModel):
    id: UUID
    full_name: str
    title: str
    function: str
    seniority: str
    email: str | None
    email_status: str
    linkedin_url: str | None
    source_urls: list[str]
    synthetic: bool


class CompanyRef(BaseModel):
    id: UUID
    name: str
    domain: str


class ProspectRow(BaseModel):
    prospect_id: UUID
    short_id: str
    role: str
    status: str
    confidence: str
    pick_reason: str
    company: CompanyRef
    contact: ContactOut
    synthetic: bool


class FactOut(BaseModel):
    field: str
    value: Any
    label: str
    source_url: str
    quote: str
    retrieved_at: datetime


def contact_out(c: Contact) -> ContactOut:
    return ContactOut.model_validate(c, from_attributes=True)


@router.get("/campaigns/{campaign_id}/companies")
async def list_companies(campaign_id: UUID, session: AsyncSession = Depends(get_session)) -> list[CompanyRow]:
    await get_campaign_or_404(session, campaign_id)
    rows = await campaign_companies(session, campaign_id)
    summaries = await facts_summaries(session, [co.id for _, co in rows])
    return [
        CompanyRow(
            company_id=co.id,
            name=co.name,
            domain=co.domain,
            status=cc.status,
            fit_score=cc.fit_score,
            confidence=cc.confidence,
            reason=cc.reason,
            wave=cc.wave,
            criteria=cc.criteria or [],
            synthetic=co.synthetic,
            facts_summary=summaries.get(co.id, {}),
        )
        for cc, co in rows
    ]


@router.get("/campaigns/{campaign_id}/prospects")
async def list_prospects(campaign_id: UUID, session: AsyncSession = Depends(get_session)) -> list[ProspectRow]:
    await get_campaign_or_404(session, campaign_id)
    return [
        ProspectRow(
            prospect_id=p.id,
            short_id=p.short_id,
            role=p.role,
            status=p.status,
            confidence=p.confidence,
            pick_reason=p.pick_reason,
            company=CompanyRef(id=co.id, name=co.name, domain=co.domain),
            contact=contact_out(c),
            synthetic=co.synthetic,
        )
        for p, c, co in await campaign_prospects(session, campaign_id)
    ]


@router.get("/companies/{company_id}")
async def company_detail(company_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    company = await session.get(Company, company_id)
    if company is None:
        raise ApiError("not_found", "That company does not exist.", 404)
    facts = (await session.execute(select(Fact).where(Fact.company_id == company_id).order_by(Fact.field))).scalars()
    contacts = (await session.execute(select(Contact).where(Contact.company_id == company_id))).scalars()
    campaigns = (
        await session.execute(select(CampaignCompany).where(CampaignCompany.company_id == company_id))
    ).scalars()
    return {
        "company": CompanyRef(id=company.id, name=company.name, domain=company.domain).model_dump(mode="json")
        | {"synthetic": company.synthetic},
        "facts": [FactOut.model_validate(f, from_attributes=True).model_dump(mode="json") for f in facts],
        "contacts": [contact_out(c).model_dump(mode="json") for c in contacts],
        "campaigns": [
            {
                "campaign_id": str(cc.campaign_id),
                "status": cc.status,
                "fit_score": cc.fit_score,
                "reason": cc.reason,
                "criteria": cc.criteria,
            }
            for cc in campaigns
        ],
    }


@router.get("/contacts/{contact_id}")
async def contact_detail(contact_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    contact = await session.get(Contact, contact_id)
    if contact is None:
        raise ApiError("not_found", "That contact does not exist.", 404)
    company = await session.get(Company, contact.company_id)
    prospects = (await session.execute(select(Prospect).where(Prospect.contact_id == contact_id))).scalars()
    return {
        "contact": contact_out(contact).model_dump(mode="json"),
        "company": CompanyRef(id=company.id, name=company.name, domain=company.domain).model_dump(mode="json"),
        "prospects": [
            {
                "campaign_id": str(p.campaign_id),
                "role": p.role,
                "status": p.status,
                "pick_reason": p.pick_reason,
                "confidence": p.confidence,
            }
            for p in prospects
        ],
    }
