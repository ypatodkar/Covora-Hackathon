from uuid import UUID

from covora.observability.redaction import redact
from covora.observability.tracing import RunContext
from covora.research.models import ToolCall


async def record_tool_call(
    ctx: RunContext,
    *,
    span_id: UUID,
    provider: str,
    operation: str,
    request_summary: str,
    result_count: int,
    cache_hit: bool,
    status: str,
    latency_ms: int,
    est_cost_usd: float,
) -> None:
    async with ctx.sessionmaker() as s:
        s.add(
            ToolCall(
                span_id=span_id,
                provider=provider,
                operation=operation,
                request_summary=redact(request_summary, ctx.secrets)[:2000],
                result_count=result_count,
                cache_hit=cache_hit,
                status=status,
                latency_ms=latency_ms,
                est_cost_usd=est_cost_usd,
            )
        )
        await s.commit()
