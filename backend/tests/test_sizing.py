from covora.campaigns.sizing import CostModel, estimate_campaign
from covora.workspace.settings import Goals


def _est(**goal):
    return estimate_campaign(
        Goals(**goal),
        prospect_limit=None,
        cost=CostModel(),
        search_price=0.005,
        page_price=0.001,
        budget_remaining=80.0,
        daily_gmail_cap=100,
    )


def test_owner_example_ten_replies_at_one_percent():
    e = _est(goal_type="positive_replies", target=10, expected_positive_rate=0.01)
    assert (e.prospects_needed, e.est_searches, e.est_pages, e.est_youcom_usd) == (1000, 8000, 4000, 44.0)
    assert (e.gmail_emails, e.in_app_emails, e.fits_budget, e.max_affordable_prospects) == (100, 900, True, 1818)


def test_meetings_goal_uses_meeting_rate():
    e = _est(goal_type="meetings", target=10, expected_positive_rate=0.01, meetings_per_positive=0.5)
    assert e.prospects_needed == 2000


def test_prospect_limit_caps_plan():
    e = estimate_campaign(
        Goals(),
        prospect_limit=20,
        cost=CostModel(),
        search_price=0.005,
        page_price=0.001,
        budget_remaining=80.0,
        daily_gmail_cap=100,
    )
    assert (e.prospects_planned, e.est_youcom_usd) == (20, 0.88)


def test_over_budget_flagged():
    e = estimate_campaign(
        Goals(target=50),
        prospect_limit=None,
        cost=CostModel(),
        search_price=0.005,
        page_price=0.001,
        budget_remaining=80.0,
        daily_gmail_cap=100,
    )
    assert e.fits_budget is False


async def test_measured_cost_model(session, workspace, sessionmaker):
    from covora.campaigns.models import Campaign
    from covora.campaigns.sizing import measured_cost_model
    from covora.discovery.models import Company
    from covora.icp.models import IcpVersion
    from covora.observability.tracing import span, start_run
    from covora.qualification.models import Contact, Prospect
    from covora.research.tooltrace import record_tool_call
    from tests.fixtures_icp import EXAMPLE_ICP

    assert await measured_cost_model(session, workspace.id) is None
    icp = IcpVersion(workspace_id=workspace.id, version=1, prompt_text="p", structured=EXAMPLE_ICP, created_by="user")
    session.add(icp)
    await session.flush()
    campaign = Campaign(
        workspace_id=workspace.id,
        name="c",
        icp_version_id=icp.id,
        config_snapshot={},
        goal={},
        target_prospects=3,
        status="complete",
    )
    session.add(campaign)
    await session.flush()
    for i in range(3):
        company = Company(workspace_id=workspace.id, name=f"Co {i}", domain=f"co{i}.test")
        session.add(company)
        await session.flush()
        contact = Contact(
            company_id=company.id,
            full_name=f"P {i}",
            name_key=f"p {i}",
            title="COO",
            function="operations",
            seniority="c_level",
            email_status="missing",
        )
        session.add(contact)
        await session.flush()
        session.add(
            Prospect(
                campaign_id=campaign.id,
                company_id=company.id,
                contact_id=contact.id,
                short_id=f"0000000{i}",
                role="primary",
                pick_reason="r",
                confidence="high",
            )
        )
    await session.commit()
    ctx = await start_run(sessionmaker, kind="campaign", workspace_id=workspace.id, secrets=[], campaign_id=campaign.id)
    async with span(ctx, "s", "tool") as sp:
        for _ in range(24):
            await record_tool_call(
                ctx,
                span_id=sp.id,
                provider="youcom",
                operation="search",
                request_summary="q",
                result_count=5,
                cache_hit=False,
                status="ok",
                latency_ms=1,
                est_cost_usd=0.005,
            )
        await record_tool_call(
            ctx,
            span_id=sp.id,
            provider="youcom",
            operation="contents",
            request_summary="u",
            result_count=12,
            cache_hit=False,
            status="ok",
            latency_ms=1,
            est_cost_usd=0.012,
        )
    model = await measured_cost_model(session, workspace.id)
    assert (model.searches_per_prospect, model.pages_per_prospect, model.source) == (8.0, 4.0, "measured")
