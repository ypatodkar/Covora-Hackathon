import pytest

from covora.research.budget import charge, refund, spend
from covora.research.cache import cache_key, get_cached, put_cached
from covora.research.provider import BudgetExceeded
from tests.helpers import latest_tool_call


async def test_charge_is_atomic_and_capped(sessionmaker, workspace):
    assert await charge(sessionmaker, workspace.id, 0.5, cap=1.0) == pytest.approx(0.5)
    with pytest.raises(BudgetExceeded):
        await charge(sessionmaker, workspace.id, 0.6, cap=1.0)
    await refund(sessionmaker, workspace.id, 0.5)
    assert await spend(sessionmaker, workspace.id) == pytest.approx(0.0)


async def test_cache_roundtrip_and_ttl(sessionmaker):
    key = cache_key("search", {"query": "a", "count": 5})
    await put_cached(sessionmaker, key, "search", {"query": "a"}, {"ok": 1})
    assert await get_cached(sessionmaker, key, ttl_days=14) == {"ok": 1}
    assert await get_cached(sessionmaker, key, ttl_days=0) is None


async def test_mock_search_ranks_and_traces(mock_research, ctx, sessionmaker):
    results = await mock_research.search("metal fabrication Ohio", count=3, ctx=ctx)
    assert results[0].url.startswith("https://ohio-precision.test")
    assert (await latest_tool_call(sessionmaker)).provider == "mock"


async def test_mock_contents_skips_unknown(mock_research, ctx):
    pages = await mock_research.contents(["https://ohio-precision.test/team", "https://nope.test/"], ctx=ctx)
    assert [p.url for p in pages] == ["https://ohio-precision.test/team"]
