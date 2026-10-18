import contextlib
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from covora.api.deps import Services, get_services, get_session
from covora.api.errors import ApiError
from covora.api.routes.campaigns import campaign_out, get_campaign_or_404
from covora.discovery.models import Company
from covora.gateway.gateway import GatewayError
from covora.jobs.queue import enqueue
from covora.memory.store import NewMemory
from covora.observability.tracing import finish_run, start_run
from covora.outreach.drafts import finalize_body
from covora.outreach.models import EmailMessage
from covora.qualification.models import Contact, Prospect

router = APIRouter()


class EmailEdit(BaseModel):
    subject: str | None = None
    body: str | None = None


class ApprovalIn(BaseModel):
    approved: list[UUID] = []
    rejected: list[UUID] = []


def email_out(e: EmailMessage, contact: Contact | None = None, company: Company | None = None) -> dict:
    return {
        "id": str(e.id),
        "prospect_id": str(e.prospect_id),
        "arm_key": e.arm_key,
        "kind": e.kind,
        "status": e.status,
        "subject": e.subject,
        "body": e.body,
        "problems": [p for p in (e.error or "").split("; ") if p],
        "intended_to": e.intended_to,
        "contact": {"full_name": contact.full_name, "title": contact.title} if contact else None,
        "company": {"name": company.name, "domain": company.domain} if company else None,
    }


@router.get("/campaigns/{campaign_id}/review")
async def review_queue(campaign_id: UUID, session: AsyncSession = Depends(get_session)) -> list[dict]:
    await get_campaign_or_404(session, campaign_id)
    rows = await session.execute(
        select(EmailMessage, Contact, Company)
        .join(Prospect, Prospect.id == EmailMessage.prospect_id)
        .join(Contact, Contact.id == Prospect.contact_id)
        .join(Company, Company.id == Prospect.company_id)
        .where(
            EmailMessage.campaign_id == campaign_id,
            EmailMessage.kind == "cold",
            EmailMessage.status.in_(("draft", "needs_review")),
        )
        .order_by(EmailMessage.created_at)
    )
    return [email_out(e, c, co) for e, c, co in rows.all()]


@router.patch("/emails/{email_id}")
async def edit_email(
    email_id: UUID,
    body: EmailEdit,
    services: Services = Depends(get_services),
    session: AsyncSession = Depends(get_session),
) -> dict:
    email = await session.get(EmailMessage, email_id)
    if email is None:
        raise ApiError("not_found", "That email does not exist.", 404)
    if email.status not in ("draft", "needs_review"):
        raise ApiError("invalid_state", "Only drafts can be edited.", 409)
    before_words, before_subject = len(email.body.split()), email.subject
    if body.subject is not None:
        email.subject = body.subject
    if body.body is not None:
        email.body = finalize_body(body.body)
    email.status, email.error = "draft", None
    await session.commit()
    await session.refresh(email)
    company = await session.get(Company, (await session.get(Prospect, email.prospect_id)).company_id)
    changes = []
    if body.subject is not None and body.subject != before_subject:
        changes.append(f"changed the subject from {before_subject!r} to {body.subject!r}")
    if body.body is not None:
        changes.append(f"rewrote the body ({before_words} → {len(email.body.split())} words)")
    if changes:
        ctx = await start_run(
            services.sessionmaker,
            kind="review",
            workspace_id=company.workspace_id,
            secrets=services.settings.secret_values(),
        )
        with contextlib.suppress(GatewayError):
            await services.memory.write(
                NewMemory(
                    kind="episodic",
                    subtype="user_correction",
                    source="mock_sim" if company.synthetic else "research",
                    summary="User edited a draft: " + "; ".join(changes),
                    payload={"email_id": str(email.id), "subject": email.subject, "words": len(email.body.split())},
                    source_refs=[{"table": "email_message", "id": str(email.id)}],
                ),
                ctx,
            )
        await finish_run(ctx, status="succeeded")
    return email_out(email)


@router.post("/campaigns/{campaign_id}/approve")
async def approve(campaign_id: UUID, body: ApprovalIn, session: AsyncSession = Depends(get_session)):
    from covora.graphs.jobs import JOB_KIND

    campaign = await get_campaign_or_404(session, campaign_id)
    if campaign.status != "awaiting_approval":
        raise ApiError("invalid_state", f"Nothing to approve: the campaign is {campaign.status}.", 409)
    campaign.status = "queued"
    await session.commit()
    value = {"approved": [str(i) for i in body.approved], "rejected": [str(i) for i in body.rejected]}
    await enqueue(
        session, JOB_KIND, {"campaign_id": str(campaign_id), "resume": True, "resume_value": value}, max_attempts=1
    )
    return await campaign_out(session, campaign)
