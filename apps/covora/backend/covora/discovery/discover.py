"""One discovery wave: queries → You.com → extract companies → validate → candidates (spec §8.1, §9.2)."""

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from covora.agents.messages import json_messages
from covora.agents.step import run_step
from covora.campaigns.models import Campaign
from covora.discovery.models import CampaignCompany, Company
from covora.discovery.schemas import ExtractedCompanies, QueryPlan
from covora.discovery.validate import validate_companies
from covora.gateway.tasks import TaskType
from covora.icp.schemas import StructuredICP
from covora.memory.prompts import get_prompt
from covora.observability.tracing import RunContext
from covora.research.provider import BudgetExceeded, ResearchError, SearchResult
from covora.services import Services

RESULTS_PER_QUERY = 20
EXTRACTION_BATCH = 25


@dataclass
class WaveResult:
    queries: list[str]
    result_count: int
    new_company_ids: list[UUID]
    errors: list[str] = field(default_factory=list)


def icp_brief(icp: StructuredICP) -> dict:
    return icp.model_dump(
        mode="json",
        include={
            "summary",
            "industries",
            "locations",
            "employee_range",
            "revenue_range_usd",
            "other_criteria",
            "exclusions",
        },
    )


async def discover_wave(
    campaign_id: UUID, *, wave: int, ctx: RunContext, services: Services, limit: int | None = None
) -> WaveResult:
    settings = services.settings
    async with services.sessionmaker() as session:
        campaign = await session.get(Campaign, campaign_id)
        icp = StructuredICP.model_validate(campaign.config_snapshot["icp"])
        used = list(campaign.progress.get("used_queries", []))
        query_prompt = (await get_prompt(session, "query_generation")).body
        extraction_prompt = (await get_prompt(session, "company_extraction")).body

    queries = [q for q in icp.search_queries if q not in used] if wave == 1 else []
    if not queries:
        inputs = {"icp": icp_brief(icp), "used_queries": used, "wave": wave}
        plan = await run_step(
            ctx=ctx,
            gateway=services.gateway,
            memory=services.memory,
            settings=settings,
            agent="discovery",
            task=TaskType.query_generation,
            goal="Write new web searches that find company websites matching the ICP",
            inputs=inputs,
            queries=[],
            build_messages=json_messages(query_prompt, inputs),
            schema=QueryPlan,
        )
        queries = [q for q in plan.output.queries if q not in used]

    results: list[SearchResult] = []
    errors: list[str] = []
    for query in queries:
        try:
            results.extend(await services.research.search(query, count=RESULTS_PER_QUERY, ctx=ctx))
        except BudgetExceeded:
            raise
        except ResearchError as exc:
            errors.append(f"{query}: {exc}")
    unique = list({r.url: r for r in results}.values())

    extracted = []
    for start in range(0, len(unique), EXTRACTION_BATCH):
        batch = unique[start : start + EXTRACTION_BATCH]
        inputs = {
            "icp_summary": icp.summary,
            "results": [
                {"url": r.url, "title": r.title, "description": r.description, "snippets": r.snippets} for r in batch
            ],
        }
        step = await run_step(
            ctx=ctx,
            gateway=services.gateway,
            memory=services.memory,
            settings=settings,
            agent="discovery",
            task=TaskType.company_extraction,
            goal="List the companies whose own websites appear in these search results",
            inputs=inputs,
            queries=[],
            build_messages=json_messages(extraction_prompt, inputs),
            schema=ExtractedCompanies,
        )
        extracted.extend(step.output.companies)
    companies = validate_companies(extracted, unique, settings.research_blocklist_domains)

    synthetic = getattr(services.research, "name", "") == "mock"
    new_ids: list[UUID] = []
    async with services.sessionmaker() as session:
        campaign = await session.get(Campaign, campaign_id)
        linked = set(
            (
                await session.execute(
                    select(CampaignCompany.company_id).where(CampaignCompany.campaign_id == campaign_id)
                )
            ).scalars()
        )
        for found in companies:
            if len(new_ids) >= (limit or settings.max_candidates_per_wave):
                break
            await session.execute(
                insert(Company)
                .values(workspace_id=campaign.workspace_id, name=found.name, domain=found.domain, synthetic=synthetic)
                .on_conflict_do_nothing(index_elements=["workspace_id", "domain"])
            )
            company_id = (
                await session.execute(
                    select(Company.id).where(
                        Company.workspace_id == campaign.workspace_id, Company.domain == found.domain
                    )
                )
            ).scalar_one()
            if company_id in linked:
                continue
            session.add(
                CampaignCompany(
                    campaign_id=campaign_id,
                    company_id=company_id,
                    wave=wave,
                    source_url=found.source_url,
                    status="candidate",
                )
            )
            linked.add(company_id)
            new_ids.append(company_id)
        campaign.progress = {**campaign.progress, "used_queries": used + queries, "waves": wave}
        await session.commit()
    return WaveResult(queries=queries, result_count=len(unique), new_company_ids=new_ids, errors=errors)
