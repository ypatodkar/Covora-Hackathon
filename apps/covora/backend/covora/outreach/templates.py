import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from covora.outreach.models import Template

SEED = Path(__file__).with_name("templates_seed.json")


async def sync_templates(session: AsyncSession, workspace_id: UUID) -> int:
    """Seed the starter templates once (by name); never overwrite the user's edits."""
    existing = set(
        (await session.execute(select(Template.name).where(Template.workspace_id == workspace_id))).scalars()
    )
    added = 0
    for spec in json.loads(SEED.read_text()):
        if spec["name"] not in existing:
            session.add(Template(workspace_id=workspace_id, **spec))
            added += 1
    await session.commit()
    return added


async def pick_default_templates(session: AsyncSession, workspace_id: UUID, offering_type: str) -> list[Template]:
    """Two active templates for this offering, preferring different lengths so arm A ≠ arm B."""
    rows = [
        t
        for t in (
            await session.execute(
                select(Template).where(Template.workspace_id == workspace_id, Template.active).order_by(Template.name)
            )
        ).scalars()
        if offering_type in (t.offering_types or [])
    ]
    if len(rows) < 2:
        raise LookupError("need at least two active templates for this offering type")
    first = rows[0]
    second = next((t for t in rows[1:] if t.length != first.length), rows[1])
    return [first, second]
