from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from covora.api.deps import get_session
from covora.workspace.service import ensure_workspace
from covora.workspace.settings import WorkspaceSettings, get_workspace_settings, update_workspace_settings

router = APIRouter()


@router.get("/workspace/settings")
async def get_settings_route(session: AsyncSession = Depends(get_session)) -> WorkspaceSettings:
    return get_workspace_settings(await ensure_workspace(session))


@router.put("/workspace/settings")
async def put_settings_route(body: WorkspaceSettings, session: AsyncSession = Depends(get_session)) -> WorkspaceSettings:
    return await update_workspace_settings(session, await ensure_workspace(session), body)
