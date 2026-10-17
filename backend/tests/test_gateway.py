import pytest

from covora.gateway.backend import BackendError
from covora.gateway.gateway import GatewayError
from covora.gateway.tasks import TaskType
from tests.fakes import MSGS, NANO, SUPER, Answer
from tests.helpers import latest_llm_call


async def test_valid_output(gateway, fake_backend, ctx):
    fake_backend.queue(SUPER, '{"value": 3}')
    r = await gateway.complete(TaskType.icp_parsing, [{"role": "user", "content": "x"}], schema=Answer, ctx=ctx)
    assert r.output.value == 3 and r.retries == 0 and r.routing.fallback_used is False


async def test_repair_retry_same_model(gateway, fake_backend, ctx):
    fake_backend.queue(SUPER, "not json", '{"value": 4}')
    r = await gateway.complete(TaskType.icp_parsing, MSGS, schema=Answer, ctx=ctx)
    assert r.output.value == 4 and r.retries == 1 and r.model == SUPER
    assert "not valid JSON" in fake_backend.calls[1]["messages"][-1]["content"]


async def test_fallback_to_other_tier(gateway, fake_backend, ctx):
    fake_backend.queue(SUPER, "bad", "still bad")
    fake_backend.queue(NANO, '{"value": 5}')
    r = await gateway.complete(TaskType.icp_parsing, MSGS, schema=Answer, ctx=ctx)
    assert r.model == NANO and r.routing.fallback_used and r.routing.actual_model == NANO


async def test_retryable_transport_error_is_retried(gateway, fake_backend, ctx):
    fake_backend.queue(SUPER, BackendError("429", status=429, retryable=True), '{"value": 1}')
    r = await gateway.complete(TaskType.icp_parsing, MSGS, schema=Answer, ctx=ctx)
    assert r.output.value == 1 and r.model == SUPER


async def test_all_attempts_fail_raises_and_logs(gateway, fake_backend, ctx, sessionmaker):
    fake_backend.queue(SUPER, *[BackendError("503", status=503, retryable=True)] * 4)
    fake_backend.queue(NANO, *[BackendError("503", status=503, retryable=True)] * 4)
    with pytest.raises(GatewayError):
        await gateway.complete(TaskType.icp_parsing, MSGS, schema=Answer, ctx=ctx)
    call = await latest_llm_call(sessionmaker)
    assert call.output_valid is False and call.fallback_used is True


async def test_reasoning_never_stored(gateway, fake_backend, ctx, sessionmaker):
    fake_backend.queue(SUPER, '<think>internal chain</think>{"value": 2}')
    await gateway.complete(TaskType.icp_parsing, MSGS, schema=Answer, ctx=ctx)
    call = await latest_llm_call(sessionmaker)
    assert "internal chain" not in (call.response_text or "")


async def test_llm_call_row_fields(gateway, fake_backend, ctx, sessionmaker):
    fake_backend.queue(SUPER, '{"value": 3}')
    await gateway.complete(TaskType.icp_parsing, MSGS, schema=Answer, ctx=ctx)
    call = await latest_llm_call(sessionmaker)
    assert call.task == "icp_parsing" and call.routing_mode == "fixed"
    assert call.routing_reason == "fixed: icp_parsing → super" and call.requested_model == SUPER


async def test_embed_logs_call(gateway, ctx, sessionmaker, settings):
    vecs = await gateway.embed(["a b", "c d"], ctx=ctx, input_type="passage")
    assert len(vecs) == 2 and len(vecs[0]) == settings.nemotron_embed_dim
    assert (await latest_llm_call(sessionmaker)).task == "embedding"
