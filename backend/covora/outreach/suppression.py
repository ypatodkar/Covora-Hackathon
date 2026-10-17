from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from covora.outreach.models import Suppression


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def is_suppressed(session: AsyncSession, workspace_id: UUID, email: str | None) -> bool:
    if not email:
        return False
    stmt = select(Suppression.email_normalized).where(
        Suppression.workspace_id == workspace_id, Suppression.email_normalized == normalize_email(email)
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def suppress(
    session: AsyncSession, workspace_id: UUID, email: str, reason: str, source_email_id: UUID | None = None
) -> None:
    await session.execute(
        insert(Suppression)
        .values(
            email_normalized=normalize_email(email),
            workspace_id=workspace_id,
            reason=reason,
            source_email_id=source_email_id,
        )
        .on_conflict_do_nothing(index_elements=["email_normalized"])
    )
    await session.commit()
