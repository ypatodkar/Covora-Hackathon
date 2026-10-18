from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from covora.workspace.models import Workspace


class WorkspaceProfile(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    website: str | None = None
    description: str | None = None
    value_props: list[str] = []
    offering_type: Literal["sales_call", "dealer"] = "sales_call"


async def ensure_workspace(session: AsyncSession) -> Workspace:
    """Return the single workspace, creating it on first run."""
    await session.execute(
        insert(Workspace).values(name="My company").on_conflict_do_nothing(index_elements=["singleton"])
    )
    await session.commit()
    return (await session.execute(select(Workspace))).scalar_one()


async def update_profile(session: AsyncSession, ws: Workspace, data: WorkspaceProfile) -> Workspace:
    for field, value in data.model_dump().items():
        setattr(ws, field, value)
    session.add(ws)
    await session.commit()
    await session.refresh(ws)
    return ws
