import pytest

from covora.memory.store import MemoryQuery, NewMemory


async def test_retrieve_ranks_by_similarity(memory, ctx):
    await memory.write(
        NewMemory("episodic", "outreach_episode", "gmail_sim", "operations manager short email interested", {}, []), ctx
    )
    await memory.write(
        NewMemory("episodic", "outreach_episode", "gmail_sim", "finance director long email ignored", {}, []), ctx
    )
    got = await memory.retrieve(
        MemoryQuery("episodic", ["outreach_episode"], "real", "operations manager", "similar episodes"), ctx
    )
    assert got[0].item.summary.startswith("operations manager") and got[0].rank == 1


async def test_scope_isolation(memory, ctx):
    await memory.write(NewMemory("episodic", "outreach_episode", "mock_sim", "ops manager mock", {}, []), ctx)
    got = await memory.retrieve(MemoryQuery("episodic", ["outreach_episode"], "real", "ops manager", "r"), ctx)
    assert got == []


async def test_superseded_excluded(memory, ctx):
    old = await memory.write(
        NewMemory("semantic", "insight", "mock_sim", "short emails win", {"dimension": "style"}, [], "signal"), ctx
    )
    new = await memory.write(
        NewMemory(
            "semantic", "insight", "mock_sim", "short emails win strongly", {"dimension": "style"}, [], "evidence"
        ),
        ctx,
    )
    await memory.supersede(old, new, ctx)
    got = await memory.retrieve(MemoryQuery("semantic", ["insight"], "mock", "short emails", "r"), ctx)
    assert [g.item.id for g in got] == [new]


async def test_assumption_insight_rejected(memory, ctx):
    with pytest.raises(ValueError):
        await memory.write(NewMemory("semantic", "insight", "research", "maybe X", {}, [], "assumption"), ctx)


async def test_outcome_is_append_only(memory, ctx):
    mid = await memory.write(NewMemory("episodic", "selection_episode", "research", "picked COO", {}, []), ctx)
    await memory.attach_outcome(mid, {"label": "interested"}, ctx)
    with pytest.raises(ValueError):
        await memory.attach_outcome(mid, {"label": "not_interested"}, ctx)


async def test_payload_filters(memory, ctx):
    await memory.write(
        NewMemory("semantic", "insight", "research", "segment A good", {"dimension": "segment"}, [], "signal"), ctx
    )
    await memory.write(
        NewMemory("semantic", "insight", "research", "style B good", {"dimension": "style"}, [], "signal"), ctx
    )
    got = await memory.retrieve(
        MemoryQuery("semantic", ["insight"], "real", "good", "r", filters={"dimension": "segment"}), ctx
    )
    assert [g.item.summary for g in got] == ["segment A good"]
