from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from covora.api.deps import Services, get_services, get_session
from covora.api.errors import ApiError
from covora.icp.agent import parse_icp
from covora.icp.models import IcpVersion
from covora.icp.schemas import StructuredICP
from covora.icp.service import save_icp_version
from covora.observability.tracing import finish_run, start_run
from covora.workspace.service import ensure_workspace

router = APIRouter()


class ParseRequest(BaseModel):
    prompt_text: str = Field(min_length=1, max_length=4000)


class ParseResponse(BaseModel):
    draft: StructuredICP
    run_id: UUID
    working_memory: list[dict]


class SaveIcpRequest(BaseModel):
    prompt_text: str = Field(min_length=1, max_length=4000)
    structured: StructuredICP
    draft: StructuredICP | None = None
    parent_id: UUID | None = None


class IcpVersionOut(BaseModel):
    id: UUID
    version: int
    prompt_text: str
    structured: StructuredICP
    parent_id: UUID | None
    created_by: Literal["user", "agent"]
    created_at: datetime


def _out(v: IcpVersion) -> IcpVersionOut:
    return IcpVersionOut(
        id=v.id,
        version=v.version,
        prompt_text=v.prompt_text,
        structured=StructuredICP.model_validate(v.structured),
        parent_id=v.parent_id,
        created_by=v.created_by,
        created_at=v.created_at,
    )


@router.post("/icp/parse")
async def parse(
    body: ParseRequest,
    services: Services = Depends(get_services),
    session: AsyncSession = Depends(get_session),
) -> ParseResponse:
    ws = await ensure_workspace(session)
    ctx = await start_run(
        services.sessionmaker, kind="icp", workspace_id=ws.id, secrets=services.settings.secret_values()
    )
    try:
        result = await parse_icp(
            body.prompt_text,
            ctx=ctx,
            gateway=services.gateway,
            memory=services.memory,
            settings=services.settings,
            session=session,
        )
    except Exception as exc:
        await finish_run(ctx, status="failed", error=str(exc))
        raise
    await finish_run(ctx, status="succeeded")
    return ParseResponse(draft=result.output, run_id=ctx.run_id, working_memory=result.working_memory.manifest())


@router.post("/icps")
async def save(
    body: SaveIcpRequest,
    services: Services = Depends(get_services),
    session: AsyncSession = Depends(get_session),
) -> IcpVersionOut:
    ws = await ensure_workspace(session)
    if body.parent_id is not None and await session.get(IcpVersion, body.parent_id) is None:
        raise ApiError("not_found", "The parent ICP version does not exist.", 404)
    ctx = await start_run(
        services.sessionmaker, kind="icp", workspace_id=ws.id, secrets=services.settings.secret_values()
    )
    try:
        version = await save_icp_version(
            session,
            workspace_id=ws.id,
            prompt_text=body.prompt_text,
            structured=body.structured,
            draft=body.draft,
            parent_id=body.parent_id,
            created_by="user",
            memory=services.memory,
            ctx=ctx,
        )
    except Exception as exc:
        await finish_run(ctx, status="failed", error=str(exc))
        raise
    await finish_run(ctx, status="succeeded")
    return _out(version)


@router.get("/icps")
async def list_icps(session: AsyncSession = Depends(get_session)) -> list[IcpVersionOut]:
    ws = await ensure_workspace(session)
    rows = await session.execute(
        select(IcpVersion).where(IcpVersion.workspace_id == ws.id).order_by(IcpVersion.version.desc())
    )
    return [_out(v) for v in rows.scalars()]


@router.get("/icps/{icp_id}")
async def get_icp(icp_id: UUID, session: AsyncSession = Depends(get_session)) -> IcpVersionOut:
    version = await session.get(IcpVersion, icp_id)
    if version is None:
        raise ApiError("not_found", "That ICP version does not exist.", 404)
    return _out(version)
