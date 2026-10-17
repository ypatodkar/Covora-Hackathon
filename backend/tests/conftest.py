import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from covora.config import Settings
from covora.db.session import make_engine, make_sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://covora:covora@localhost:5434/covora_test"
)


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url=TEST_DATABASE_URL,
        nvidia_api_key="nvapi-test-key-000000",
        ydc_api_key="ydc-test-key-000000",
        retry_base_delay_s=0,
    )


@pytest.fixture(scope="session")
def migrated(settings):
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
async def engine(settings, migrated):
    eng = make_engine(settings.database_url)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="session")
def sessionmaker(engine):
    return make_sessionmaker(engine)


@pytest.fixture(autouse=True)
async def clean_db(request):
    """After each test that touched the database, empty every table (pure tests need no database)."""
    yield
    if "sessionmaker" not in request.fixturenames:
        return
    sessionmaker = request.getfixturevalue("sessionmaker")
    async with sessionmaker() as s:
        tables = (
            await s.execute(
                text(
                    "select tablename from pg_tables "
                    "where schemaname = 'public' and tablename <> 'alembic_version'"
                )
            )
        ).scalars().all()
        if tables:
            joined = ", ".join(f'"{t}"' for t in tables)
            await s.execute(text(f"TRUNCATE {joined} RESTART IDENTITY CASCADE"))
            await s.commit()


@pytest.fixture
async def session(sessionmaker):
    async with sessionmaker() as s:
        yield s


@pytest.fixture
async def workspace(session):
    from covora.workspace.service import ensure_workspace

    return await ensure_workspace(session)


@pytest.fixture
def fake_backend(settings):
    from tests.fakes import FakeChatBackend

    return FakeChatBackend(dim=settings.nemotron_embed_dim)


@pytest.fixture
def gateway(fake_backend, settings):
    from covora.gateway.gateway import ModelGateway

    return ModelGateway(fake_backend, settings)


@pytest.fixture
def memory(sessionmaker, gateway):
    from covora.memory.store import MemoryStore

    return MemoryStore(sessionmaker, gateway)


@pytest.fixture
def tmp_prompts_dir(tmp_path, monkeypatch):
    import covora.memory.prompts

    monkeypatch.setattr(covora.memory.prompts, "PROMPTS_DIR", tmp_path)
    return tmp_path


@pytest.fixture
async def ctx(sessionmaker, workspace, settings):
    from covora.observability.tracing import start_run

    return await start_run(sessionmaker, kind="icp", workspace_id=workspace.id, secrets=settings.secret_values())


class StepEnv:
    def __init__(self, *, backend, gateway, memory, ctx, sessionmaker, settings):
        self.backend = backend
        self.gateway = gateway
        self.memory = memory
        self.ctx = ctx
        self.sessionmaker = sessionmaker
        self.settings = settings

    def kwargs(self, **overrides):
        base = {
            "ctx": self.ctx,
            "gateway": self.gateway,
            "memory": self.memory,
            "settings": self.settings,
            "goal": "test",
            "inputs": {},
        }
        return base | overrides


@pytest.fixture
def step_env(fake_backend, gateway, memory, ctx, sessionmaker, settings):
    return StepEnv(
        backend=fake_backend, gateway=gateway, memory=memory, ctx=ctx, sessionmaker=sessionmaker, settings=settings
    )


class IcpEnv:
    def __init__(self, *, ws, backend, gateway, memory, ctx, settings, session):
        self.ws = ws
        self.backend = backend
        self.gateway = gateway
        self.memory = memory
        self.ctx = ctx
        self.settings = settings
        self.session = session

    def kwargs(self):
        return {
            "ctx": self.ctx,
            "gateway": self.gateway,
            "memory": self.memory,
            "settings": self.settings,
            "session": self.session,
        }

    def save_kwargs(self, **overrides):
        from covora.icp.schemas import StructuredICP
        from tests.fixtures_icp import EXAMPLE_ICP

        base = {
            "workspace_id": self.ws.id,
            "prompt_text": "p",
            "structured": StructuredICP.model_validate(EXAMPLE_ICP),
            "draft": None,
            "parent_id": None,
            "created_by": "user",
            "memory": self.memory,
            "ctx": self.ctx,
        }
        return base | overrides


@pytest.fixture
async def icp_env(session, workspace, fake_backend, gateway, memory, ctx, settings):
    from covora.memory.prompts import sync_prompts
    from covora.workspace.service import WorkspaceProfile, update_profile

    ws = await update_profile(
        session,
        workspace,
        WorkspaceProfile(
            name="Acme Robotics",
            description="Cobots for small factories",
            value_props=["Pays back in 9 months"],
            offering_type="sales_call",
        ),
    )
    await sync_prompts(session)
    return IcpEnv(
        ws=ws, backend=fake_backend, gateway=gateway, memory=memory, ctx=ctx, settings=settings, session=session
    )


@pytest.fixture
async def api(settings, fake_backend, sessionmaker):
    """HTTP client for the app, with the fake model backend. Depends on sessionmaker so tables get cleaned."""
    import httpx
    from asgi_lifespan import LifespanManager

    from covora.api.app import create_app

    app = create_app(settings, backend=fake_backend)
    async with LifespanManager(app) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
def services(settings, sessionmaker, gateway, memory):
    from covora.services import Services

    return Services(settings=settings, sessionmaker=sessionmaker, gateway=gateway, memory=memory, research=None)
