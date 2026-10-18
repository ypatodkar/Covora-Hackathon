import pytest

from covora.memory.prompts import get_prompt, render_prompt, sync_prompts


async def test_sync_creates_new_version_on_change(session, tmp_prompts_dir):
    (tmp_prompts_dir / "x.md").write_text("v1 $a")
    await sync_prompts(session)
    (tmp_prompts_dir / "x.md").write_text("v2 $a")
    await sync_prompts(session)
    p = await get_prompt(session, "x")
    assert (p.version, p.body) == (2, "v2 $a")


def test_render_prompt_missing_value_raises():
    with pytest.raises(KeyError):
        render_prompt("hello $name")
