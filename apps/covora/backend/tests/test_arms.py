from uuid import uuid4

from covora.outreach.arms import arm_for


async def test_campaign_gets_two_arms_by_default(api, saved_icp):
    c = (await api.post("/api/campaigns", json={"icp_version_id": saved_icp, "name": "x", "goals": {}})).json()
    assert [a["key"] for a in c["arms"]] == ["A", "B"]
    assert c["arms"][0]["template_id"] != c["arms"][1]["template_id"]


def test_arm_assignment_is_stable_and_balanced():
    ids = [uuid4() for _ in range(1000)]
    first = [arm_for(i, ["A", "B"]) for i in ids]
    assert first == [arm_for(i, ["A", "B"]) for i in ids]
    assert 400 <= first.count("A") <= 600


async def test_create_with_unknown_template_404(api, saved_icp):
    body = {"icp_version_id": saved_icp, "name": "x", "goals": {}, "template_ids": [str(uuid4()), str(uuid4())]}
    assert (await api.post("/api/campaigns", json=body)).status_code == 404
