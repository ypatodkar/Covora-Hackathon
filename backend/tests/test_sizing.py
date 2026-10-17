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
