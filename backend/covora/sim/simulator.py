"""Reply simulator: code decides each simulated prospect's outcome from a hidden profile; the model writes the text."""

import random
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import yaml
from pydantic import BaseModel
from sqlalchemy import select

from covora.agents.messages import json_messages
from covora.agents.step import run_step
from covora.campaigns.models import Campaign
from covora.discovery.models import Company, Fact
from covora.gateway.tasks import TaskType
from covora.jobs.models import Job
from covora.jobs.queue import enqueue
from covora.jobs.registry import HANDLERS
from covora.memory.prompts import get_prompt
from covora.observability.tracing import RunContext, finish_run, start_run
from covora.outreach.models import EmailMessage, Template
from covora.qualification.models import Contact, Prospect
from covora.services import Services
from covora.workspace.models import Workspace
from covora.workspace.settings import get_workspace_settings

PROFILES = Path(__file__).with_name("profiles")
REPLY_HANDLE_JOB = "reply.handle"


@dataclass
class Profile:
    name: str
    base_positive_rate: float
    multipliers: dict
    outcome_mix_when_not_positive: dict
    p_book: float


class SimReply(BaseModel):
    body: str


def load_profile(name: str) -> Profile:
    return Profile(**yaml.safe_load((PROFILES / f"{name}.yaml").read_text()))


def rng_for(prospect_id: UUID, seed: int) -> random.Random:
    return random.Random(f"{seed}:{prospect_id}")


def positive_rate(profile: Profile, features: dict) -> float:
    m = profile.multipliers
    rate = profile.base_positive_rate
    for key in ("function", "length", "cta"):
        rate *= m.get(key, {}).get(features.get(key), 1.0)
    if features.get("seniority") == "c_level" and (features.get("company_size") or 0) > 50:
        rate *= m.get("seniority_by_size", {}).get("c_level_at_51_plus", 1.0)
    return min(rate, 0.95)


def decide_outcome(profile: Profile, features: dict, rng: random.Random) -> str:
    if rng.random() < positive_rate(profile, features):
        return "interested"
    pick, total = rng.random(), 0.0
    mix = profile.outcome_mix_when_not_positive
    for label, share in mix.items():
        total += share / sum(mix.values())
        if pick < total:
            return label
    return "none"


async def features_for(session, email: EmailMessage) -> dict:
    prospect = await session.get(Prospect, email.prospect_id)
    contact = await session.get(Contact, prospect.contact_id)
    template = await session.get(Template, email.template_id) if email.template_id else None
    size = (
        (
            await session.execute(
                select(Fact.value).where(Fact.company_id == prospect.company_id, Fact.field == "employee_count")
            )
        )
        .scalars()
        .first()
    )
    try:
        company_size = int(str(size)) if size is not None else None
    except ValueError:
        company_size = None
    return {
        "function": contact.function,
        "seniority": contact.seniority,
        "company_size": company_size,
        "length": template.length if template else None,
        "cta": template.cta if template else None,
        "angle": template.angle if template else None,
        "tone": template.tone if template else None,
    }


async def simulate_reply(email_id: UUID, *, ctx: RunContext, services: Services) -> UUID | None:
    async with services.sessionmaker() as s:
        email = await s.get(EmailMessage, email_id)
        if email is None or email.kind != "cold" or email.direction != "out":
            return None  # the simulator answers only cold emails (no reply loops)
        campaign = await s.get(Campaign, email.campaign_id)
        ws_settings = get_workspace_settings(await s.get(Workspace, campaign.workspace_id))
        prospect = await s.get(Prospect, email.prospect_id)
        contact = await s.get(Contact, prospect.contact_id)
        company = await s.get(Company, prospect.company_id)
        features = await features_for(s, email)
        prompt = (await get_prompt(s, "sim_reply_writing")).body
    profile = load_profile(ws_settings.simulation.profile)
    outcome = decide_outcome(profile, features, rng_for(prospect.id, ws_settings.simulation.seed))
    if outcome == "none":
        return None
    inputs = {
        "persona": {"name": contact.full_name, "title": contact.title, "company": company.name},
        "outcome": outcome,
        "email": {"subject": email.subject, "body": email.body},
    }
    step = await run_step(
        ctx=ctx,
        gateway=services.gateway,
        memory=services.memory,
        settings=services.settings,
        agent="simulator",
        task=TaskType.sim_reply_writing,
        goal="Write the simulated prospect's reply for the decided outcome",
        inputs=inputs,
        queries=[],
        build_messages=json_messages(prompt, inputs),
        schema=SimReply,
    )
    reply = EmailMessage(
        campaign_id=email.campaign_id,
        prospect_id=email.prospect_id,
        arm_key=email.arm_key,
        direction="in",
        kind="inbound",
        status="received",
        intended_to=None,
        actual_to="in-app",
        subject=f"Re: {email.subject}",
        body=step.output.body,
        source="in_app_sim",
        received_at=datetime.now(UTC),
        error=None,
    )
    async with services.sessionmaker() as s:
        s.add(reply)
        await s.commit()
        await s.refresh(reply)
        await enqueue(s, REPLY_HANDLE_JOB, {"email_id": str(reply.id)}, max_attempts=2)
    return reply.id


async def sim_reply_job(job: Job, services: Services) -> None:
    email_id = UUID(job.payload["email_id"])
    async with services.sessionmaker() as s:
        email = await s.get(EmailMessage, email_id)
        workspace_id = (await s.get(Campaign, email.campaign_id)).workspace_id
    ctx = await start_run(
        services.sessionmaker,
        kind="reply",
        workspace_id=workspace_id,
        secrets=services.settings.secret_values(),
        campaign_id=email.campaign_id,
    )
    try:
        await simulate_reply(email_id, ctx=ctx, services=services)
    except Exception as exc:
        await finish_run(ctx, status="failed", error=str(exc))
        raise
    await finish_run(ctx, status="succeeded")


HANDLERS["sim.reply"] = sim_reply_job
