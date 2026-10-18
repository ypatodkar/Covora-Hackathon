import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from covora.observability.models import Span, WorkflowRun
from covora.observability.redaction import redact

SpanKind = Literal["stage", "agent", "llm", "tool", "http", "db", "memory"]


@dataclass(frozen=True)
class RunContext:
    run_id: UUID
    trace_id: str
    workspace_id: UUID
    span_id: UUID | None
    sessionmaker: async_sessionmaker[AsyncSession]
    secrets: list[str] = field(default_factory=list)

    def child(self, span_id: UUID) -> "RunContext":
        return replace(self, span_id=span_id)


@dataclass
class SpanHandle:
    id: UUID
    ctx: RunContext
    attributes: dict[str, Any]

    def set(self, key: str, value: Any) -> None:
        self.attributes[key] = value


def _now() -> datetime:
    return datetime.now(UTC)


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


async def start_run(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    kind: str,
    workspace_id: UUID,
    secrets: list[str],
    campaign_id: UUID | None = None,
) -> RunContext:
    run = WorkflowRun(
        kind=kind, workspace_id=workspace_id, campaign_id=campaign_id, status="running", started_at=_now()
    )
    async with sessionmaker() as s:
        s.add(run)
        await s.commit()
    return RunContext(
        run_id=run.id,
        trace_id=uuid4().hex,
        workspace_id=workspace_id,
        span_id=None,
        sessionmaker=sessionmaker,
        secrets=list(secrets),
    )


async def finish_run(
    ctx: RunContext, *, status: Literal["succeeded", "failed"], error: str | None = None
) -> None:
    async with ctx.sessionmaker() as s:
        await s.execute(
            update(WorkflowRun)
            .where(WorkflowRun.id == ctx.run_id)
            .values(status=status, ended_at=_now(), error=redact(error, ctx.secrets) if error else None)
        )
        await s.commit()


@asynccontextmanager
async def span(
    ctx: RunContext, name: str, kind: SpanKind, attributes: dict[str, Any] | None = None
) -> AsyncIterator[SpanHandle]:
    """Trace one unit of work. The row is written on enter (status `running`) so children and
    llm_call/memory_read rows can reference it, then completed on exit. Uses its own session so
    traces survive a rolled-back business transaction."""
    span_id = uuid4()
    started = _now()
    handle = SpanHandle(id=span_id, ctx=ctx.child(span_id), attributes=dict(attributes or {}))
    async with ctx.sessionmaker() as s:
        s.add(
            Span(
                id=span_id,
                run_id=ctx.run_id,
                trace_id=ctx.trace_id,
                parent_span_id=ctx.span_id,
                name=name,
                kind=kind,
                status="running",
                started_at=started,
                attributes=_jsonable(redact(handle.attributes, ctx.secrets)),
            )
        )
        await s.commit()
    try:
        yield handle
    except BaseException as exc:
        message = redact(str(exc) or type(exc).__name__, ctx.secrets)
        await _close(ctx, span_id, started, handle.attributes, status="error", error=message)
        raise
    else:
        await _close(ctx, span_id, started, handle.attributes, status="ok", error=None)


async def _close(
    ctx: RunContext, span_id: UUID, started: datetime, attributes: dict, *, status: str, error: str | None
) -> None:
    duration_ms = int((_now() - started).total_seconds() * 1000)
    async with ctx.sessionmaker() as s:
        await s.execute(
            update(Span)
            .where(Span.id == span_id)
            .values(
                status=status,
                duration_ms=duration_ms,
                attributes=_jsonable(redact(attributes, ctx.secrets)),
                error=error,
            )
        )
        await s.commit()
