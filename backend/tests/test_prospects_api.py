from covora.exports import csv_safe

PASSED_FIT = {"contact_selected", "qualified", "no_contact"}


async def test_companies_and_prospects_lists(api, completed_campaign):
    companies = (await api.get(f"/api/campaigns/{completed_campaign}/companies")).json()
    assert companies[0]["status"] in PASSED_FIT
    scores = [c["fit_score"] for c in companies if c["status"] in PASSED_FIT]
    assert scores == sorted(scores, reverse=True)
    assert all(c["synthetic"] for c in companies)
    prospects = (await api.get(f"/api/campaigns/{completed_campaign}/prospects")).json()
    assert {p["role"] for p in prospects} >= {"primary"} and all(p["contact"]["full_name"] for p in prospects)


async def test_company_detail_has_labeled_facts(api, completed_campaign):
    companies = (await api.get(f"/api/campaigns/{completed_campaign}/companies")).json()
    cid = next(c["company_id"] for c in companies if c["domain"] == "ohio-precision.test")
    detail = (await api.get(f"/api/companies/{cid}")).json()
    assert any(f["field"] == "employee_count" and f["label"] == "verified" and f["source_url"] for f in detail["facts"])
    assert {c["full_name"] for c in detail["contacts"]} >= {"Dana Ruiz"}


def test_csv_cells_are_formula_escaped():
    assert csv_safe('=HYPERLINK("x")') == '\'=HYPERLINK("x")'
    assert csv_safe("+1 555") == "'+1 555" and csv_safe("@me") == "'@me" and csv_safe("Acme") == "Acme"
    assert csv_safe(None) == "" and csv_safe(42) == "42"


async def test_prospects_csv_export(api, completed_campaign):
    r = await api.get(f"/api/exports/prospects.csv?campaign_id={completed_campaign}")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert r.text.splitlines()[0].startswith("company,domain,contact,title,role")
    assert "attachment" in r.headers["content-disposition"]


async def test_unknown_company_404(api):
    from uuid import uuid4

    r = await api.get(f"/api/companies/{uuid4()}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
