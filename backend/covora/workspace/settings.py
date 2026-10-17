"""Workspace goals and sending settings, stored in workspace.settings (spec §5.1 step 4, §18)."""

from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from covora.workspace.models import Workspace


class Goals(BaseModel):
    goal_type: Literal["positive_replies", "meetings"] = "positive_replies"
    target: int = Field(10, ge=1)
    expected_positive_rate: float = Field(0.01, gt=0, le=1)
    meetings_per_positive: float = Field(0.5, gt=0, le=1)


class SendingSettings(BaseModel):
    daily_gmail_cap: int = Field(100, ge=1)
    first_batch_size: int = Field(10, ge=1)
    no_reply_window_minutes: int = Field(10, ge=1)
    test_inbox_address: str | None = None


class SimulationSettings(BaseModel):
    profile: Literal["realistic", "accelerated"] = "realistic"
    reply_delay_seconds: list[int] = [5, 30]
    seed: int = 7


class WorkspaceSettings(BaseModel):
    goals: Goals = Goals()
    sending: SendingSettings = SendingSettings()
    simulation: SimulationSettings = SimulationSettings()


def get_workspace_settings(ws: Workspace) -> WorkspaceSettings:
    return WorkspaceSettings.model_validate(ws.settings or {})


async def update_workspace_settings(
    session: AsyncSession, ws: Workspace, value: WorkspaceSettings
) -> WorkspaceSettings:
    ws.settings = value.model_dump(mode="json")
    session.add(ws)
    await session.commit()
    await session.refresh(ws)
    return get_workspace_settings(ws)
