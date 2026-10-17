import copy
import json

import httpx
import pytest

from covora.gateway.backend import BackendError
from covora.gateway.nvidia import NvidiaBackend
from tests.fakes import MSGS

CHAT_OK = {
    "id": "chat-1",
    "object": "chat.completion",
    "created": 0,
    "model": "m",
    "choices": [
        {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": '{"ok": true}'}}
    ],
    "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
}
CHAT_WITH_REASONING_CONTENT = copy.deepcopy(CHAT_OK)
CHAT_WITH_REASONING_CONTENT["choices"][0]["message"]["reasoning_content"] = "hidden"


@pytest.fixture
def nvidia_with_transport(settings):
    def build(handler):
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return NvidiaBackend(settings, http_client=client)

    return build


async def test_maps_429_to_retryable(nvidia_with_transport):
    backend = nvidia_with_transport(lambda req: httpx.Response(429, json={"error": "slow down"}))
    with pytest.raises(BackendError) as e:
        await backend.chat(
            model="m", messages=[{"role": "user", "content": "hi"}], json_schema=None, reasoning=False, timeout_s=5
        )
    assert e.value.retryable and e.value.status == 429


async def test_sends_guided_json_and_thinking_flag(nvidia_with_transport):
    seen = {}

    def handler(req):
        seen.update(json.loads(req.content))
        return httpx.Response(200, json=CHAT_OK)

    backend = nvidia_with_transport(handler)
    await backend.chat(model="m", messages=MSGS, json_schema={"type": "object"}, reasoning=True, timeout_s=5)
    assert seen["nvext"]["guided_json"] == {"type": "object"}
    assert seen["chat_template_kwargs"] == {"enable_thinking": True}


async def test_ignores_reasoning_content(nvidia_with_transport):
    backend = nvidia_with_transport(lambda req: httpx.Response(200, json=CHAT_WITH_REASONING_CONTENT))
    r = await backend.chat(model="m", messages=MSGS, json_schema=None, reasoning=True, timeout_s=5)
    assert r.text == '{"ok": true}'
