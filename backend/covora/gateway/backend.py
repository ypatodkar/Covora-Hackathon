from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass
class ChatResponse:
    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str


class BackendError(Exception):
    """A failed model call. `retryable` covers 429, 5xx, timeouts, and connection errors."""

    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class ChatBackend(Protocol):
    async def chat(
        self,
        *,
        model: str,
        messages: list[dict],
        json_schema: dict | None,
        reasoning: bool,
        timeout_s: float,
    ) -> ChatResponse: ...

    async def embed(
        self,
        *,
        model: str,
        texts: list[str],
        input_type: Literal["query", "passage"],
        timeout_s: float,
    ) -> list[list[float]]: ...
