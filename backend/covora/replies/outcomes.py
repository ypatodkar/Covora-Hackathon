"""Outcomes become episodic memory: what was sent to whom, and what happened (spec §7.2)."""

import contextlib

from sqlalchemy import select

from covora.discovery.models import Fact
from covora.gateway.gateway import GatewayError
from covora.memory.models import MemoryItem
from covora.memory.store import NewMemory
from covora.observability.tracing import RunContext
from covora.outreach.models import EmailMessage
from covora.qualification.models import Contact, Prospect
from covora.services import Services
from covora.sim.simulator import features_for


async def record_outcome(email: EmailMessage, label: str, *, ctx: RunContext, services: Services) -> None:
    async with services.sessionmaker() as s:
        cold = (
            (
                await s.execute(
                    select(EmailMessage).where(
                        EmailMessage.prospect_id == email.prospect_id, EmailMessage.kind == "cold"
                    )
                )
            )
            .scalars()
            .first()
        )
        if cold is None:
            return
        features = await features_for(s, cold)
        prospect = await s.get(Prospect, email.prospect_id)
        contact = await s.get(Contact, prospect.contact_id)
        facts = {
            f.field: str(f.value)
            for f in (await s.execute(select(Fact).where(Fact.company_id == prospect.company_id))).scalars()
        }
        selection = (
            (
                await s.execute(
                    select(MemoryItem).where(
                        MemoryItem.subtype == "selection_episode",
                        MemoryItem.payload["contact_id"].astext == str(contact.id),
                        MemoryItem.outcome.is_(None),
                    )
                )
            )
            .scalars()
            .first()
        )
    source = "mock_sim" if email.source == "mock_sim" else (email.source or "research")
    summary = (
        f"{contact.title} · {features.get('company_size') or '?'}-person {facts.get('industry', 'company')} · "
        f"{facts.get('location', '?')} · {features.get('length')} email, {features.get('cta')} CTA, "
        f"{features.get('angle')} angle → {label}"
    )
    with contextlib.suppress(GatewayError):
        await services.memory.write(
            NewMemory(
                kind="episodic",
                subtype="outreach_episode",
                source=source,
                summary=summary,
                payload={**features, "outcome_label": label, "campaign_id": str(cold.campaign_id), "arm": cold.arm_key},
                source_refs=[
                    {"table": "email_message", "id": str(cold.id)},
                    {"table": "email_message", "id": str(email.id)},
                ],
            ),
            ctx,
        )
    if selection is not None:
        with contextlib.suppress(ValueError):
            await services.memory.attach_outcome(selection.id, {"label": label}, ctx)
