from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from covora.api.deps import get_session
from covora.api.errors import ApiError
from covora.outreach.models import Template
from covora.workspace.service import ensure_workspace

router = APIRouter()


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    angle: Literal["pain", "roi", "social-proof", "curiosity", "partnership", "referral-ask"]
    length: Literal["short", "medium"]
    tone: Literal["direct", "warm", "formal"]
    cta: Literal["question", "booking-link", "soft"]
    subject_template: str = Field(min_length=1)
    body_template: str = Field(min_length=1)
    offering_types: list[Literal["sales_call", "dealer"]] = ["sales_call", "dealer"]
    active: bool = True


class TemplateOut(TemplateIn):
    id: UUID
    version: int


def _out(t: Template) -> TemplateOut:
    return TemplateOut.model_validate(t, from_attributes=True)


async def _get(session: AsyncSession, template_id: UUID) -> Template:
    t = await session.get(Template, template_id)
    if t is None:
        raise ApiError("not_found", "That template does not exist.", 404)
    return t


@router.get("/templates")
async def list_templates(session: AsyncSession = Depends(get_session)) -> list[TemplateOut]:
    ws = await ensure_workspace(session)
    rows = await session.execute(select(Template).where(Template.workspace_id == ws.id).order_by(Template.name))
    return [_out(t) for t in rows.scalars()]


@router.post("/templates")
async def create_template(body: TemplateIn, session: AsyncSession = Depends(get_session)) -> TemplateOut:
    ws = await ensure_workspace(session)
    t = Template(workspace_id=ws.id, **body.model_dump())
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return _out(t)


@router.put("/templates/{template_id}")
async def update_template(
    template_id: UUID, body: TemplateIn, session: AsyncSession = Depends(get_session)
) -> TemplateOut:
    t = await _get(session, template_id)
    for key, value in body.model_dump().items():
        setattr(t, key, value)
    t.version += 1
    await session.commit()
    await session.refresh(t)
    return _out(t)


@router.post("/templates/{template_id}/deactivate")
async def deactivate_template(template_id: UUID, session: AsyncSession = Depends(get_session)) -> TemplateOut:
    t = await _get(session, template_id)
    t.active = False
    await session.commit()
    await session.refresh(t)
    return _out(t)
