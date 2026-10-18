import json

import httpx
import pytest

from covora.research.budget import spend
from covora.research.provider import BudgetExceeded, ResearchError
from covora.research.youcom import YouComProvider
from tests.helpers import latest_tool_call

SEARCH_OK = {
    "results": {
        "web": [
            {
                "url": "https://ohio-precision.test/",
                "title": "Ohio Precision Fabrication",
                "description": "Metal fabrication in Dayton, Ohio.",
                "snippets": ["Our team of 18 employees runs two shifts."],
                "page_age": "2026-09-01T00:00:00",
            },
            {"url": "https://lakeside-plastics.test/", "title": "Lakeside Plastics", "description": "Plastics."},
        ]
    },
    "metadata": {"query": "metal fab", "search_uuid": "u1", "latency": 0.2},
}


@pytest.fixture
def youcom_with(settings, sessionmaker):
    def build(handler, budget_usd=None):
        calls: list[httpx.Request] = []

        def recording(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return handler(request)

        s = settings if budget_usd is None else settings.model_copy(update={"youcom_budget_usd": budget_usd})
        client = httpx.AsyncClient(transport=httpx.MockTransport(recording))
        return YouComProvider(s, sessionmaker, http_client=client), calls

    return build


async def test_search_parses_and_caches(youcom_with, ctx, sessionmaker):
    provider, calls = youcom_with(lambda req: httpx.Response(200, json=SEARCH_OK))
    first = await provider.search("metal fab", count=5, ctx=ctx)
    second = await provider.search("metal fab", count=5, ctx=ctx)
    assert first[0].url == "https://ohio-precision.test/" and second == first and len(calls) == 1
    assert first[1].snippets == []
    assert (await latest_tool_call(sessionmaker)).cache_hit is True
    assert calls[0].headers["X-API-Key"] == "ydc-test-key-000000"


async def test_retry_then_refund_on_failure(youcom_with, ctx, sessionmaker, workspace):
    provider, calls = youcom_with(lambda req: httpx.Response(503))
    with pytest.raises(ResearchError):
        await provider.search("x", count=5, ctx=ctx)
    assert len(calls) == 4 and await spend(sessionmaker, workspace.id) == 0


async def test_budget_refused_before_call(youcom_with, ctx):
    provider, calls = youcom_with(lambda req: httpx.Response(200, json=SEARCH_OK), budget_usd=0.001)
    with pytest.raises(BudgetExceeded):
        await provider.search("x", count=5, ctx=ctx)
    assert calls == []


async def test_contents_fetches_only_uncached(youcom_with, ctx):
    def handler(req):
        urls = json.loads(req.content)["urls"]
        return httpx.Response(200, json=[{"url": u, "title": "t", "markdown": "m"} for u in urls])

    provider, calls = youcom_with(handler)
    await provider.contents(["https://a.test/"], ctx=ctx)
    pages = await provider.contents(["https://a.test/", "https://b.test/"], ctx=ctx)
    assert json.loads(calls[1].content)["urls"] == ["https://b.test/"]
    assert [p.url for p in pages] == ["https://a.test/", "https://b.test/"]


async def test_missing_key_raises_without_call(settings, sessionmaker, ctx):
    provider = YouComProvider(settings.model_copy(update={"ydc_api_key": None}), sessionmaker)
    with pytest.raises(ResearchError, match="YDC_API_KEY"):
        await provider.search("x", count=5, ctx=ctx)
