from sqlalchemy import func, select, text

from covora.workspace.models import Workspace
from covora.workspace.service import WorkspaceProfile, ensure_workspace, update_profile


async def test_ensure_workspace_is_idempotent(session):
    a = await ensure_workspace(session)
    b = await ensure_workspace(session)
    assert a.id == b.id
    assert (await session.execute(select(func.count()).select_from(Workspace))).scalar() == 1


async def test_update_profile(session):
    ws = await ensure_workspace(session)
    ws = await update_profile(
        session,
        ws,
        WorkspaceProfile(
            name="Acme Robotics",
            website="https://acme.example",
            description="Cobots for small factories",
            value_props=["Pays back in 9 months"],
            offering_type="sales_call",
        ),
    )
    assert ws.name == "Acme Robotics" and ws.value_props == ["Pays back in 9 months"]


async def test_vector_extension_installed(session):
    row = (await session.execute(text("select extname from pg_extension where extname='vector'"))).scalar()
    assert row == "vector"
