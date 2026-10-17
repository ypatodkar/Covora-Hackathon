"""Procedural memory: prompts live as files and are versioned in the database (spec §7.2)."""

from pathlib import Path
from string import Template

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from covora.memory.models import PromptVersion

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


async def sync_prompts(session: AsyncSession) -> None:
    """Record a new active version for every prompt file whose text changed."""
    for path in sorted(PROMPTS_DIR.glob("*.md")):
        name, body = path.stem, path.read_text()
        active = (
            await session.execute(select(PromptVersion).where(PromptVersion.name == name, PromptVersion.active))
        ).scalar_one_or_none()
        if active is not None and active.body == body:
            continue
        latest = (
            await session.execute(select(func.max(PromptVersion.version)).where(PromptVersion.name == name))
        ).scalar() or 0
        if active is not None:
            active.active = False
        session.add(PromptVersion(name=name, version=latest + 1, body=body, active=True))
    await session.commit()


async def get_prompt(session: AsyncSession, name: str) -> PromptVersion:
    prompt = (
        await session.execute(select(PromptVersion).where(PromptVersion.name == name, PromptVersion.active))
    ).scalar_one_or_none()
    if prompt is None:
        raise LookupError(f"prompt {name!r} not found; is covora/prompts/{name}.md present?")
    return prompt


def render_prompt(body: str, **values: object) -> str:
    """Fill `$placeholders`; a missing value raises KeyError."""
    return Template(body).substitute(**values)
