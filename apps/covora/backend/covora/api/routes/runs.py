from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from covora.api.deps import Services, get_services, get_session
from covora.api.errors import ApiError
from covora.memory.models import MemoryItem, MemoryRead
from covora.observability.models import LlmCall, Span, WorkflowRun

router = APIRouter()


class RunSummary(BaseModel):
    id: UUID
    kind: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    duration_ms: int | None
    error: str | None
    llm_calls: int
    prompt_tokens: int
    completion_tokens: int
    est_cost_usd: float | None


class SpanOut(BaseModel):
    id: UUID
    parent_span_id: UUID | None
    name: str
    kind: str
    status: str
    started_at: datetime
    duration_ms: int | None
    attributes: dict[str, Any]
    error: str | None


class LlmCallOut(BaseModel):
    id: UUID
    span_id: UUID
    task: str
    routing_mode: str
    requested_model: str
    actual_model: str
    routing_reason: str
    fallback_used: bool
    fallback_reason: str | None
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    est_cost_usd: float | None
    output_valid: bool
    retries: int
    response_text: str | None = None
    created_at: datetime


class RunDetail(BaseModel):
    run: RunSummary
    spans: list[SpanOut]
    llm_calls: list[LlmCallOut]


class WorkingMemoryItem(BaseModel):
    memory_item_id: UUID
    kind: str
    subtype: str
    source: str
    summary: str
    evidence_level: str | None
    reason: str
    rank: int


def _summary_query():
    return (
        select(
            WorkflowRun,
            func.count(LlmCall.id),
            func.coalesce(func.sum(LlmCall.prompt_tokens), 0),
            func.coalesce(func.sum(LlmCall.completion_tokens), 0),
            func.sum(LlmCall.est_cost_usd),
        )
        .outerjoin(Span, Span.run_id == WorkflowRun.id)
        .outerjoin(LlmCall, LlmCall.span_id == Span.id)
        .group_by(WorkflowRun.id)
    )


def _summary(row) -> RunSummary:
    run, calls, prompt_tokens, completion_tokens, cost = row
    duration = int((run.ended_at - run.started_at).total_seconds() * 1000) if run.ended_at else None
    return RunSummary(
        id=run.id,
        kind=run.kind,
        status=run.status,
        started_at=run.started_at,
        ended_at=run.ended_at,
        duration_ms=duration,
        error=run.error,
        llm_calls=calls,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        est_cost_usd=cost,
    )


@router.get("/runs")
async def list_runs(
    kind: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[RunSummary]:
    stmt = _summary_query().order_by(WorkflowRun.started_at.desc()).limit(limit)
    if kind:
        stmt = stmt.where(WorkflowRun.kind == kind)
    return [_summary(row) for row in (await session.execute(stmt)).all()]


@router.get("/runs/{run_id}")
async def get_run(
    run_id: UUID,
    services: Services = Depends(get_services),
    session: AsyncSession = Depends(get_session),
) -> RunDetail:
    row = (await session.execute(_summary_query().where(WorkflowRun.id == run_id))).one_or_none()
    if row is None:
        raise ApiError("not_found", "That run does not exist.", 404)
    spans = (await session.execute(select(Span).where(Span.run_id == run_id).order_by(Span.started_at))).scalars()
    calls = (
        await session.execute(
            select(LlmCall)
            .join(Span, LlmCall.span_id == Span.id)
            .where(Span.run_id == run_id)
            .order_by(LlmCall.created_at)
        )
    ).scalars()
    keep_text = services.settings.log_llm_payloads
    return RunDetail(
        run=_summary(row),
        spans=[SpanOut.model_validate(s, from_attributes=True) for s in spans],
        llm_calls=[
            LlmCallOut.model_validate(c, from_attributes=True).model_copy(
                update={"response_text": c.response_text if keep_text else None}
            )
            for c in calls
        ],
    )


@router.get("/runs/{run_id}/spans/{span_id}/memory")
async def get_working_memory(
    run_id: UUID, span_id: UUID, session: AsyncSession = Depends(get_session)
) -> list[WorkingMemoryItem]:
    span_row = await session.get(Span, span_id)
    if span_row is None or span_row.run_id != run_id:
        raise ApiError("not_found", "That step does not exist in this run.", 404)
    rows = await session.execute(
        select(MemoryRead, MemoryItem)
        .join(MemoryItem, MemoryRead.memory_item_id == MemoryItem.id)
        .where(MemoryRead.span_id == span_id)
        .order_by(MemoryRead.rank)
    )
    return [
        WorkingMemoryItem(
            memory_item_id=item.id,
            kind=item.kind,
            subtype=item.subtype,
            source=item.source,
            summary=item.summary,
            evidence_level=item.evidence_level,
            reason=read.reason,
            rank=read.rank,
        )
        for read, item in rows.all()
    ]
