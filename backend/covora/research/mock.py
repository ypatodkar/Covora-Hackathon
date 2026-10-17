"""A fixture web for tests and the RESEARCH_PROVIDER=mock development mode. Everything it finds is synthetic."""

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from covora.observability.tracing import RunContext, span
from covora.research.budget import charge
from covora.research.provider import BudgetExceeded, PageContent, SearchResult
from covora.research.tooltrace import record_tool_call

_WORD = re.compile(r"[a-z0-9]{3,}")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


@dataclass
class MockPage:
    url: str
    title: str
    description: str
    markdown: str


@dataclass
class ChargeWith:
    """Test hook: make the mock charge the real budget guard, to exercise budget handling."""

    sessionmaker: async_sessionmaker[AsyncSession]
    cap: float
    price: float


class MockProvider:
    name = "mock"

    def __init__(self, pages: list[MockPage], *, charge_with: ChargeWith | None = None) -> None:
        self._pages = pages
        self._by_url = {p.url: p for p in pages}
        self._charge_with = charge_with

    @classmethod
    def from_file(cls, path: str | Path, *, charge_with: ChargeWith | None = None) -> "MockProvider":
        data = json.loads(Path(path).read_text())
        return cls([MockPage(**p) for p in data["pages"]], charge_with=charge_with)

    async def search(self, query: str, *, count: int, ctx: RunContext) -> list[SearchResult]:
        async with span(ctx, "mock.search", "tool", {"query": query, "count": count}) as sp:
            started = time.monotonic()
            await self._maybe_charge(ctx, sp.id, "search", query)
            wanted = _tokens(query)
            scored = []
            for page in self._pages:
                overlap = len(wanted & _tokens(f"{page.title} {page.description} {page.markdown}"))
                if overlap:
                    scored.append((overlap, page))
            scored.sort(key=lambda pair: (-pair[0], pair[1].url))
            results = [
                SearchResult(
                    url=p.url, title=p.title, description=p.description, snippets=self._snippets(p.markdown, wanted)
                )
                for _, p in scored[:count]
            ]
            await record_tool_call(
                ctx,
                span_id=sp.id,
                provider=self.name,
                operation="search",
                request_summary=query,
                result_count=len(results),
                cache_hit=False,
                status="ok",
                latency_ms=int((time.monotonic() - started) * 1000),
                est_cost_usd=self._charge_with.price if self._charge_with else 0.0,
            )
        return results

    async def contents(self, urls: list[str], *, ctx: RunContext) -> list[PageContent]:
        async with span(ctx, "mock.contents", "tool", {"urls": urls}) as sp:
            started = time.monotonic()
            await self._maybe_charge(ctx, sp.id, "contents", " ".join(urls))
            pages = [
                PageContent(url=u, title=self._by_url[u].title, markdown=self._by_url[u].markdown)
                for u in urls
                if u in self._by_url
            ]
            await record_tool_call(
                ctx,
                span_id=sp.id,
                provider=self.name,
                operation="contents",
                request_summary=" ".join(urls),
                result_count=len(pages),
                cache_hit=False,
                status="ok",
                latency_ms=int((time.monotonic() - started) * 1000),
                est_cost_usd=self._charge_with.price if self._charge_with else 0.0,
            )
        return pages

    async def _maybe_charge(self, ctx: RunContext, span_id, operation: str, summary: str) -> None:
        if self._charge_with is None:
            return
        cw = self._charge_with
        try:
            await charge(cw.sessionmaker, ctx.workspace_id, cw.price, cap=cw.cap)
        except BudgetExceeded:
            await record_tool_call(
                ctx,
                span_id=span_id,
                provider=self.name,
                operation=operation,
                request_summary=summary,
                result_count=0,
                cache_hit=False,
                status="refused",
                latency_ms=0,
                est_cost_usd=0.0,
            )
            raise

    @staticmethod
    def _snippets(markdown: str, wanted: set[str]) -> list[str]:
        sentences = [s.strip() for s in _SENTENCE.split(markdown) if s.strip()]
        return [s for s in sentences if wanted & _tokens(s)][:2]
