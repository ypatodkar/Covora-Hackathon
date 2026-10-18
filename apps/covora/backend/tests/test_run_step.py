from covora.agents.step import run_step
from covora.gateway.tasks import TaskType
from covora.memory.store import MemoryQuery, NewMemory
from tests.fakes import SUPER, Answer
from tests.helpers import count_memory_reads


async def test_cycle_order_and_manifest(step_env):
    await step_env.memory.write(
        NewMemory("episodic", "icp_edit", "research", "user widened size to 10-50", {}, []), step_env.ctx
    )
    step_env.backend.queue(SUPER, '{"value": 1}')
    seen = {}

    def build(wm):
        seen["mem"] = wm.render_memories()
        return [{"role": "user", "content": "go"}]

    r = await run_step(
        **step_env.kwargs(
            agent="icp",
            task=TaskType.icp_parsing,
            queries=[MemoryQuery("episodic", ["icp_edit"], "real", "size", "past ICP corrections")],
            build_messages=build,
            schema=Answer,
        )
    )
    assert "user widened size" in seen["mem"]
    assert r.working_memory.manifest()[0]["reason"] == "past ICP corrections"
    assert await count_memory_reads(step_env.sessionmaker, r.span_id) == 1


async def test_run_step_with_no_memories(step_env):
    step_env.backend.queue(SUPER, '{"value": 1}')
    r = await run_step(
        **step_env.kwargs(
            agent="icp",
            task=TaskType.icp_parsing,
            queries=[MemoryQuery("semantic", ["insight"], "real", "x", "insights")],
            build_messages=lambda wm: [{"role": "user", "content": wm.render_memories()}],
            schema=Answer,
        )
    )
    assert r.output.value == 1 and r.working_memory.memories == []
    assert "(no relevant memories)" in step_env.backend.calls[0]["messages"][0]["content"]


async def test_memory_disabled_skips_retrieval(step_env, monkeypatch):
    monkeypatch.setenv("MEMORY_ENABLED_ICP", "false")
    await step_env.memory.write(NewMemory("episodic", "icp_edit", "research", "something", {}, []), step_env.ctx)
    step_env.backend.queue(SUPER, '{"value": 1}')
    r = await run_step(
        **step_env.kwargs(
            agent="icp",
            task=TaskType.icp_parsing,
            queries=[MemoryQuery("episodic", ["icp_edit"], "real", "something", "r")],
            build_messages=lambda wm: [{"role": "user", "content": "go"}],
            schema=Answer,
        )
    )
    assert r.working_memory.memories == []


async def test_budget_trims_lowest_scores(step_env):
    for i in range(10):
        await step_env.memory.write(
            NewMemory("episodic", "icp_edit", "research", f"edit number {i} " + "x" * 400, {}, []), step_env.ctx
        )
    step_env.backend.queue(SUPER, '{"value": 1}')
    r = await run_step(
        **step_env.kwargs(
            agent="icp",
            task=TaskType.icp_parsing,
            queries=[MemoryQuery("episodic", ["icp_edit"], "real", "edit", "r", k=10)],
            build_messages=lambda wm: [{"role": "user", "content": "go"}],
            schema=Answer,
            budgets={"episodic": 250, "semantic": 0},
        )
    )
    assert len(r.working_memory.memories) == 2


async def test_episode_written(step_env):
    step_env.backend.queue(SUPER, '{"value": 7}')
    r = await run_step(
        **step_env.kwargs(
            agent="icp",
            task=TaskType.icp_parsing,
            queries=[],
            build_messages=lambda wm: [{"role": "user", "content": "go"}],
            schema=Answer,
            episode=lambda out, wm: NewMemory(
                "episodic", "selection_episode", "research", f"chose {out.value}", {}, []
            ),
        )
    )
    assert r.episode_id is not None


async def test_memory_failure_degrades_to_no_memories(step_env):
    step_env.backend.fail_embeddings = True
    step_env.backend.queue(SUPER, '{"value": 3}')
    r = await run_step(
        **step_env.kwargs(
            agent="icp",
            task=TaskType.icp_parsing,
            queries=[MemoryQuery("episodic", ["icp_edit"], "real", "anything", "r")],
            build_messages=lambda wm: [{"role": "user", "content": wm.render_memories()}],
            schema=Answer,
            episode=lambda out, wm: NewMemory("episodic", "selection_episode", "research", "x", {}, []),
        )
    )
    assert r.output.value == 3 and r.working_memory.memories == [] and r.episode_id is None
