from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from covora.api.deps import get_session
from covora.api.routes.campaigns import get_campaign_or_404
from covora.exports import to_csv
from covora.prospects_queries import campaign_companies, campaign_prospects, facts_summaries

router = APIRouter()

COMPANY_COLUMNS = [
    "company",
    "domain",
    "status",
    "fit_score",
    "confidence",
    "reason",
    "wave",
    "industry",
    "location",
    "employee_count",
    "synthetic",
]
PROSPECT_COLUMNS = [
    "company",
    "domain",
    "contact",
    "title",
    "role",
    "confidence",
    "pick_reason",
    "email",
    "email_status",
    "linkedin_url",
    "source_urls",
    "synthetic",
]


def _csv(body: str, kind: str, campaign_id: UUID) -> Response:
    filename = f"{kind}-{str(campaign_id)[:8]}.csv"
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/exports/companies.csv")
async def export_companies(campaign_id: UUID, session: AsyncSession = Depends(get_session)) -> Response:
    await get_campaign_or_404(session, campaign_id)
    rows = await campaign_companies(session, campaign_id)
    summaries = await facts_summaries(session, [co.id for _, co in rows])
    body = to_csv(
        COMPANY_COLUMNS,
        (
            [
                co.name,
                co.domain,
                cc.status,
                cc.fit_score,
                cc.confidence,
                cc.reason,
                cc.wave,
                summaries.get(co.id, {}).get("industry"),
                summaries.get(co.id, {}).get("location"),
                summaries.get(co.id, {}).get("employee_count"),
                co.synthetic,
            ]
            for cc, co in rows
        ),
    )
    return _csv(body, "companies", campaign_id)


@router.get("/exports/prospects.csv")
async def export_prospects(campaign_id: UUID, session: AsyncSession = Depends(get_session)) -> Response:
    await get_campaign_or_404(session, campaign_id)
    body = to_csv(
        PROSPECT_COLUMNS,
        (
            [
                co.name,
                co.domain,
                c.full_name,
                c.title,
                p.role,
                p.confidence,
                p.pick_reason,
                c.email,
                c.email_status,
                c.linkedin_url,
                c.source_urls,
                co.synthetic,
            ]
            for p, c, co in await campaign_prospects(session, campaign_id)
        ),
    )
    return _csv(body, "prospects", campaign_id)
