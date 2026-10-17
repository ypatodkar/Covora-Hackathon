"""Find named people at qualified companies (spec §9.4)."""

from uuid import UUID

from sqlalchemy import select

from covora.agents.messages import json_messages
from covora.agents.step import run_step
from covora.campaigns.models import Campaign
from covora.concurrency import bounded_gather
from covora.discovery.models import Company
from covora.gateway.tasks import TaskType
from covora.icp.schemas import StructuredICP
from covora.memory.prompts import get_prompt
from covora.observability.tracing import RunContext, span
from covora.qualification.models import Contact
from covora.qualification.schemas import ExtractedPeople
from covora.qualification.validate import classify_email, name_key, validate_people
from covora.research.provider import BudgetExceeded, ResearchError
from covora.services import Services

CONCURRENCY = 4
SOURCE_CHARS = 8000


def _functions(icp: StructuredICP) -> list[str]:
    return [t.value for t in icp.buyer_map.target_functions] or ["owner", "CEO"]


async def _sources(company: Company, functions: list[str], *, ctx: RunContext, services: Services) -> dict[str, str]:
    name, domain = company.name, company.domain
    wanted = " OR ".join(functions)
    first = (
        f'site:linkedin.com/in "{name}" {wanted}'
        if services.settings.youcom_site_operator
        else f'"{name}" {wanted} linkedin'
    )
    sources: dict[str, str] = {}
    for query in (first, f'"{name}" leadership team'):
        for r in await services.research.search(query, count=10, ctx=ctx):
            text = r.text()
            if name.lower() in text.lower() or domain in r.url:
                sources[r.url] = text[:SOURCE_CHARS]
    for page in await services.research.contents([f"https://{domain}/team", f"https://{domain}/about"], ctx=ctx):
        sources[page.url] = f"{page.title}\n{page.markdown}"[:SOURCE_CHARS]
    return sources


async def find_people(
    campaign_id: UUID, company_ids: list[UUID], *, ctx: RunContext, services: Services
) -> dict[UUID, int]:
    async with services.sessionmaker() as s:
        campaign = await s.get(Campaign, campaign_id)
        icp = StructuredICP.model_validate(campaign.config_snapshot["icp"])
        prompt = (await get_prompt(s, "people_extraction")).body
        companies = list((await s.execute(select(Company).where(Company.id.in_(company_ids)))).scalars())
    functions = _functions(icp)

    async def one(company: Company) -> tuple[UUID, int]:
        async with services.sessionmaker() as s:
            existing = list((await s.execute(select(Contact).where(Contact.company_id == company.id))).scalars())
        if existing:
            return company.id, len(existing)  # idempotent: already researched
        async with span(ctx, f"people:{company.domain}", "stage", {"company": company.domain}) as sp:
            try:
                sources = await _sources(company, functions, ctx=sp.ctx, services=services)
            except BudgetExceeded:
                raise
            except ResearchError as exc:
                sp.set("research_error", str(exc))
                return company.id, 0
            if not sources:
                return company.id, 0
            inputs = {
                "company": {"name": company.name, "domain": company.domain},
                "target_functions": functions,
                "sources": [{"url": u, "text": t} for u, t in sources.items()],
            }
            step = await run_step(
                ctx=sp.ctx,
                gateway=services.gateway,
                memory=services.memory,
                settings=services.settings,
                agent="people",
                task=TaskType.people_extraction,
                goal="List the people named in these sources, with their titles",
                inputs=inputs,
                queries=[],
                build_messages=json_messages(prompt, inputs),
                schema=ExtractedPeople,
            )
            linkedin_urls = {u for u in sources if "linkedin.com/in/" in u}
            people = validate_people(step.output.people, sources, linkedin_urls=linkedin_urls)
            contacts = []
            for person in people:
                email, status = classify_email(person.email, person.full_name, sources[person.source_url])
                urls = [person.source_url] + ([person.linkedin_url] if person.linkedin_url else [])
                contacts.append(
                    Contact(
                        company_id=company.id,
                        full_name=person.full_name,
                        name_key=name_key(person.full_name),
                        title=person.title,
                        function=person.function,
                        seniority=person.seniority,
                        linkedin_url=person.linkedin_url,
                        source_urls=urls,
                        email=email,
                        email_status=status,
                        email_source_url=person.source_url if email else None,
                        synthetic=company.synthetic,
                    )
                )
            async with services.sessionmaker() as s:
                s.add_all(contacts)
                await s.commit()
            sp.set("contacts", len(contacts))
            return company.id, len(contacts)

    pairs = await bounded_gather([lambda c=c: one(c) for c in companies], CONCURRENCY)
    return dict(pairs)
