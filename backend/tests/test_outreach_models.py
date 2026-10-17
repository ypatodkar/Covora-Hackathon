from covora.outreach.suppression import is_suppressed, normalize_email, suppress
from covora.outreach.templates import pick_default_templates, sync_templates
from covora.workspace.settings import WorkspaceSettings


async def test_templates_seeded_once(session, workspace):
    await sync_templates(session, workspace.id)
    await sync_templates(session, workspace.id)
    from sqlalchemy import func, select

    from covora.outreach.models import Template

    assert (await session.execute(select(func.count()).select_from(Template))).scalar_one() == 12


async def test_default_templates_differ_in_length(session, workspace):
    await sync_templates(session, workspace.id)
    a, b = await pick_default_templates(session, workspace.id, "sales_call")
    assert a.length != b.length


async def test_suppress_is_idempotent_and_normalized(session, workspace):
    assert normalize_email("  Dana@X.test ") == "dana@x.test"
    await suppress(session, workspace.id, "  Dana@X.test ", "unsubscribe")
    await suppress(session, workspace.id, "dana@x.test", "unsubscribe")
    assert await is_suppressed(session, workspace.id, "DANA@x.test")
    assert not await is_suppressed(session, workspace.id, None)


async def test_sales_rep_crud(api):
    rep = (
        await api.post(
            "/api/sales-reps", json={"name": "Sam", "email": "sam@acme.test", "booking_url": "https://cal.test/sam"}
        )
    ).json()
    assert (await api.get("/api/sales-reps")).json()[0]["name"] == "Sam"
    updated = (await api.put(f"/api/sales-reps/{rep['id']}", json={**rep, "active": False})).json()
    assert updated["active"] is False
    assert (await api.delete(f"/api/sales-reps/{rep['id']}")).status_code == 204


async def test_templates_api_lists_seeded(api):
    templates = (await api.get("/api/templates")).json()
    assert len(templates) == 12 and {"angle", "length", "cta", "subject_template"} <= set(templates[0])


def test_settings_defaults_include_simulation():
    s = WorkspaceSettings()
    assert s.simulation.profile == "realistic" and s.sending.test_inbox_address is None
