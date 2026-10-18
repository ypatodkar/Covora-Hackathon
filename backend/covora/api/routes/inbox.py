"""Inbox: one thread per prospect, with every simulated message and its label (spec §13)."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from covora.api.deps import get_session
from covora.api.errors import ApiError
from covora.campaigns.models import Campaign
from covora.discovery.models import Company
from covora.outreach.drafts import finalize_body
from covora.outreach.models import EmailMessage, ReplyClassification, SalesRep
from covora.outreach.suppression import is_suppressed
from covora.qualification.models import Contact, Prospect
from covora.workspace.service import ensure_workspace

router = APIRouter()

_SIM_SOURCES = {"in_app_sim", "gmail_sim", "mock_sim"}


class ManualReply(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


def _contact(c: Contact) -> dict:
    return {"id": str(c.id), "full_name": c.full_name, "title": c.title, "email": c.email, "synthetic": c.synthetic}


def _company(c: Company) -> dict:
    return {"id": str(c.id), "name": c.name, "domain": c.domain, "synthetic": c.synthetic}


def _when(e: EmailMessage) -> datetime:
    return e.received_at or e.sent_at or e.created_at


async def _prospect_or_404(session: AsyncSession, prospect_id: UUID) -> Prospect:
    prospect = await session.get(Prospect, prospect_id)
    if prospect is None:
        raise ApiError("not_found", "That prospect does not exist.", 404)
    return prospect


@router.get("/inbox/threads")
async def threads(
    filter: str = "all", campaign_id: UUID | None = None, session: AsyncSession = Depends(get_session)
) -> list[dict]:
    ws = await ensure_workspace(session)
    query = (
        select(EmailMessage, Prospect, Contact, Company, ReplyClassification)
        .join(Prospect, Prospect.id == EmailMessage.prospect_id)
        .join(Contact, Contact.id == Prospect.contact_id)
        .join(Company, Company.id == Prospect.company_id)
        .join(Campaign, Campaign.id == EmailMessage.campaign_id)
        .outerjoin(ReplyClassification, ReplyClassification.email_message_id == EmailMessage.id)
        .where(Campaign.workspace_id == ws.id, EmailMessage.status.notin_(("draft", "needs_review", "rejected")))
    )
    if campaign_id:
        query = query.where(EmailMessage.campaign_id == campaign_id)
    by_prospect: dict[UUID, dict] = {}
    for email, prospect, contact, company, label in (await session.execute(query)).all():
        row = by_prospect.setdefault(
            prospect.id,
            {
                "prospect_id": str(prospect.id),
                "campaign_id": str(prospect.campaign_id),
                "contact": _contact(contact),
                "company": _company(company),
                "status": prospect.status,
                "meeting_booked": prospect.meeting_booked_at is not None,
                "simulated": False,
                "message_count": 0,
                "last_message_at": None,
                "last_label": None,
                "_last_in": None,
            },
        )
        row["message_count"] += 1
        row["simulated"] = row["simulated"] or email.delivery == "in_app" or email.source in _SIM_SOURCES
        when = _when(email)
        if row["last_message_at"] is None or when > row["last_message_at"]:
            row["last_message_at"] = when
        if email.direction == "in" and label and (row["_last_in"] is None or when > row["_last_in"]):
            row["_last_in"], row["last_label"] = when, label.label
    rows = sorted(by_prospect.values(), key=lambda r: r["last_message_at"], reverse=True)
    if filter == "interested":
        rows = [r for r in rows if r["last_label"] == "interested" or r["status"] == "handed_off"]
    elif filter == "needs_review":
        rows = [r for r in rows if r["status"] == "needs_review" or r["last_label"] == "needs_review"]
    for r in rows:
        r.pop("_last_in")
    return rows


@router.get("/inbox/threads/{prospect_id}")
async def thread(prospect_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    prospect = await _prospect_or_404(session, prospect_id)
    contact = await session.get(Contact, prospect.contact_id)
    company = await session.get(Company, prospect.company_id)
    rep = await session.get(SalesRep, prospect.assigned_rep_id) if prospect.assigned_rep_id else None
    rows = (
        await session.execute(
            select(EmailMessage, ReplyClassification)
            .outerjoin(ReplyClassification, ReplyClassification.email_message_id == EmailMessage.id)
            .where(EmailMessage.prospect_id == prospect_id)
        )
    ).all()
    messages = [
        {
            "id": str(e.id),
            "direction": e.direction,
            "kind": e.kind,
            "subject": e.subject,
            "body": e.body,
            "status": e.status,
            "delivery": e.delivery,
            "source": e.source,
            "intended_to": e.intended_to,
            "actual_to": e.actual_to,
            "cc": e.cc,
            "sent_at": e.sent_at,
            "received_at": e.received_at,
            "created_at": e.created_at,
            "error": e.error,
            "label": rc.label if rc else None,
            "confidence": rc.confidence if rc else None,
            "summary": rc.summary if rc else None,
        }
        for e, rc in sorted(rows, key=lambda r: _when(r[0]))
    ]
    return {
        "prospect": {
            "id": str(prospect.id),
            "campaign_id": str(prospect.campaign_id),
            "role": prospect.role,
            "status": prospect.status,
            "arm_key": prospect.arm_key,
            "pick_reason": prospect.pick_reason,
            "meeting_booked_at": prospect.meeting_booked_at,
            "meeting_synthetic": prospect.meeting_synthetic,
        },
        "contact": _contact(contact),
        "company": _company(company),
        "rep": {"name": rep.name, "email": rep.email, "booking_url": rep.booking_url} if rep else None,
        "messages": messages,
    }


@router.post("/inbox/threads/{prospect_id}/reply")
async def manual_reply(prospect_id: UUID, body: ManualReply, session: AsyncSession = Depends(get_session)) -> dict:
    prospect = await _prospect_or_404(session, prospect_id)
    contact = await session.get(Contact, prospect.contact_id)
    campaign = await session.get(Campaign, prospect.campaign_id)
    if contact.email and await is_suppressed(session, campaign.workspace_id, contact.email):
        raise ApiError("suppressed", "This person unsubscribed, so Covora won't email them again.", 409)
    last = (
        (
            await session.execute(
                select(EmailMessage)
                .where(EmailMessage.prospect_id == prospect_id)
                .order_by(EmailMessage.created_at.desc())
            )
        )
        .scalars()
        .first()
    )
    subject = (last.subject if last else "") or "Following up"
    email = EmailMessage(
        campaign_id=prospect.campaign_id,
        prospect_id=prospect.id,
        arm_key=prospect.arm_key,
        direction="out",
        kind="manual_reply",
        status="queued",
        intended_to=contact.email,
        subject=subject if subject.lower().startswith("re:") else f"Re: {subject}",
        body=finalize_body(body.body),
    )
    session.add(email)
    await session.commit()
    return {"id": str(email.id), "status": email.status}


@router.post("/prospects/{prospect_id}/meeting")
async def mark_meeting(prospect_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    prospect = await _prospect_or_404(session, prospect_id)
    prospect.meeting_booked_at = datetime.now(UTC)
    prospect.meeting_synthetic = False
    await session.commit()
    return {"id": str(prospect.id), "meeting_booked_at": prospect.meeting_booked_at}
