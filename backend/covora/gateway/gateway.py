"""The one path every model call takes (spec §15): routing, validation, repair, fallback, logging."""

import asyncio
import math
import random
import time
from dataclasses import dataclass, field
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ValidationError

from covora.config import Settings
from covora.gateway.backend import BackendError, ChatBackend, ChatResponse
from covora.gateway.output import extract_json, strip_reasoning
from covora.gateway.pricing import estimate_cost
from covora.gateway.router import ModelIds, choose_route, other_tier
from covora.gateway.tasks import REASONING_DEFAULT, TaskType, Tier
from covora.observability.models import LlmCall
from covora.observability.redaction import redact
from covora.observability.tracing import RunContext, span

T = TypeVar("T", bound=BaseModel)

_RETRY_MULTIPLIERS = (1, 2, 4)
_EMBED_BATCH = 32
_REPAIR_PROMPT = (
    "Your previous reply was not valid JSON for the required schema. Error: {error}. "
    "Reply with only the corrected JSON."
)


class GatewayError(Exception):
    """Every attempt on every tier failed."""


@dataclass
class RoutingInfo:
    mode: str
    decision_reason: str
    requested_model: str
    actual_model: str
    fallback_used: bool
    fallback_reason: str | None


@dataclass
class GatewayResult(Generic[T]):
    output: T
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    est_cost_usd: float | None
    retries: int
    routing: RoutingInfo
    llm_call_id: UUID


class _AttemptFailed(Exception):
    pass


@dataclass
class _Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    errors: list[str] = field(default_factory=list)


class ModelGateway:
    def __init__(self, backend: ChatBackend, settings: Settings) -> None:
        self._backend = backend
        self._settings = settings
        self._models = ModelIds(nano=settings.nemotron_nano_model, super=settings.nemotron_super_model)
        self._semaphores = {
            Tier.nano: asyncio.Semaphore(settings.nano_concurrency),
            Tier.super: asyncio.Semaphore(settings.super_concurrency),
        }
        self._timeouts = {Tier.nano: settings.nano_timeout_s, Tier.super: settings.super_timeout_s}

    async def complete(
        self,
        task: TaskType,
        messages: list[dict],
        *,
        schema: type[T] | None,
        ctx: RunContext,
        reasoning: bool | None = None,
    ) -> GatewayResult[T]:
        decision = choose_route(task, self._settings.routing_mode, self._models)
        usage = _Usage()
        started = time.monotonic()
        attrs = {"task": str(task), "routing_mode": decision.mode, "requested_model": decision.model}
        async with span(ctx, f"llm:{task}", "llm", attrs) as sp:
            output: T | str | None = None
            text, actual_model, fallback_reason, last_error = "", decision.model, None, ""
            for index, tier in enumerate((decision.tier, other_tier(decision.tier))):
                model = self._models.for_tier(tier)
                actual_model = model
                use_reasoning = REASONING_DEFAULT[tier] if reasoning is None else reasoning
                try:
                    output, text = await self._attempt(tier, model, messages, schema, use_reasoning, usage)
                    break
                except _AttemptFailed as exc:
                    last_error = str(exc)
                    if index == 0:
                        fallback_reason = redact(last_error, ctx.secrets)

            latency_ms = int((time.monotonic() - started) * 1000)
            cost = estimate_cost(
                actual_model, usage.prompt_tokens, usage.completion_tokens, self._settings.model_prices
            )
            routing = RoutingInfo(
                mode=decision.mode,
                decision_reason=decision.reason,
                requested_model=decision.model,
                actual_model=actual_model,
                fallback_used=fallback_reason is not None,
                fallback_reason=fallback_reason,
            )
            sp.set("actual_model", actual_model)
            sp.set("fallback_used", routing.fallback_used)
            sp.set("prompt_tokens", usage.prompt_tokens)
            sp.set("completion_tokens", usage.completion_tokens)
            call_id = await self._log(
                ctx,
                span_id=sp.id,
                task=str(task),
                routing=routing,
                usage=usage,
                latency_ms=latency_ms,
                cost=cost,
                output_valid=output is not None,
                messages=messages,
                text=text,
            )
            if output is None:
                raise GatewayError(f"all model attempts failed for {task}: {redact(last_error, ctx.secrets)}")

        return GatewayResult(
            output=output,
            text=text,
            model=actual_model,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            latency_ms=latency_ms,
            est_cost_usd=cost,
            retries=max(usage.calls - 1, 0),
            routing=routing,
            llm_call_id=call_id,
        )

    async def embed(
        self, texts: list[str], *, ctx: RunContext, input_type: Literal["query", "passage"]
    ) -> list[list[float]]:
        model = self._settings.nemotron_embed_model
        usage = _Usage(prompt_tokens=sum(math.ceil(len(t) / 4) for t in texts))
        started = time.monotonic()
        async with span(ctx, "llm:embedding", "llm", {"task": "embedding", "count": len(texts)}) as sp:
            vectors: list[list[float]] = []
            error: str | None = None
            try:
                for i in range(0, len(texts), _EMBED_BATCH):
                    batch = texts[i : i + _EMBED_BATCH]
                    vectors.extend(await self._embed_with_retries(model, batch, input_type, usage))
                bad = [len(v) for v in vectors if len(v) != self._settings.nemotron_embed_dim]
                if bad:
                    error = (
                        f"embedding dimension {bad[0]} != NEMOTRON_EMBED_DIM "
                        f"{self._settings.nemotron_embed_dim}"
                    )
            except _AttemptFailed as exc:
                error = str(exc)
            routing = RoutingInfo("n/a", "embeddings are not routed", model, model, False, None)
            await self._log(
                ctx,
                span_id=sp.id,
                task=str(TaskType.embedding),
                routing=routing,
                usage=usage,
                latency_ms=int((time.monotonic() - started) * 1000),
                cost=estimate_cost(model, usage.prompt_tokens, 0, self._settings.model_prices),
                output_valid=error is None,
                messages=None,
                text="",
            )
            if error is not None:
                raise GatewayError(redact(error, ctx.secrets))
        return vectors

    async def _attempt(
        self,
        tier: Tier,
        model: str,
        messages: list[dict],
        schema: type[T] | None,
        reasoning: bool,
        usage: _Usage,
    ) -> tuple[T | str, str]:
        json_schema = schema.model_json_schema() if schema else None
        msgs = list(messages)
        response = await self._chat_with_retries(tier, model, msgs, json_schema, reasoning, usage)
        text = strip_reasoning(response.text)
        if schema is None:
            return text, text
        try:
            return schema.model_validate_json(extract_json(response.text)), text
        except (ValueError, ValidationError) as err:
            repair = _REPAIR_PROMPT.format(error=str(err)[:1000])
            msgs = msgs + [{"role": "assistant", "content": text}, {"role": "user", "content": repair}]
        response = await self._chat_with_retries(tier, model, msgs, json_schema, reasoning, usage)
        text = strip_reasoning(response.text)
        try:
            return schema.model_validate_json(extract_json(response.text)), text
        except (ValueError, ValidationError) as err:
            raise _AttemptFailed(f"{model} returned invalid output after repair: {str(err)[:500]}") from err

    async def _chat_with_retries(
        self,
        tier: Tier,
        model: str,
        messages: list[dict],
        json_schema: dict | None,
        reasoning: bool,
        usage: _Usage,
    ) -> ChatResponse:
        for attempt in range(len(_RETRY_MULTIPLIERS) + 1):
            try:
                async with self._semaphores[tier]:
                    response = await self._backend.chat(
                        model=model,
                        messages=messages,
                        json_schema=json_schema,
                        reasoning=reasoning,
                        timeout_s=self._timeouts[tier],
                    )
            except BackendError as exc:
                usage.calls += 1
                if not exc.retryable or attempt == len(_RETRY_MULTIPLIERS):
                    raise _AttemptFailed(f"{model}: {exc}") from exc
                await self._backoff(attempt)
                continue
            usage.calls += 1
            usage.prompt_tokens += response.prompt_tokens
            usage.completion_tokens += response.completion_tokens
            return response
        raise AssertionError("unreachable")

    async def _embed_with_retries(
        self, model: str, texts: list[str], input_type: Literal["query", "passage"], usage: _Usage
    ) -> list[list[float]]:
        for attempt in range(len(_RETRY_MULTIPLIERS) + 1):
            try:
                async with self._semaphores[Tier.nano]:
                    vectors = await self._backend.embed(
                        model=model, texts=texts, input_type=input_type, timeout_s=self._timeouts[Tier.nano]
                    )
            except BackendError as exc:
                usage.calls += 1
                if not exc.retryable or attempt == len(_RETRY_MULTIPLIERS):
                    raise _AttemptFailed(f"{model}: {exc}") from exc
                await self._backoff(attempt)
                continue
            usage.calls += 1
            return vectors
        raise AssertionError("unreachable")

    async def _backoff(self, attempt: int) -> None:
        delay = self._settings.retry_base_delay_s * _RETRY_MULTIPLIERS[attempt]
        await asyncio.sleep(delay + random.uniform(0, 0.25 * delay))

    async def _log(
        self,
        ctx: RunContext,
        *,
        span_id: UUID,
        task: str,
        routing: RoutingInfo,
        usage: _Usage,
        latency_ms: int,
        cost: float | None,
        output_valid: bool,
        messages: list[dict] | None,
        text: str,
    ) -> UUID:
        keep_payloads = self._settings.log_llm_payloads
        row = LlmCall(
            span_id=span_id,
            task=task,
            routing_mode=routing.mode,
            requested_model=routing.requested_model,
            actual_model=routing.actual_model,
            routing_reason=routing.decision_reason,
            fallback_used=routing.fallback_used,
            fallback_reason=routing.fallback_reason,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            latency_ms=latency_ms,
            est_cost_usd=cost,
            output_valid=output_valid,
            retries=max(usage.calls - 1, 0),
            request_payload=redact(messages, ctx.secrets) if keep_payloads and messages else None,
            response_text=redact(text, ctx.secrets) if keep_payloads and text else None,
        )
        async with ctx.sessionmaker() as s:
            s.add(row)
            await s.commit()
        return row.id
