"""Query helpers shared by tests (kept out of conftest so tests can import them)."""

from uuid import UUID

from sqlalchemy import select

from covora.observability.models import LlmCall, Span, WorkflowRun


async def fetch_spans(sessionmaker, run_id: UUID) -> list[Span]:
    async with sessionmaker() as s:
        return list((await s.execute(select(Span).where(Span.run_id == run_id).order_by(Span.started_at))).scalars())


async def get_run(sessionmaker, run_id: UUID) -> WorkflowRun:
    async with sessionmaker() as s:
        return (await s.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))).scalar_one()


async def latest_llm_call(sessionmaker) -> LlmCall:
    async with sessionmaker() as s:
        return (await s.execute(select(LlmCall).order_by(LlmCall.created_at.desc()).limit(1))).scalar_one()
