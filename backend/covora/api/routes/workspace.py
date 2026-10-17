from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from covora.api.deps import get_session
from covora.workspace.models import Workspace
from covora.workspace.service import WorkspaceProfile, ensure_workspace, update_profile

router = APIRouter()


class WorkspaceOut(WorkspaceProfile):
    id: UUID


def _out(ws: Workspace) -> WorkspaceOut:
    return WorkspaceOut(
        id=ws.id,
        name=ws.name,
        website=ws.website,
        description=ws.description,
        value_props=list(ws.value_props or []),
        offering_type=ws.offering_type,
    )


@router.get("/workspace")
async def get_workspace(session: AsyncSession = Depends(get_session)) -> WorkspaceOut:
    return _out(await ensure_workspace(session))


@router.put("/workspace")
async def put_workspace(body: WorkspaceProfile, session: AsyncSession = Depends(get_session)) -> WorkspaceOut:
    ws = await ensure_workspace(session)
    return _out(await update_profile(session, ws, body))
