"""You.com budget guard: spend is reserved atomically before a call and refunded if it fails."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from covora.research.provider import BudgetExceeded

_CHARGE = text(
    "UPDATE workspace SET youcom_spend_usd = youcom_spend_usd + :cost "
    "WHERE id = :id AND youcom_spend_usd + :cost <= :cap RETURNING youcom_spend_usd"
)


async def charge(
    sessionmaker: async_sessionmaker[AsyncSession], workspace_id: UUID, cost: float, *, cap: float
) -> float:
    async with sessionmaker() as s:
        new_spend = (await s.execute(_CHARGE, {"cost": cost, "id": workspace_id, "cap": cap})).scalar_one_or_none()
        await s.commit()
    if new_spend is None:
        raise BudgetExceeded(f"You.com budget of ${cap:.2f} reached")
    return float(new_spend)


async def refund(sessionmaker: async_sessionmaker[AsyncSession], workspace_id: UUID, cost: float) -> None:
    async with sessionmaker() as s:
        await s.execute(
            text("UPDATE workspace SET youcom_spend_usd = GREATEST(youcom_spend_usd - :cost, 0) WHERE id = :id"),
            {"cost": cost, "id": workspace_id},
        )
        await s.commit()


async def spend(sessionmaker: async_sessionmaker[AsyncSession], workspace_id: UUID) -> float:
    async with sessionmaker() as s:
        value = (
            await s.execute(text("SELECT youcom_spend_usd FROM workspace WHERE id = :id"), {"id": workspace_id})
        ).scalar_one()
    return float(value)
