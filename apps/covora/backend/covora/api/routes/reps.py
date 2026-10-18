from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from covora.api.deps import get_session
from covora.api.errors import ApiError
from covora.outreach.models import SalesRep, Suppression
from covora.outreach.suppression import suppress
from covora.workspace.service import ensure_workspace

router = APIRouter()


class SalesRepIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    booking_url: str | None = None
    active: bool = True


class SalesRepOut(SalesRepIn):
    id: UUID


class SuppressionIn(BaseModel):
    email: str = Field(min_length=3)
    reason: str = "manual"


async def _rep(session: AsyncSession, rep_id: UUID) -> SalesRep:
    rep = await session.get(SalesRep, rep_id)
    if rep is None:
        raise ApiError("not_found", "That sales rep does not exist.", 404)
    return rep


@router.get("/sales-reps")
async def list_reps(session: AsyncSession = Depends(get_session)) -> list[SalesRepOut]:
    ws = await ensure_workspace(session)
    rows = await session.execute(select(SalesRep).where(SalesRep.workspace_id == ws.id).order_by(SalesRep.created_at))
    return [SalesRepOut.model_validate(r, from_attributes=True) for r in rows.scalars()]


@router.post("/sales-reps")
async def create_rep(body: SalesRepIn, session: AsyncSession = Depends(get_session)) -> SalesRepOut:
    ws = await ensure_workspace(session)
    rep = SalesRep(workspace_id=ws.id, **body.model_dump())
    session.add(rep)
    await session.commit()
    await session.refresh(rep)
    return SalesRepOut.model_validate(rep, from_attributes=True)


@router.put("/sales-reps/{rep_id}")
async def update_rep(rep_id: UUID, body: SalesRepIn, session: AsyncSession = Depends(get_session)) -> SalesRepOut:
    rep = await _rep(session, rep_id)
    for key, value in body.model_dump().items():
        setattr(rep, key, value)
    await session.commit()
    await session.refresh(rep)
    return SalesRepOut.model_validate(rep, from_attributes=True)


@router.delete("/sales-reps/{rep_id}", status_code=204)
async def delete_rep(rep_id: UUID, session: AsyncSession = Depends(get_session)) -> Response:
    await session.delete(await _rep(session, rep_id))
    await session.commit()
    return Response(status_code=204)


@router.get("/suppression")
async def list_suppression(session: AsyncSession = Depends(get_session)) -> list[dict]:
    ws = await ensure_workspace(session)
    rows = await session.execute(select(Suppression).where(Suppression.workspace_id == ws.id))
    return [
        {"email": s.email_normalized, "reason": s.reason, "created_at": s.created_at.isoformat()}
        for s in rows.scalars()
    ]


@router.post("/suppression")
async def add_suppression(body: SuppressionIn, session: AsyncSession = Depends(get_session)) -> dict:
    ws = await ensure_workspace(session)
    await suppress(session, ws.id, body.email, body.reason)
    return {"email": body.email.strip().lower(), "reason": body.reason}
