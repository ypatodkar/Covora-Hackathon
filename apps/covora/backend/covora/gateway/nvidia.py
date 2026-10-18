"""NVIDIA hosted API backend (build.nvidia.com, OpenAI-compatible). The only module that imports openai."""

from typing import Literal

import httpx
import openai
from openai import AsyncOpenAI

from covora.config import Settings
from covora.gateway.backend import BackendError, ChatResponse


class NvidiaBackend:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        key = settings.nvidia_api_key.get_secret_value() if settings.nvidia_api_key else ""
        self._has_key = bool(key)
        self._structured_mode = settings.nvidia_structured_mode
        # Retries belong to the gateway, so the SDK must not retry on its own.
        self._client = AsyncOpenAI(
            base_url=settings.nvidia_base_url,
            api_key=key or "missing",
            max_retries=0,
            http_client=http_client,
        )

    async def chat(
        self,
        *,
        model: str,
        messages: list[dict],
        json_schema: dict | None,
        reasoning: bool,
        timeout_s: float,
    ) -> ChatResponse:
        self._require_key()
        extra_body: dict = {"chat_template_kwargs": {"enable_thinking": reasoning}}
        kwargs: dict = {}
        if json_schema is not None:
            if self._structured_mode == "guided_json":
                extra_body["nvext"] = {"guided_json": json_schema}
            elif self._structured_mode == "response_format":
                kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": "output", "schema": json_schema},
                }
        try:
            response = await self._client.chat.completions.create(
                model=model, messages=messages, extra_body=extra_body, timeout=timeout_s, **kwargs
            )
        except openai.OpenAIError as exc:
            raise _to_backend_error(exc) from exc

        message = response.choices[0].message
        usage = response.usage
        # Only `content` is used: any `reasoning_content` field is deliberately ignored (spec §15.5).
        return ChatResponse(
            text=message.content or "",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            model=response.model or model,
        )

    async def embed(
        self,
        *,
        model: str,
        texts: list[str],
        input_type: Literal["query", "passage"],
        timeout_s: float,
    ) -> list[list[float]]:
        self._require_key()
        try:
            response = await self._client.embeddings.create(
                model=model,
                input=texts,
                encoding_format="float",
                extra_body={"input_type": input_type, "truncate": "END"},
                timeout=timeout_s,
            )
        except openai.OpenAIError as exc:
            raise _to_backend_error(exc) from exc
        return [item.embedding for item in sorted(response.data, key=lambda d: d.index)]

    def _require_key(self) -> None:
        if not self._has_key:
            raise BackendError("NVIDIA_API_KEY is not set", retryable=False)


def _to_backend_error(exc: openai.OpenAIError) -> BackendError:
    if isinstance(exc, openai.APITimeoutError):
        return BackendError(f"timeout: {exc}", retryable=True)
    if isinstance(exc, openai.APIConnectionError):
        return BackendError(f"connection error: {exc}", retryable=True)
    if isinstance(exc, openai.APIStatusError):
        status = exc.status_code
        return BackendError(f"HTTP {status}: {exc.message}", status=status, retryable=status == 429 or status >= 500)
    return BackendError(str(exc), retryable=False)
