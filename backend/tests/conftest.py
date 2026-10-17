import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from covora.config import Settings
from covora.db.session import make_engine, make_sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://covora:covora@localhost:5434/covora_test")


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
            (
                await s.execute(
                    text(
                        "select tablename from pg_tables where schemaname = 'public' and tablename <> 'alembic_version'"
                    )
                )
            )
            .scalars()
            .all()
        )
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


@pytest.fixture
def mock_research():
    from covora.research.mock import MockProvider

    return MockProvider.from_file(BACKEND_DIR / "tests" / "data" / "mock_web.json")


@pytest.fixture
async def saved_icp(api):
    from tests.fixtures_icp import EXAMPLE_ICP

    r = await api.post("/api/icps", json={"prompt_text": "US manufacturers", "structured": EXAMPLE_ICP, "draft": None})
    return r.json()["id"]


class PipelineEnv:
    """A campaign from EXAMPLE_ICP with a scripted model and the fixture web."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


@pytest.fixture
async def discovery_env(session, workspace, settings, sessionmaker, mock_research):
    from covora.campaigns.service import create_campaign
    from covora.gateway.gateway import ModelGateway
    from covora.icp.models import IcpVersion
    from covora.memory.prompts import sync_prompts
    from covora.memory.store import MemoryStore
    from covora.observability.tracing import start_run
    from covora.services import Services
    from covora.workspace.settings import Goals
    from tests.fake_handlers import STANDARD_HANDLERS
    from tests.fakes import ScriptedBackend
    from tests.fixtures_icp import EXAMPLE_ICP

    backend = ScriptedBackend(settings.nemotron_embed_dim, STANDARD_HANDLERS)
    gateway = ModelGateway(backend, settings)
    services = Services(
        settings=settings,
        sessionmaker=sessionmaker,
        gateway=gateway,
        memory=MemoryStore(sessionmaker, gateway),
        research=mock_research,
    )
    await sync_prompts(session)
    icp = IcpVersion(workspace_id=workspace.id, version=1, prompt_text="p", structured=EXAMPLE_ICP, created_by="user")
    session.add(icp)
    await session.commit()
    campaign = await create_campaign(
        session, workspace_id=workspace.id, icp=icp, name="Test", goals=Goals(), target_prospects=3
    )
    ctx = await start_run(
        sessionmaker,
        kind="campaign",
        workspace_id=workspace.id,
        secrets=settings.secret_values(),
        campaign_id=campaign.id,
    )
    return PipelineEnv(
        services=services,
        backend=backend,
        ctx=ctx,
        campaign_id=campaign.id,
        sessionmaker=sessionmaker,
        workspace=workspace,
        settings=settings,
    )


@pytest.fixture
async def enrich_env(discovery_env):
    from sqlalchemy import update

    from covora.discovery.discover import discover_wave
    from covora.discovery.models import CampaignCompany

    env = discovery_env
    wave = await discover_wave(env.campaign_id, wave=1, ctx=env.ctx, services=env.services)
    env.candidate_ids = wave.new_company_ids

    async def reset_status(company_ids):
        async with env.sessionmaker() as s:
            await s.execute(
                update(CampaignCompany)
                .where(CampaignCompany.campaign_id == env.campaign_id, CampaignCompany.company_id.in_(company_ids))
                .values(status="candidate")
            )
            await s.commit()

    env.reset_status = reset_status
    return env


@pytest.fixture
async def people_env(enrich_env):
    from covora.discovery.enrich import enrich_and_score
    from tests.helpers import campaign_companies_by_domain

    env = enrich_env
    env.qualified_ids = await enrich_and_score(env.campaign_id, env.candidate_ids, ctx=env.ctx, services=env.services)
    rows = await campaign_companies_by_domain(env.sessionmaker, env.campaign_id)
    ids = {domain: row.company_id for domain, row in rows.items()}
    env.company_id = ids.__getitem__
    env.domain_of = {v: k for k, v in ids.items()}.__getitem__
    return env


@pytest.fixture
async def select_env(people_env):
    from covora.qualification.people import find_people

    env = people_env
    await find_people(env.campaign_id, env.qualified_ids, ctx=env.ctx, services=env.services)
    return env


@pytest.fixture(scope="session")
async def checkpointer_tables(settings, migrated):
    from covora.graphs.checkpointer import ensure_checkpointer_tables

    await ensure_checkpointer_tables(settings)


@pytest.fixture
async def graph_env(checkpointer_tables, discovery_env):
    from sqlalchemy import update

    from covora.campaigns.models import Campaign
    from covora.campaigns.service import campaign_funnel
    from covora.jobs.models import Job
    from covora.research.mock import ChargeWith, MockProvider
    from covora.workspace.models import Workspace

    env = discovery_env

    def job(resume: bool) -> Job:
        return Job(kind="campaign.run", payload={"campaign_id": str(env.campaign_id), "resume": resume})

    async def campaign() -> Campaign:
        async with env.sessionmaker() as s:
            return await s.get(Campaign, env.campaign_id)

    async def funnel() -> dict:
        async with env.sessionmaker() as s:
            return await campaign_funnel(s, env.campaign_id)

    async def set_budget(*, spent: float, cap: float) -> None:
        async with env.sessionmaker() as s:
            await s.execute(update(Workspace).where(Workspace.id == env.workspace.id).values(youcom_spend_usd=spent))
            await s.commit()
        env.services.settings = env.settings.model_copy(update={"youcom_budget_usd": cap})
        env.services.research = MockProvider.from_file(
            BACKEND_DIR / "tests" / "data" / "mock_web.json",
            charge_with=ChargeWith(sessionmaker=env.sessionmaker, cap=cap, price=0.05),
        )

    env.job, env.campaign, env.funnel, env.set_budget = job, campaign, funnel, set_budget
    return env


@pytest.fixture
async def draft_campaign_id(api, saved_icp):
    body = {"icp_version_id": saved_icp, "name": "Draft", "goals": {}, "prospect_limit": 3}
    return (await api.post("/api/campaigns", json=body)).json()["id"]


@pytest.fixture
async def completed_campaign(graph_env, api):
    from covora.graphs.jobs import run_campaign_job

    await run_campaign_job(graph_env.job(resume=False), graph_env.services)
    return str(graph_env.campaign_id)
