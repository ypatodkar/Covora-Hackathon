"""Query helpers shared by tests (kept out of conftest so tests can import them)."""

from uuid import UUID

from sqlalchemy import select

from covora.observability.models import LlmCall, Span, WorkflowRun


async def fetch_spans(sessionmaker, run_id: UUID) -> list[Span]:
    async with sessionmaker() as s:
        return list((await s.execute(select(Span).where(Span.run_id == run_id).order_by(Span.started_at))).scalars())


async def get_run(sessionmaker, run_id: UUID) -> WorkflowRun:
    async with sessionmaker() as s:
        return (await s.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))).scalar_one()


async def count_memory_reads(sessionmaker, span_id: UUID) -> int:
    from sqlalchemy import func

    from covora.memory.models import MemoryRead

    async with sessionmaker() as s:
        stmt = select(func.count()).select_from(MemoryRead).where(MemoryRead.span_id == span_id)
        return (await s.execute(stmt)).scalar_one()


async def latest_llm_call(sessionmaker) -> LlmCall:
    async with sessionmaker() as s:
        return (await s.execute(select(LlmCall).order_by(LlmCall.created_at.desc()).limit(1))).scalar_one()


async def set_locked_at(sessionmaker, job_id: UUID, when) -> None:
    from sqlalchemy import update

    from covora.jobs.models import Job

    async with sessionmaker() as s:
        await s.execute(update(Job).where(Job.id == job_id).values(locked_at=when))
        await s.commit()


async def get_job(sessionmaker, *, kind: str):
    from covora.jobs.models import Job

    async with sessionmaker() as s:
        return (
            await s.execute(select(Job).where(Job.kind == kind).order_by(Job.created_at.desc()).limit(1))
        ).scalar_one()


async def latest_tool_call(sessionmaker):
    from covora.research.models import ToolCall

    async with sessionmaker() as s:
        return (await s.execute(select(ToolCall).order_by(ToolCall.created_at.desc()).limit(1))).scalar_one()


async def count_tool_calls(sessionmaker, operation: str | None = None) -> int:
    from sqlalchemy import func

    from covora.research.models import ToolCall

    stmt = select(func.count()).select_from(ToolCall)
    if operation is not None:
        stmt = stmt.where(ToolCall.operation == operation)
    async with sessionmaker() as s:
        return (await s.execute(stmt)).scalar_one()


async def candidate_domains(sessionmaker, campaign_id: UUID) -> list[str]:
    from covora.discovery.models import CampaignCompany, Company

    stmt = (
        select(Company.domain)
        .join(CampaignCompany, CampaignCompany.company_id == Company.id)
        .where(CampaignCompany.campaign_id == campaign_id)
    )
    async with sessionmaker() as s:
        return list((await s.execute(stmt)).scalars())


async def campaign_companies_by_domain(sessionmaker, campaign_id: UUID) -> dict:
    from covora.discovery.models import CampaignCompany, Company

    stmt = (
        select(Company.domain, CampaignCompany)
        .join(CampaignCompany, CampaignCompany.company_id == Company.id)
        .where(CampaignCompany.campaign_id == campaign_id)
    )
    async with sessionmaker() as s:
        return dict((await s.execute(stmt)).all())


async def facts_for(sessionmaker, workspace_id: UUID, domain: str) -> list:
    from covora.discovery.models import Company, Fact

    stmt = (
        select(Fact)
        .join(Company, Fact.company_id == Company.id)
        .where(Company.workspace_id == workspace_id, Company.domain == domain)
    )
    async with sessionmaker() as s:
        return list((await s.execute(stmt)).scalars())


async def contacts_by_name(sessionmaker, workspace_id: UUID, domain: str) -> dict:
    from covora.discovery.models import Company
    from covora.qualification.models import Contact

    stmt = (
        select(Contact)
        .join(Company, Contact.company_id == Company.id)
        .where(Company.workspace_id == workspace_id, Company.domain == domain)
    )
    async with sessionmaker() as s:
        return {c.full_name: c for c in (await s.execute(stmt)).scalars()}


async def prospects_by_domain(sessionmaker, campaign_id: UUID) -> dict:
    from collections import defaultdict

    from covora.discovery.models import Company
    from covora.qualification.models import Prospect

    stmt = select(Company.domain, Prospect).join(Company, Prospect.company_id == Company.id)
    stmt = stmt.where(Prospect.campaign_id == campaign_id)
    out: dict = defaultdict(list)
    async with sessionmaker() as s:
        for domain, prospect in (await s.execute(stmt)).all():
            out[domain].append(prospect)
    return dict(out)
