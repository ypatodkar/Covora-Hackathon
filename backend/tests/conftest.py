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
