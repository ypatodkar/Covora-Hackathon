import pytest

from covora.observability.tracing import finish_run, span, start_run
from tests.helpers import fetch_spans, get_run


async def test_nested_spans_record_parents(sessionmaker, workspace):
    ctx = await start_run(sessionmaker, kind="icp", workspace_id=workspace.id, secrets=[])
    async with span(ctx, "outer", "agent") as outer:
        async with span(outer.ctx, "inner", "llm") as inner:
            inner.set("model", "nano")
    rows = await fetch_spans(sessionmaker, ctx.run_id)
    inner_row = next(r for r in rows if r.name == "inner")
    assert inner_row.parent_span_id == outer.id and inner_row.attributes["model"] == "nano"


async def test_span_error_is_redacted(sessionmaker, workspace):
    ctx = await start_run(sessionmaker, kind="icp", workspace_id=workspace.id, secrets=["nvapi-test-key-000000"])
    with pytest.raises(RuntimeError):
        async with span(ctx, "call", "llm"):
            raise RuntimeError("401 Authorization: Bearer nvapi-test-key-000000")
    row = (await fetch_spans(sessionmaker, ctx.run_id))[0]
    assert row.status == "error" and "nvapi-test-key-000000" not in row.error


async def test_finish_run_failed(sessionmaker, workspace):
    ctx = await start_run(sessionmaker, kind="icp", workspace_id=workspace.id, secrets=[])
    await finish_run(ctx, status="failed", error="boom")
    run = await get_run(sessionmaker, ctx.run_id)
    assert run.status == "failed" and run.ended_at is not None
