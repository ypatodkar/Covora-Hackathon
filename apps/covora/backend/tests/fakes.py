"""Test doubles: a scripted chat backend and deterministic embeddings."""

import hashlib
import json
import math
import re
from collections import defaultdict, deque

from pydantic import BaseModel

from covora.gateway.backend import BackendError, ChatResponse

NANO = "nvidia/nemotron-3.5-lightning-30b-a3b"
SUPER = "nvidia/nemotron-3-super-120b-a12b"
MSGS = [{"role": "user", "content": "x"}]


class Answer(BaseModel):
    value: int


def fake_embedding(text: str, dim: int) -> list[float]:
    """Hashed bag of words, L2-normalized: texts sharing words have higher cosine similarity."""
    vec = [0.0] * dim
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        vec[int(hashlib.sha256(word.encode()).hexdigest(), 16) % dim] += 1.0
    if not any(vec):
        vec[0] = 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec]


class FakeChatBackend:
    def __init__(self, dim: int = 2048) -> None:
        self.dim = dim
        self.fail_embeddings = False
        self.calls: list[dict] = []
        self.embed_calls: list[dict] = []
        self._queues: dict[str, deque] = defaultdict(deque)

    def queue(self, model: str, *items: str | Exception) -> None:
        self._queues[model].extend(items)

    async def chat(self, *, model, messages, json_schema, reasoning, timeout_s) -> ChatResponse:
        self.calls.append(
            {
                "model": model,
                "messages": [dict(m) for m in messages],
                "json_schema": json_schema,
                "reasoning": reasoning,
            }
        )
        if not self._queues[model]:
            raise AssertionError(f"no scripted response left for {model}")
        item = self._queues[model].popleft()
        if isinstance(item, Exception):
            raise item
        return ChatResponse(text=item, prompt_tokens=10, completion_tokens=5, model=model)

    async def embed(self, *, model, texts, input_type, timeout_s) -> list[list[float]]:
        self.embed_calls.append({"model": model, "texts": list(texts), "input_type": input_type})
        if self.fail_embeddings:
            raise BackendError("HTTP 404: embedding model not found", status=404, retryable=False)
        return [fake_embedding(t, self.dim) for t in texts]


def _last_json_user_message(messages: list[dict]) -> dict:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        try:
            value = json.loads(message["content"])
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(value, dict):
            return value
    return {}


class ScriptedBackend(FakeChatBackend):
    """Answers each call with a handler chosen by the requested schema's title (the Pydantic class name)."""

    def __init__(self, dim: int, handlers: dict) -> None:
        super().__init__(dim)
        self.handlers = dict(handlers)
        self._failures: dict[str, int] = {}

    def override(self, title: str, fn) -> None:
        self.handlers[title] = fn

    def fail_next(self, title: str, times: int) -> None:
        self._failures[title] = times

    def inputs_for(self, title: str) -> list[dict]:
        return [c["input"] for c in self.calls if c.get("title") == title]

    async def chat(self, *, model, messages, json_schema, reasoning, timeout_s) -> ChatResponse:
        title = (json_schema or {}).get("title")
        user = _last_json_user_message(messages)
        self.calls.append({"model": model, "title": title, "input": user, "messages": [dict(m) for m in messages]})
        if self._failures.get(title):
            self._failures[title] -= 1
            raise BackendError(f"scripted failure for {title}", retryable=False)
        handler = self.handlers.get(title)
        if handler is None:
            raise AssertionError(f"no scripted handler for schema {title!r}")
        return ChatResponse(text=json.dumps(handler(user)), prompt_tokens=10, completion_tokens=5, model=model)
