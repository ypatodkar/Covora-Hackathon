from covora.icp.schemas import Range, StructuredICP
from covora.icp.service import save_icp_version
from covora.memory.store import MemoryQuery
from tests.fixtures_icp import EXAMPLE_ICP, EXAMPLE_ICP_WITH_INFERRED_SIZE


async def test_edit_marks_stated_and_writes_episode(icp_env, session):
    draft = StructuredICP.model_validate(EXAMPLE_ICP_WITH_INFERRED_SIZE)
    final = draft.model_copy(deep=True)
    final.employee_range.value = Range(min=10, max=50)
    v = await save_icp_version(
        session,
        workspace_id=icp_env.ws.id,
        prompt_text="p",
        structured=final,
        draft=draft,
        parent_id=None,
        created_by="user",
        memory=icp_env.memory,
        ctx=icp_env.ctx,
    )
    assert v.version == 1 and v.structured["employee_range"]["origin"] == "stated"
    mems = await icp_env.memory.retrieve(
        MemoryQuery("episodic", ["icp_edit"], "real", "employee_range", "r"), icp_env.ctx
    )
    assert "10–50" in mems[0].item.summary


async def test_no_episode_when_unchanged(icp_env, session):
    draft = StructuredICP.model_validate(EXAMPLE_ICP)
    await save_icp_version(
        session,
        workspace_id=icp_env.ws.id,
        prompt_text="p",
        structured=draft,
        draft=draft,
        parent_id=None,
        created_by="user",
        memory=icp_env.memory,
        ctx=icp_env.ctx,
    )
    assert await icp_env.memory.retrieve(MemoryQuery("episodic", ["icp_edit"], "real", "x", "r"), icp_env.ctx) == []


async def test_versions_increment(icp_env, session):
    a = await save_icp_version(session, **icp_env.save_kwargs())
    b = await save_icp_version(session, **icp_env.save_kwargs(parent_id=a.id))
    assert (a.version, b.version, b.parent_id) == (1, 2, a.id)


async def test_save_survives_memory_failure(icp_env, session):
    icp_env.backend.fail_embeddings = True
    draft = StructuredICP.model_validate(EXAMPLE_ICP_WITH_INFERRED_SIZE)
    final = draft.model_copy(deep=True)
    final.employee_range.value = Range(min=10, max=50)
    v = await save_icp_version(session, **icp_env.save_kwargs(structured=final, draft=draft))
    assert v.version == 1 and v.structured["employee_range"]["origin"] == "stated"
