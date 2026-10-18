from covora.workspace.settings import WorkspaceSettings


def test_defaults_match_owner_example():
    s = WorkspaceSettings()
    assert (s.goals.goal_type, s.goals.target, s.goals.expected_positive_rate) == ("positive_replies", 10, 0.01)


async def test_settings_roundtrip(api):
    body = {
        "goals": {"goal_type": "meetings", "target": 5, "expected_positive_rate": 0.02, "meetings_per_positive": 0.5},
        "sending": {"daily_gmail_cap": 50, "first_batch_size": 10, "no_reply_window_minutes": 10},
    }
    assert (await api.put("/api/workspace/settings", json=body)).status_code == 200
    assert (await api.get("/api/workspace/settings")).json()["goals"]["goal_type"] == "meetings"


async def test_invalid_rate_rejected(api):
    r = await api.put("/api/workspace/settings", json={"goals": {"expected_positive_rate": 0}})
    assert r.status_code == 422
