from uuid import uuid4

GOALS = {"goal_type": "positive_replies", "target": 10, "expected_positive_rate": 0.01, "meetings_per_positive": 0.5}


async def test_estimate_and_create(api, saved_icp):
    est = (await api.post("/api/campaigns/estimate", json={**GOALS, "prospect_limit": 20})).json()
    assert est["prospects_planned"] == 20 and est["prospects_needed"] == 1000
    c = (
        await api.post(
            "/api/campaigns",
            json={"icp_version_id": saved_icp, "name": "Ohio fab", "goals": GOALS, "prospect_limit": 20},
        )
    ).json()
    assert c["status"] == "draft" and c["target_prospects"] == 20 and c["funnel"]["prospects"] == 0
    assert (await api.get("/api/campaigns")).json()[0]["id"] == c["id"]
    assert (await api.get(f"/api/campaigns/{c['id']}")).json()["name"] == "Ohio fab"


async def test_create_with_unknown_icp_404(api):
    r = await api.post("/api/campaigns", json={"icp_version_id": str(uuid4()), "name": "x", "goals": {}})
    assert r.status_code == 404
