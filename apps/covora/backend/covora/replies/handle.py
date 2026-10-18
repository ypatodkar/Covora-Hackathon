"""Reply handling (spec §12): code rules first, then the model's label; code decides and acts, once per prospect."""

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from covora.agents.messages import json_messages
from covora.agents.step import run_step
from covora.campaigns.models import Campaign
from covora.discovery.models import Company
from covora.gateway.tasks import TaskType
from covora.jobs.models import Job
from covora.jobs.registry import HANDLERS
from covora.memory.prompts import get_prompt
from covora.observability.tracing import RunContext, finish_run, start_run
from covora.outreach.drafts import finalize_body
from covora.outreach.models import EmailMessage, RepAssignment, ReplyClassification, SalesRep
from covora.outreach.send import cancel_queued_to
from covora.outreach.suppression import suppress
from covora.qualification.models import Contact, Prospect
from covora.replies.backups import activate_backup
from covora.replies.outcomes import record_outcome
from covora.replies.schemas import HandoffReply, ReplyClassificationOut
from covora.services import Services
from covora.sim.simulator import load_profile, rng_for
from covora.workspace.models import Workspace
from covora.workspace.settings import get_workspace_settings

_UNSUBSCRIBE = re.compile(r"\bunsubscribe\b|\bremove me\b|\bstop emailing\b|\btake me off\b", re.IGNORECASE)
_BOUNCE = re.compile(r"mailer-daemon|postmaster|delivery status notification|undeliverable", re.IGNORECASE)
_DECIDED = {"handed_off", "closed_lost", "not_now", "suppressed", "bounced", "needs_review"}
_STATUS = {"not_now": "not_now", "not_interested": "closed_lost", "out_of_office": None}


def rule_label(body: str, from_address: str | None = None) -> str | None:
    if _UNSUBSCRIBE.search(body):
        return "unsubscribe"
    if _BOUNCE.search(from_address or "") or _BOUNCE.search(body[:200]):
        return "bounce"
    return None


async def _classify(
    email: EmailMessage, *, ctx: RunContext, services: Services
) -> tuple[str, float, str | None, dict | None, str]:
    async with services.sessionmaker() as s:
        prompt = (await get_prompt(s, "reply_classification")).body
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
    inputs = {"reply": email.body, "our_email": {"subject": cold.subject, "body": cold.body} if cold else None}
    label, confidence, model, referral, summary = "other", 0.0, None, None, ""
    for task in (TaskType.reply_classification, TaskType.reply_reclassification):
        step = await run_step(
            ctx=ctx,
            gateway=services.gateway,
            memory=services.memory,
            settings=services.settings,
            agent="replies",
            task=task,
            goal="Label this reply to our cold email",
            inputs=inputs,
            queries=[],
            build_messages=json_messages(prompt, inputs),
            schema=ReplyClassificationOut,
        )
        out = step.output
        label, confidence, model = out.label, out.confidence, step.gateway.model
        referral, summary = (out.referral.model_dump() if out.referral else None), out.summary
        if confidence >= 0.7:
            break
    if confidence < 0.6:
        label = "needs_review"
    return label, confidence, model, referral, summary


async def _hand_off(
    email: EmailMessage, prospect: Prospect, contact: Contact, *, ctx: RunContext, services: Services
) -> bool:
    async with services.sessionmaker() as s:
        campaign = await s.get(Campaign, prospect.campaign_id)
        workspace = await s.get(Workspace, campaign.workspace_id)
        rep = (
            await s.execute(
                select(SalesRep)
                .where(SalesRep.workspace_id == workspace.id, SalesRep.active)
                .order_by(SalesRep.last_assigned_at.asc().nulls_first(), SalesRep.created_at)
                .limit(1)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if rep is None:
            return False
        rep.last_assigned_at = datetime.now(UTC)
        await s.commit()
        prompt = (await get_prompt(s, "handoff_reply_draft")).body
    inputs = {
        "contact": {"first_name": contact.full_name.split()[0], "title": contact.title},
        "rep": {"name": rep.name, "booking_url": rep.booking_url},
        "offering_type": workspace.offering_type,
        "their_reply": email.body,
    }
    step = await run_step(
        ctx=ctx,
        gateway=services.gateway,
        memory=services.memory,
        settings=services.settings,
        agent="handoff",
        task=TaskType.handoff_reply_draft,
        goal="Introduce the salesperson who'll take it from here",
        inputs=inputs,
        queries=[],
        build_messages=json_messages(prompt, inputs),
        schema=HandoffReply,
    )
    body = step.output.body
    if rep.booking_url and rep.booking_url not in body:
        body = f"{body.rstrip()}\n\nYou can pick a time here: {rep.booking_url}"
    async with services.sessionmaker() as s:
        s.add(
            EmailMessage(
                campaign_id=prospect.campaign_id,
                prospect_id=prospect.id,
                arm_key=prospect.arm_key,
                direction="out",
                kind="handoff",
                status="queued",
                intended_to=contact.email,
                cc=[rep.email],
                subject=email.subject if email.subject.lower().startswith("re:") else f"Re: {email.subject}",
                body=finalize_body(body),
            )
        )
        s.add(RepAssignment(prospect_id=prospect.id, sales_rep_id=rep.id, reason="round-robin: interested reply"))
        row = await s.get(Prospect, prospect.id)
        row.status, row.assigned_rep_id = "handed_off", rep.id
        if email.source == "in_app_sim":
            ws_settings = get_workspace_settings(workspace)
            rng = rng_for(prospect.id, ws_settings.simulation.seed + 1)
            if rng.random() < load_profile(ws_settings.simulation.profile).p_book:
                row.meeting_booked_at, row.meeting_synthetic = datetime.now(UTC), True
        await s.commit()
    return True


async def handle_reply(email_id: UUID, *, ctx: RunContext, services: Services) -> str:
    async with services.sessionmaker() as s:
        email = await s.get(EmailMessage, email_id)
        prospect = await s.get(Prospect, email.prospect_id)
        contact = await s.get(Contact, prospect.contact_id)
        company = await s.get(Company, prospect.company_id)
        workspace_id = company.workspace_id
        already_decided = prospect.status in _DECIDED
    rule = rule_label(email.body)
    if rule:
        label, confidence, model, referral, summary = rule, 1.0, None, None, "matched a code rule"
    else:
        label, confidence, model, referral, summary = await _classify(email, ctx=ctx, services=services)
    async with services.sessionmaker() as s:
        s.add(
            ReplyClassification(
                email_message_id=email.id,
                label=label,
                confidence=confidence,
                model=model,
                referral=referral,
                summary=summary,
                rule_override=rule,
            )
        )
        await s.commit()

    if already_decided and label != "unsubscribe":
        return label  # automatic actions happen at most once per prospect

    new_status: str | None = None
    if label == "interested":
        if not await _hand_off(email, prospect, contact, ctx=ctx, services=services):
            new_status = "needs_review"
            async with services.sessionmaker() as s:
                (
                    await s.get(EmailMessage, email.id)
                ).error = "Interested, but no active sales rep: add a sales rep in Settings."
                await s.commit()
    elif label == "unsubscribe":
        new_status = "suppressed"
        async with services.sessionmaker() as s:
            if contact.email:
                await suppress(s, workspace_id, contact.email, "unsubscribe", email.id)
                await cancel_queued_to(s, workspace_id, contact.email)
            for queued in (
                await s.execute(
                    select(EmailMessage).where(EmailMessage.prospect_id == prospect.id, EmailMessage.status == "queued")
                )
            ).scalars():
                queued.status = "cancelled"
            await s.commit()
    elif label in ("wrong_person", "bounce"):
        new_status = "bounced" if label == "bounce" else "closed_lost"
        await activate_backup(prospect.id, ctx=ctx, services=services)
    elif label == "needs_review" or label == "other":
        new_status = "needs_review"
    else:
        new_status = _STATUS.get(label)

    if new_status:
        async with services.sessionmaker() as s:
            (await s.get(Prospect, prospect.id)).status = new_status
            await s.commit()
    if label not in ("needs_review", "other"):
        await record_outcome(email, label, ctx=ctx, services=services)
    return label


async def reply_handle_job(job: Job, services: Services) -> None:
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
        await handle_reply(email_id, ctx=ctx, services=services)
    except Exception as exc:
        await finish_run(ctx, status="failed", error=str(exc))
        raise
    await finish_run(ctx, status="succeeded")


HANDLERS["reply.handle"] = reply_handle_job
