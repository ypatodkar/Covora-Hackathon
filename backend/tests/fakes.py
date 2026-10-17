"""Test doubles: a scripted chat backend and deterministic embeddings."""

import hashlib
import math
import re
from collections import defaultdict, deque

from pydantic import BaseModel

from covora.gateway.backend import ChatResponse

NANO = "nvidia/nemotron-nano-3-30b-a3b"
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
        return [fake_embedding(t, self.dim) for t in texts]
