import json

from covora.icp.agent import parse_icp
from covora.memory.store import NewMemory
from tests.fakes import SUPER
from tests.fixtures_icp import EXAMPLE_ICP


async def test_parse_icp_uses_profile_and_returns_structured(icp_env):
    icp_env.backend.queue(SUPER, json.dumps(EXAMPLE_ICP))
    r = await parse_icp("Find US manufacturers with 5–25 employees", **icp_env.kwargs())
    assert r.output.employee_range.value.max == 25 and r.output.employee_range.origin == "stated"
    system = icp_env.backend.calls[0]["messages"][0]["content"]
    assert "Acme Robotics" in system and "(no relevant memories)" in system


async def test_parse_icp_sees_past_corrections(icp_env):
    await icp_env.memory.write(
        NewMemory("episodic", "icp_edit", "research", "User changed employee_range 5–25 → 10–50", {}, []), icp_env.ctx
    )
    icp_env.backend.queue(SUPER, json.dumps(EXAMPLE_ICP))
    r = await parse_icp("Find US manufacturers", **icp_env.kwargs())
    assert "10–50" in icp_env.backend.calls[0]["messages"][0]["content"]
    assert r.working_memory.manifest()[0]["subtype"] == "icp_edit"
