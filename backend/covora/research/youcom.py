"""You.com research provider: cached, budget-guarded, retried, and traced (spec §9.6)."""

import asyncio
import random
import time
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from covora.config import Settings
from covora.observability.redaction import redact
from covora.observability.tracing import RunContext, span
from covora.research.budget import charge, refund
from covora.research.cache import cache_key, get_cached, put_cached
from covora.research.provider import BudgetExceeded, PageContent, ResearchError, SearchResult
from covora.research.tooltrace import record_tool_call

_RETRY_MULTIPLIERS = (1, 2, 4)
_BUDGET_WARNING_SHARE = 0.8


class _Retryable(Exception):
    pass


class YouComProvider:
    name = "youcom"

    def __init__(
        self,
        settings: Settings,
        sessionmaker: async_sessionmaker[AsyncSession],
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._sessionmaker = sessionmaker
        self._http = http_client or httpx.AsyncClient(timeout=settings.youcom_timeout_s)
        self._key = settings.ydc_api_key.get_secret_value() if settings.ydc_api_key else ""

    async def search(self, query: str, *, count: int, ctx: RunContext) -> list[SearchResult]:
        params = {"query": query, "count": count}
        async with span(ctx, "youcom.search", "tool", {"query": query, "count": count}) as sp:
            started = time.monotonic()
            key = cache_key("search", params)
            cached = await get_cached(self._sessionmaker, key, ttl_days=self._settings.youcom_cache_ttl_days)
            if cached is not None:
                results = [_to_result(item) for item in cached]
                await self._trace(ctx, sp.id, "search", query, len(results), True, "ok", started, 0.0)
                return results

            price = self._settings.youcom_search_price_usd
            await self._reserve(ctx, sp, "search", query, price)
            try:
                body = await self._post("/search", params)
            except ResearchError:
                await refund(self._sessionmaker, ctx.workspace_id, price)
                await self._trace(ctx, sp.id, "search", query, 0, False, "error", started, 0.0)
                raise
            web = (body.get("results") or {}).get("web") or []
            await put_cached(self._sessionmaker, key, "search", params, web)
            results = [_to_result(item) for item in web]
            await self._trace(ctx, sp.id, "search", query, len(results), False, "ok", started, price)
        return results

    async def contents(self, urls: list[str], *, ctx: RunContext) -> list[PageContent]:
        summary = " ".join(urls)
        async with span(ctx, "youcom.contents", "tool", {"urls": urls}) as sp:
            started = time.monotonic()
            found: dict[str, PageContent] = {}
            missing: list[str] = []
            for url in urls:
                cached = await get_cached(
                    self._sessionmaker,
                    cache_key("contents", {"url": url}),
                    ttl_days=self._settings.youcom_cache_ttl_days,
                )
                if cached is None:
                    missing.append(url)
                elif cached:
                    found[url] = PageContent(
                        url=url, title=cached.get("title", ""), markdown=cached.get("markdown", "")
                    )

            cost = 0.0
            if missing:
                cost = self._settings.youcom_contents_price_usd * len(missing)
                await self._reserve(ctx, sp, "contents", summary, cost)
                try:
                    items = await self._post("/contents", {"urls": missing, "formats": ["markdown"]})
                except ResearchError:
                    await refund(self._sessionmaker, ctx.workspace_id, cost)
                    await self._trace(ctx, sp.id, "contents", summary, len(found), False, "error", started, 0.0)
                    raise
                returned = {item.get("url"): item for item in items if isinstance(item, dict)}
                for url in missing:
                    item = returned.get(url) or {}
                    markdown = item.get("markdown") or ""
                    page = {"title": item.get("title") or "", "markdown": markdown} if markdown else {}
                    # An empty dict is cached too, so a page with no content isn't paid for twice.
                    await put_cached(
                        self._sessionmaker, cache_key("contents", {"url": url}), "contents", {"url": url}, page
                    )
                    if page:
                        found[url] = PageContent(url=url, title=page["title"], markdown=markdown)

            pages = [found[u] for u in urls if u in found]
            await self._trace(ctx, sp.id, "contents", summary, len(pages), not missing, "ok", started, cost)
        return pages

    async def _reserve(self, ctx: RunContext, sp, operation: str, summary: str, cost: float) -> None:
        if not self._key:
            raise ResearchError("YDC_API_KEY is not set")
        cap = self._settings.youcom_budget_usd
        try:
            new_spend = await charge(self._sessionmaker, ctx.workspace_id, cost, cap=cap)
        except BudgetExceeded:
            await self._trace(ctx, sp.id, operation, summary, 0, False, "refused", time.monotonic(), 0.0)
            raise
        sp.set("youcom_spend_usd", round(new_spend, 4))
        if new_spend >= _BUDGET_WARNING_SHARE * cap:
            sp.set("budget_warning", True)

    async def _post(self, path: str, body: dict) -> Any:
        url = self._settings.youcom_base_url.rstrip("/") + path
        headers = {"X-API-Key": self._key, "Content-Type": "application/json"}
        for attempt in range(len(_RETRY_MULTIPLIERS) + 1):
            try:
                response = await self._http.post(
                    url, json=body, headers=headers, timeout=self._settings.youcom_timeout_s
                )
                if response.status_code == 429 or response.status_code >= 500:
                    raise _Retryable(f"HTTP {response.status_code}")
                if response.status_code >= 400:
                    detail = redact(response.text[:300], self._settings.secret_values())
                    raise ResearchError(f"You.com {path} failed: HTTP {response.status_code}: {detail}")
                return response.json()
            except (_Retryable, httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt == len(_RETRY_MULTIPLIERS):
                    raise ResearchError(f"You.com {path} failed after retries: {exc}") from exc
                delay = self._settings.retry_base_delay_s * _RETRY_MULTIPLIERS[attempt]
                await asyncio.sleep(delay + random.uniform(0, 0.25 * delay))
        raise AssertionError("unreachable")

    async def _trace(
        self,
        ctx: RunContext,
        span_id,
        operation: str,
        summary: str,
        result_count: int,
        cache_hit: bool,
        status: str,
        started: float,
        cost: float,
    ) -> None:
        await record_tool_call(
            ctx,
            span_id=span_id,
            provider=self.name,
            operation=operation,
            request_summary=summary,
            result_count=result_count,
            cache_hit=cache_hit,
            status=status,
            latency_ms=int((time.monotonic() - started) * 1000),
            est_cost_usd=cost,
        )


def _to_result(item: dict) -> SearchResult:
    return SearchResult(
        url=item.get("url", ""),
        title=item.get("title") or "",
        description=item.get("description") or "",
        snippets=[s for s in (item.get("snippets") or []) if isinstance(s, str)],
        page_age=item.get("page_age"),
    )
