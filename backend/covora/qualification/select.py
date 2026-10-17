"""Pick the primary and backup contact per company (spec §9.4), and remember the pick (spec §7.2)."""

import contextlib
import secrets
from uuid import UUID

from sqlalchemy import select

from covora.agents.messages import json_messages
from covora.agents.step import run_step
from covora.campaigns.models import Campaign
from covora.concurrency import bounded_gather
from covora.discovery.models import CampaignCompany, Company, Fact
from covora.gateway.gateway import GatewayError
from covora.gateway.tasks import TaskType
from covora.icp.schemas import StructuredICP
from covora.memory.prompts import get_prompt
from covora.memory.store import MemoryQuery, NewMemory
from covora.observability.tracing import RunContext, span
from covora.qualification.models import Contact, Prospect
from covora.qualification.schemas import ContactSelection
from covora.qualification.validate import validate_selection
from covora.services import Services
from covora.workspace.models import Workspace

CONCURRENCY = 4
_DECIDED = {"contact_selected", "no_contact", "needs_review"}


def _latest(facts: list[Fact], field: str) -> str | None:
    values = sorted((f for f in facts if f.field == field), key=lambda f: f.retrieved_at, reverse=True)
    return str(values[0].value) if values else None


async def select_contacts(campaign_id: UUID, company_ids: list[UUID], *, ctx: RunContext, services: Services) -> int:
    async with services.sessionmaker() as s:
        campaign = await s.get(Campaign, campaign_id)
        workspace = await s.get(Workspace, campaign.workspace_id)
        icp = StructuredICP.model_validate(campaign.config_snapshot["icp"])
        prompt = (await get_prompt(s, "contact_selection")).body
        rows = (
            await s.execute(
                select(CampaignCompany, Company)
                .join(Company, Company.id == CampaignCompany.company_id)
                .where(CampaignCompany.campaign_id == campaign_id, CampaignCompany.company_id.in_(company_ids))
            )
        ).all()
    buyer_map = icp.buyer_map.model_dump(mode="json")
    buyer_map["target_functions"] = [t.value for t in icp.buyer_map.target_functions]
    offering = {"type": workspace.offering_type, "description": workspace.description or ""}

    async def one(cc: CampaignCompany, company: Company) -> int:
        if cc.status in _DECIDED:
            return 0  # idempotent on resume
        async with services.sessionmaker() as s:
            contacts = list(
                (
                    await s.execute(
                        select(Contact)
                        .where(Contact.company_id == company.id)
                        .order_by(Contact.created_at, Contact.full_name)
                    )
                ).scalars()
            )
            facts = list((await s.execute(select(Fact).where(Fact.company_id == company.id))).scalars())
        if not contacts:
            await _set_status(services, cc.id, "no_contact", "No suitable contact found")
            return 0
        size, industry, location = (_latest(facts, f) for f in ("employee_count", "industry", "location"))
        inputs = {
            "company": {"name": company.name, "domain": company.domain, "employee_count": size, "industry": industry},
            "offering": offering,
            "buyer_map": buyer_map,
            "candidates": [
                {
                    "id": str(c.id),
                    "full_name": c.full_name,
                    "title": c.title,
                    "function": c.function,
                    "seniority": c.seniority,
                    "email_status": c.email_status,
                }
                for c in contacts
            ],
        }
        titles = ", ".join(c.title for c in contacts)
        queries = [
            MemoryQuery(
                "episodic",
                ["selection_episode"],
                "real",
                f"{titles} at a {size or 'small'}-person {industry or ''} company",
                "past picks at similar companies",
                k=5,
            ),
            MemoryQuery("semantic", ["insight"], "real", titles, "title insights", filters={"dimension": "title"}, k=3),
        ]
        by_id = {str(c.id): c for c in contacts}
        emails = {cid: c.email for cid, c in by_id.items()}
        async with span(ctx, f"select:{company.domain}", "stage", {"company": company.domain}) as sp:
            selection = None
            for _attempt in range(2):
                step = await run_step(
                    ctx=sp.ctx,
                    gateway=services.gateway,
                    memory=services.memory,
                    settings=services.settings,
                    agent="selection",
                    task=TaskType.contact_selection,
                    goal="Pick the person who owns this problem and can buy, plus a backup",
                    inputs=inputs,
                    queries=queries,
                    build_messages=json_messages(prompt, inputs),
                    schema=ContactSelection,
                )
                try:
                    selection = validate_selection(step.output, set(by_id), set(), emails)
                    break
                except ValueError as exc:
                    sp.set("invalid_pick", str(exc))
            if selection is None:
                await _set_status(
                    services, cc.id, "needs_review", "The agent picked a person who isn't in the candidate list."
                )
                return 0
            if selection.no_suitable_contact:
                await _set_status(services, cc.id, "no_contact", "No suitable contact found")
                return 0

            picks = [("primary", selection.primary)] + ([("backup", selection.backup)] if selection.backup else [])
            prospects = [
                Prospect(
                    campaign_id=campaign_id,
                    company_id=company.id,
                    contact_id=UUID(pick.contact_id),
                    short_id=secrets.token_hex(4),
                    role=role,
                    pick_reason=pick.reason,
                    confidence=pick.confidence,
                    status="selected",
                )
                for role, pick in picks
            ]
            async with services.sessionmaker() as s:
                s.add_all(prospects)
                row = await s.get(CampaignCompany, cc.id)
                row.status = "contact_selected"
                await s.commit()

            primary = by_id[selection.primary.contact_id]
            summary = f"Picked {primary.title} ({primary.seniority}) as primary"
            if selection.backup:
                backup = by_id[selection.backup.contact_id]
                summary += f", {backup.title} ({backup.seniority}) as backup"
            where = location or "an unknown place"
            summary += f" at a {size or 'unknown'}-person {industry or 'unknown-industry'} company in {where}"
            with contextlib.suppress(GatewayError):  # memory helps but never blocks (Plan 1 ruling)
                await services.memory.write(
                    NewMemory(
                        kind="episodic",
                        subtype="selection_episode",
                        source="mock_sim" if company.synthetic else "research",
                        summary=summary,
                        payload={
                            "campaign_id": str(campaign_id),
                            "company_id": str(company.id),
                            "contact_id": str(primary.id),
                            "title": primary.title,
                            "function": primary.function,
                            "seniority": primary.seniority,
                        },
                        source_refs=[{"table": "prospect", "id": str(p.id)} for p in prospects],
                    ),
                    sp.ctx,
                )
            return 1

    counts = await bounded_gather([lambda cc=cc, co=co: one(cc, co) for cc, co in rows], CONCURRENCY)
    return sum(counts)


async def _set_status(services: Services, campaign_company_id: UUID, status: str, reason: str) -> None:
    async with services.sessionmaker() as s:
        row = await s.get(CampaignCompany, campaign_company_id)
        row.status = status
        row.reason = reason if status != "no_contact" or not row.reason else f"{row.reason} {reason}."
        await s.commit()
