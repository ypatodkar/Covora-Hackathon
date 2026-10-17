"""Drafting cold emails: the model personalizes a template; code checks what it wrote (spec §10)."""

import re
from typing import Any
from uuid import UUID

from pydantic import BaseModel, model_validator
from sqlalchemy import select

from covora.agents.messages import json_messages
from covora.agents.step import run_step
from covora.campaigns.models import Campaign
from covora.discovery.models import Company, Fact
from covora.discovery.schemas import clean_strings_except
from covora.gateway.tasks import TaskType
from covora.memory.prompts import get_prompt
from covora.memory.store import MemoryQuery
from covora.observability.tracing import RunContext
from covora.outreach.arms import arm_for, campaign_arms
from covora.outreach.models import EmailMessage, SalesRep, Template
from covora.qualification.models import Contact, Prospect
from covora.services import Services
from covora.workspace.models import Workspace
from covora.workspace.settings import get_workspace_settings

FOOTER = "Not relevant? Reply 'unsubscribe' and I won't email again."
_MAX_WORDS = {"short": 120, "medium": 200}
_PLACEHOLDER = re.compile(r"\{[a-z_]+\}")
_URL = re.compile(r"(https?://[^\s)>\]]+|www\.[^\s)>\]]+)", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PRICE = re.compile(r"\$\s?\d|\bprice\b|\bpricing\b|\bdiscount|\d+\s?% off", re.IGNORECASE)


class PersonalizationItem(BaseModel):
    text: str
    fact_ids: list[str] = []


class DraftEmail(BaseModel):
    subject: str
    body: str
    personalization: list[PersonalizationItem] = []

    @model_validator(mode="before")
    @classmethod
    def _clean(cls, data: Any) -> Any:
        return clean_strings_except(data, {"fact_ids"})


def check_draft(
    draft: DraftEmail, *, template: Template, allowed_fact_ids: set[str], allowed_urls: set[str]
) -> list[str]:
    problems: list[str] = []
    text = f"{draft.subject}\n{draft.body}"
    if _PLACEHOLDER.search(text):
        problems.append("unresolved placeholder")
    for item in draft.personalization:
        if not item.fact_ids or not set(item.fact_ids) <= allowed_fact_ids:
            problems.append(f"personalization not backed by a fact: {item.text[:60]!r}")
    words = len(draft.body.split())
    if words > _MAX_WORDS.get(template.length, 200):
        problems.append(f"too long for a {template.length} template ({words} words)")
    allowed = tuple(u.rstrip("/").lower() for u in allowed_urls if u)
    for url in _URL.findall(draft.body):
        if not url.rstrip("/.,").lower().startswith(allowed or ("\x00",)):
            problems.append(f"URL not allowed: {url}")
    if _EMAIL.search(draft.body):
        problems.append("email address in body")
    if _PRICE.search(text):
        problems.append("mentions price or discount")
    return problems


def finalize_body(body: str) -> str:
    body = body.rstrip()
    return body if body.endswith(FOOTER) else f"{body}\n\n—\n{FOOTER}"


def fill_template(template: Template, *, first_name: str, company: str, sender_name: str) -> tuple[str, str]:
    """No-model fill, for fast simulation."""
    values = {
        "first_name": first_name,
        "company": company,
        "personal_hook": f"I came across {company} and had a thought.",
        "value_prop": "We help teams like yours take repetitive work off their plate.",
        "cta": {"question": "Is this on your radar?", "booking-link": "Want to grab 15 minutes?"}.get(
            template.cta, "Happy to share more if useful."
        ),
        "sender_name": sender_name,
    }
    subject = template.subject_template.format_map(values)
    body = template.body_template.format_map(values)
    return subject, finalize_body(body)


async def draft_email(prospect_id: UUID, *, ctx: RunContext, services: Services) -> EmailMessage:
    async with services.sessionmaker() as s:
        prospect = await s.get(Prospect, prospect_id)
        contact = await s.get(Contact, prospect.contact_id)
        company = await s.get(Company, prospect.company_id)
        campaign = await s.get(Campaign, prospect.campaign_id)
        workspace = await s.get(Workspace, campaign.workspace_id)
        arms = await campaign_arms(s, campaign.id)
        if not prospect.arm_key:
            prospect.arm_key = arm_for(prospect.id, [arm.key for arm, _ in arms])
            await s.commit()
        template = next(t for arm, t in arms if arm.key == prospect.arm_key)
        facts = list((await s.execute(select(Fact).where(Fact.company_id == company.id))).scalars())
        reps = list(
            (await s.execute(select(SalesRep).where(SalesRep.workspace_id == workspace.id, SalesRep.active))).scalars()
        )
        prompt = (await get_prompt(s, "email_draft")).body
    settings = get_workspace_settings(workspace)
    sender_name = settings.sending.sender_name or workspace.name
    booking = next((r.booking_url for r in reps if r.booking_url), None)
    inputs = {
        "seller": {
            "company": workspace.name,
            "website": workspace.website,
            "offering": workspace.description or "",
            "proof_points": list(workspace.value_props or []),
        },
        "sender_name": sender_name,
        "booking_link": booking,
        "template": {
            "subject_template": template.subject_template,
            "body_template": template.body_template,
            "angle": template.angle,
            "length": template.length,
            "tone": template.tone,
            "cta": template.cta,
        },
        "contact": {"first_name": contact.full_name.split()[0], "full_name": contact.full_name, "title": contact.title},
        "company": {"name": company.name, "domain": company.domain},
        "facts": [{"id": str(f.id), "field": f.field, "value": f.value, "label": f.label} for f in facts],
    }
    allowed_urls = {u for u in [workspace.website, *(r.booking_url for r in reps)] if u}
    features = f"{contact.title} at {company.name}; {template.length} email, {template.cta} CTA, {template.angle} angle"
    queries = [
        MemoryQuery(
            "episodic",
            ["outreach_episode"],
            "real",
            features,
            "similar positive outreach",
            filters={"outcome_label": "interested"},
            k=3,
        ),
        MemoryQuery("episodic", ["user_correction"], "real", "draft edits", "the user's past draft edits", k=3),
    ]
    problems: list[str] = []
    draft: DraftEmail | None = None
    for _attempt in range(2):
        attempt_inputs = inputs | ({"fix_these_problems": problems} if problems else {})
        step = await run_step(
            ctx=ctx,
            gateway=services.gateway,
            memory=services.memory,
            settings=services.settings,
            agent="email",
            task=TaskType.email_draft,
            goal="Personalize the template for this person using only the given facts",
            inputs=attempt_inputs,
            queries=queries,
            build_messages=json_messages(prompt, attempt_inputs),
            schema=DraftEmail,
        )
        draft = step.output
        problems = check_draft(
            draft, template=template, allowed_fact_ids={str(f.id) for f in facts}, allowed_urls=allowed_urls
        )
        if not problems:
            break
    email = EmailMessage(
        campaign_id=campaign.id,
        prospect_id=prospect.id,
        arm_key=prospect.arm_key,
        direction="out",
        kind="cold",
        status="needs_review" if problems else "draft",
        intended_to=contact.email,
        subject=draft.subject,
        body=finalize_body(draft.body),
        template_id=template.id,
        personalization=[p.model_dump() for p in draft.personalization],
        error="; ".join(problems) or None,
    )
    async with services.sessionmaker() as s:
        s.add(email)
        row = await s.get(Prospect, prospect.id)
        row.status = "drafted"
        await s.commit()
        await s.refresh(email)
    return email
