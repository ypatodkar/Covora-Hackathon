from covora.memory.store import MemoryQuery
from covora.qualification.select import select_contacts
from tests.helpers import campaign_companies_by_domain, prospects_by_domain


async def test_primary_and_backup_created(select_env):
    n = await select_contacts(
        select_env.campaign_id, select_env.qualified_ids, ctx=select_env.ctx, services=select_env.services
    )
    prospects = await prospects_by_domain(select_env.sessionmaker, select_env.campaign_id)
    assert {p.role for p in prospects["ohio-precision.test"]} == {"primary", "backup"}
    assert n >= 3


async def test_company_without_people_marked_no_contact(select_env):
    await select_contacts(
        select_env.campaign_id, select_env.qualified_ids, ctx=select_env.ctx, services=select_env.services
    )
    rows = await campaign_companies_by_domain(select_env.sessionmaker, select_env.campaign_id)
    assert rows["midwest-valve.test"].status == "no_contact"


async def test_invented_pick_retried_then_needs_review(select_env):
    select_env.backend.override(
        "ContactSelection",
        lambda inp: {
            "primary": {"contact_id": "nope", "reason": "r", "confidence": "low"},
            "backup": None,
            "no_suitable_contact": False,
        },
    )
    ohio = select_env.company_id("ohio-precision.test")
    await select_contacts(select_env.campaign_id, [ohio], ctx=select_env.ctx, services=select_env.services)
    rows = await campaign_companies_by_domain(select_env.sessionmaker, select_env.campaign_id)
    assert rows["ohio-precision.test"].status == "needs_review"
    assert len(select_env.backend.inputs_for("ContactSelection")) == 2


async def test_selection_episode_written(select_env):
    await select_contacts(
        select_env.campaign_id, select_env.qualified_ids, ctx=select_env.ctx, services=select_env.services
    )
    episodes = await select_env.services.memory.retrieve(
        MemoryQuery("episodic", ["selection_episode"], "mock", "Operations Manager", "r", k=10), select_env.ctx
    )
    assert any("Operations Manager" in e.item.summary for e in episodes)


async def test_funnel_counts(select_env, session):
    from covora.campaigns.service import campaign_funnel

    await select_contacts(
        select_env.campaign_id, select_env.qualified_ids, ctx=select_env.ctx, services=select_env.services
    )
    funnel = await campaign_funnel(session, select_env.campaign_id)
    assert funnel["rejected"] == 2 and funnel["no_contact"] == 1 and funnel["prospects"] >= 3
    assert funnel["candidates"] >= funnel["qualified"] >= funnel["with_contacts"]
