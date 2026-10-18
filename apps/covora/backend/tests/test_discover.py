from covora.discovery.discover import discover_wave
from tests.fixtures_icp import EXAMPLE_ICP
from tests.helpers import candidate_domains


async def test_wave_one_uses_icp_queries_and_creates_candidates(discovery_env):
    r = await discover_wave(discovery_env.campaign_id, wave=1, ctx=discovery_env.ctx, services=discovery_env.services)
    assert r.queries == EXAMPLE_ICP["search_queries"]
    domains = await candidate_domains(discovery_env.sessionmaker, discovery_env.campaign_id)
    assert "ohio-precision.test" in domains and "thomasnet.com" not in domains


async def test_unlisted_company_dropped(discovery_env):
    await discover_wave(discovery_env.campaign_id, wave=1, ctx=discovery_env.ctx, services=discovery_env.services)
    assert "ghost.test" not in await candidate_domains(discovery_env.sessionmaker, discovery_env.campaign_id)


async def test_wave_two_generates_new_queries(discovery_env):
    await discover_wave(discovery_env.campaign_id, wave=1, ctx=discovery_env.ctx, services=discovery_env.services)
    r = await discover_wave(discovery_env.campaign_id, wave=2, ctx=discovery_env.ctx, services=discovery_env.services)
    assert r.queries and not set(r.queries) & set(EXAMPLE_ICP["search_queries"])
    sent = discovery_env.backend.inputs_for("QueryPlan")[0]
    assert set(sent["used_queries"]) >= set(EXAMPLE_ICP["search_queries"])


async def test_rerun_does_not_duplicate_candidates(discovery_env):
    for wave in (1, 2):
        await discover_wave(
            discovery_env.campaign_id, wave=wave, ctx=discovery_env.ctx, services=discovery_env.services
        )
    domains = await candidate_domains(discovery_env.sessionmaker, discovery_env.campaign_id)
    assert len(domains) == len(set(domains))


async def test_wave_respects_candidate_limit(discovery_env):
    r = await discover_wave(
        discovery_env.campaign_id, wave=1, ctx=discovery_env.ctx, services=discovery_env.services, limit=2
    )
    assert len(r.new_company_ids) == 2
    assert len(await candidate_domains(discovery_env.sessionmaker, discovery_env.campaign_id)) == 2


def test_wave_limit_scales_with_what_is_still_needed():
    from covora.graphs.campaign import wave_candidate_limit

    assert wave_candidate_limit(target_companies=4, qualified=0, cap=40) == 8
    assert wave_candidate_limit(target_companies=4, qualified=3, cap=40) == 5
    assert wave_candidate_limit(target_companies=1000, qualified=0, cap=40) == 40
