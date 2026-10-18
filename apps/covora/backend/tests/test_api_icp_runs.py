import json
from uuid import uuid4

from covora.gateway.backend import BackendError
from tests.fakes import NANO, SUPER
from tests.fixtures_icp import EXAMPLE_ICP


async def test_parse_then_save_then_list(api, fake_backend):
    fake_backend.queue(SUPER, json.dumps(EXAMPLE_ICP))
    parsed = (await api.post("/api/icp/parse", json={"prompt_text": "US manufacturers 5–25 employees"})).json()
    saved = (
        await api.post(
            "/api/icps",
            json={
                "prompt_text": "US manufacturers 5–25 employees",
                "structured": parsed["draft"],
                "draft": parsed["draft"],
                "parent_id": None,
            },
        )
    ).json()
    assert saved["version"] == 1
    assert (await api.get("/api/icps")).json()[0]["id"] == saved["id"]


async def test_parse_returns_502_when_models_unavailable(api, fake_backend):
    for m in (SUPER, NANO):
        fake_backend.queue(m, *[BackendError("503", status=503, retryable=True)] * 4)
    r = await api.post("/api/icp/parse", json={"prompt_text": "anything"})
    assert r.status_code == 502 and r.json()["error"]["code"] == "model_unavailable"
    runs = (await api.get("/api/runs?kind=icp")).json()
    assert runs[0]["status"] == "failed"


async def test_run_detail_has_spans_llm_calls_and_memory(api, fake_backend):
    fake_backend.queue(SUPER, json.dumps(EXAMPLE_ICP))
    run_id = (await api.post("/api/icp/parse", json={"prompt_text": "x"})).json()["run_id"]
    d = (await api.get(f"/api/runs/{run_id}")).json()
    assert {s["kind"] for s in d["spans"]} >= {"agent", "llm"}
    call = next(c for c in d["llm_calls"] if c["task"] == "icp_parsing")
    assert call["routing_reason"] == "fixed: icp_parsing → super" and "request_payload" not in call
    agent_span = next(s for s in d["spans"] if s["kind"] == "agent")
    assert (await api.get(f"/api/runs/{run_id}/spans/{agent_span['id']}/memory")).status_code == 200


async def test_unknown_icp_404(api):
    r = await api.get(f"/api/icps/{uuid4()}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
