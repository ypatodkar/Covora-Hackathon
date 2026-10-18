"""Enrichment and fit: gather sourced facts per company, judge each ICP criterion, score in code (spec §9.2–9.3)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from covora.agents.messages import json_messages
from covora.agents.step import run_step
from covora.campaigns.models import Campaign
from covora.concurrency import bounded_gather
from covora.discovery.criteria import fit_score, icp_criteria
from covora.discovery.domains import normalize_domain
from covora.discovery.models import CampaignCompany, Company, Fact
from covora.discovery.schemas import ExtractedFacts, FitJudgment
from covora.discovery.validate import validate_facts
from covora.gateway.tasks import TaskType
from covora.icp.schemas import StructuredICP
from covora.memory.prompts import get_prompt
from covora.memory.store import MemoryQuery
from covora.observability.tracing import RunContext, span
from covora.research.provider import BudgetExceeded, ResearchError
from covora.services import Services
from covora.workspace.models import Workspace

FACT_FRESH_DAYS = 30
PAGE_CHARS = 8000
CONCURRENCY = 4


async def _gather_pages(company: Company, *, ctx: RunContext, services: Services) -> dict[str, str]:
    """Text the fact agent may read: the company's own pages, plus search results that name the company."""
    domain = company.domain
    pages: dict[str, str] = {}
    results = await services.research.search(f'"{company.name}" {domain} employees', count=5, ctx=ctx)
    for r in results:
        own = normalize_domain(r.url) == domain
        mentions = company.name.lower() in r.text().lower() or domain in r.text().lower()
        if own or mentions:
            pages[r.url] = r.text()[:PAGE_CHARS]
    for page in await services.research.contents([f"https://{domain}/", f"https://{domain}/about"], ctx=ctx):
        pages[page.url] = f"{page.title}\n{page.markdown}"[:PAGE_CHARS]
    return pages


async def _company_facts(company: Company, *, ctx: RunContext, services: Services, prompt: str) -> list[Fact]:
    cutoff = datetime.now(UTC) - timedelta(days=FACT_FRESH_DAYS)
    async with services.sessionmaker() as s:
        fresh = list(
            (await s.execute(select(Fact).where(Fact.company_id == company.id, Fact.retrieved_at >= cutoff))).scalars()
        )
    if fresh:
        return fresh  # semantic memory still fresh: no new research (spec §7.3)

    pages = await _gather_pages(company, ctx=ctx, services=services)
    if not pages:
        return []
    inputs = {
        "company": {"name": company.name, "domain": company.domain},
        "pages": [{"url": u, "text": t} for u, t in pages.items()],
    }
    step = await run_step(
        ctx=ctx,
        gateway=services.gateway,
        memory=services.memory,
        settings=services.settings,
        agent="enrichment",
        task=TaskType.fact_extraction,
        goal="Extract facts about this company, each with its source and an exact quote",
        inputs=inputs,
        queries=[],
        build_messages=json_messages(prompt, inputs),
        schema=ExtractedFacts,
    )
    facts = [
        Fact(
            company_id=company.id,
            field=f.field,
            value=f.value,
            source_url=f.source_url,
            quote=f.quote,
            label=f.label,
            retrieved_at=datetime.now(UTC),
        )
        for f in validate_facts(step.output.facts, pages)
    ]
    async with services.sessionmaker() as s:
        s.add_all(facts)
        await s.commit()
    return facts


async def _judge(
    company: Company,
    facts: list[Fact],
    *,
    criteria,
    icp: StructuredICP,
    offering: dict,
    ctx: RunContext,
    services: Services,
    prompt: str,
) -> tuple[list[dict], int, str, str]:
    inputs = {
        "company": {"name": company.name, "domain": company.domain},
        "criteria": [
            {"name": c.name, "description": c.description, "hard": c.hard, "stated": c.stated, "kind": c.kind}
            for c in criteria
        ],
        "facts": [
            {"id": str(f.id), "field": f.field, "value": f.value, "label": f.label, "source_url": f.source_url}
            for f in facts
        ],
        "offering": offering,
    }
    step = await run_step(
        ctx=ctx,
        gateway=services.gateway,
        memory=services.memory,
        settings=services.settings,
        agent="fit",
        task=TaskType.company_fit,
        goal="Judge each ICP criterion for this company from its facts",
        inputs=inputs,
        queries=[
            MemoryQuery(
                "semantic", ["insight"], "real", icp.summary, "segment insights", filters={"dimension": "segment"}, k=3
            )
        ],
        build_messages=json_messages(prompt, inputs),
        schema=FitJudgment,
    )
    judged = {j.criterion: j for j in step.output.criteria}
    own_ids = {str(f.id) for f in facts}
    rows, statuses = [], {}
    for c in criteria:
        j = judged.get(c.name)
        status = j.status if j else "unknown"
        statuses[c.name] = status
        rows.append(
            {"name": c.name, "status": status, "fact_ids": [i for i in (j.fact_ids if j else []) if i in own_ids]}
        )
    return rows, fit_score(criteria, statuses), step.output.confidence, step.output.reason


async def enrich_and_score(
    campaign_id: UUID, company_ids: list[UUID], *, ctx: RunContext, services: Services
) -> list[UUID]:
    async with services.sessionmaker() as s:
        campaign = await s.get(Campaign, campaign_id)
        workspace = await s.get(Workspace, campaign.workspace_id)
        icp = StructuredICP.model_validate(campaign.config_snapshot["icp"])
        fact_prompt = (await get_prompt(s, "fact_extraction")).body
        fit_prompt = (await get_prompt(s, "company_fit")).body
        rows = (
            await s.execute(
                select(CampaignCompany, Company)
                .join(Company, Company.id == CampaignCompany.company_id)
                .where(CampaignCompany.campaign_id == campaign_id, CampaignCompany.company_id.in_(company_ids))
            )
        ).all()
    criteria = icp_criteria(icp)
    offering = {"type": workspace.offering_type, "description": workspace.description or ""}
    todo = [(cc, company) for cc, company in rows if cc.status == "candidate"]  # idempotent on resume

    async def score_one(cc: CampaignCompany, company: Company) -> UUID | None:
        async with span(ctx, f"score:{company.domain}", "stage", {"company": company.domain}) as sp:
            try:
                facts = await _company_facts(company, ctx=sp.ctx, services=services, prompt=fact_prompt)
            except BudgetExceeded:
                raise
            except ResearchError as exc:
                await _update(services, cc.id, status="needs_review", reason=f"Couldn't gather facts: {exc}")
                return None
            criteria_rows, score, confidence, reason = await _judge(
                company,
                facts,
                criteria=criteria,
                icp=icp,
                offering=offering,
                ctx=sp.ctx,
                services=services,
                prompt=fit_prompt,
            )
            qualified = score >= services.settings.min_fit_score
            await _update(
                services,
                cc.id,
                status="qualified" if qualified else "rejected",
                criteria=criteria_rows,
                fit_score=score,
                confidence=confidence,
                reason=reason,
            )
            sp.set("fit_score", score)
            return company.id if qualified else None

    results = await bounded_gather([lambda cc=cc, co=co: score_one(cc, co) for cc, co in todo], CONCURRENCY)
    await _rerank(services, campaign_id)
    return [company_id for company_id in results if company_id is not None]


async def _update(services: Services, campaign_company_id: UUID, **values) -> None:
    async with services.sessionmaker() as s:
        row = await s.get(CampaignCompany, campaign_company_id)
        for key, value in values.items():
            setattr(row, key, value)
        await s.commit()


async def _rerank(services: Services, campaign_id: UUID) -> None:
    async with services.sessionmaker() as s:
        qualified = (
            await s.execute(
                select(CampaignCompany)
                .where(CampaignCompany.campaign_id == campaign_id, CampaignCompany.status == "qualified")
                .order_by(CampaignCompany.fit_score.desc(), CampaignCompany.created_at)
            )
        ).scalars()
        for rank, row in enumerate(qualified, start=1):
            row.rank = rank
        await s.commit()
