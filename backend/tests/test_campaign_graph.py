import pytest

from covora.gateway.gateway import GatewayError
from covora.graphs.campaign import route_after_scoring
from covora.graphs.jobs import run_campaign_job
from tests.helpers import count_tool_calls, stage_span_names


def test_route_rules():
    s = {"campaign_id": "c", "wave": 1, "stop_reason": None}
    kw = {"target_companies": 4, "max_waves": 15}
    assert route_after_scoring(s, qualified=4, new_last_wave=3, new_prev_wave=None, **kw) == "find_people"
    assert route_after_scoring(s, qualified=1, new_last_wave=3, new_prev_wave=None, **kw) == "discover_companies"
    assert route_after_scoring({**s, "wave": 15}, qualified=1, new_last_wave=3, new_prev_wave=2, **kw) == "find_people"
    assert route_after_scoring({**s, "wave": 3}, qualified=1, new_last_wave=0, new_prev_wave=0, **kw) == "find_people"


async def test_full_pipeline_creates_prospects(graph_env):
    await run_campaign_job(graph_env.job(resume=False), graph_env.services)
    c = await graph_env.campaign()
    assert c.status == "awaiting_approval" and c.progress["stop_reason"] in {"enough_qualified", "no_new_companies"}
    assert (await graph_env.funnel())["prospects"] >= 3
    names = await stage_span_names(graph_env.sessionmaker, graph_env.campaign_id)
    assert {"discover_companies", "score_companies", "find_people", "select_contacts"} <= set(names)


async def test_retry_resumes_without_rediscovery(graph_env, sessionmaker):
    graph_env.backend.fail_next("ContactSelection", times=100)
    with pytest.raises(GatewayError):
        await run_campaign_job(graph_env.job(resume=False), graph_env.services)
    assert (await graph_env.campaign()).status == "failed"
    searches_before = await count_tool_calls(sessionmaker, operation="search")
    graph_env.backend.fail_next("ContactSelection", times=0)
    await run_campaign_job(graph_env.job(resume=True), graph_env.services)
    assert (await graph_env.campaign()).status == "awaiting_approval"
    assert await count_tool_calls(sessionmaker, operation="search") == searches_before
    assert (await graph_env.funnel())["prospects"] >= 3


async def test_budget_exhaustion_completes_with_partial_results(graph_env):
    await graph_env.set_budget(spent=79.99, cap=80.0)
    await run_campaign_job(graph_env.job(resume=False), graph_env.services)
    c = await graph_env.campaign()
    assert c.status == "complete" and c.progress["stop_reason"] == "budget"


async def test_run_and_retry_endpoints_guard_state(api, draft_campaign_id):
    assert (await api.post(f"/api/campaigns/{draft_campaign_id}/run")).json()["status"] == "queued"
    assert (await api.post(f"/api/campaigns/{draft_campaign_id}/run")).status_code == 409
    assert (await api.post(f"/api/campaigns/{draft_campaign_id}/retry")).status_code == 409
