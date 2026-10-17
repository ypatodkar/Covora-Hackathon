"""Everything an API request or a worker job needs, built once per process."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from covora.config import REPO_ROOT, Settings
from covora.db.session import make_engine, make_sessionmaker
from covora.gateway.backend import ChatBackend
from covora.gateway.gateway import ModelGateway
from covora.gateway.nvidia import NvidiaBackend
from covora.memory.store import MemoryStore
from covora.research.mock import MockProvider
from covora.research.youcom import YouComProvider


@dataclass
class Services:
    settings: Settings
    sessionmaker: async_sessionmaker[AsyncSession]
    gateway: ModelGateway
    memory: MemoryStore
    research: Any = None  # ResearchProvider (covora.research.provider)


def build_services(
    settings: Settings, *, backend: ChatBackend | None = None, research: Any = None
) -> tuple[Services, AsyncEngine]:
    engine = make_engine(settings.database_url)
    sessionmaker = make_sessionmaker(engine)
    gateway = ModelGateway(backend or NvidiaBackend(settings), settings)
    if research is None:
        research = _default_research(settings, sessionmaker)
    services = Services(
        settings=settings,
        sessionmaker=sessionmaker,
        gateway=gateway,
        memory=MemoryStore(sessionmaker, gateway),
        research=research,
    )
    return services, engine


def _default_research(settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]):
    if settings.research_provider == "mock":
        path = Path(settings.mock_web_path or "backend/tests/data/mock_web.json")
        return MockProvider.from_file(path if path.is_absolute() else REPO_ROOT / path)
    return YouComProvider(settings, sessionmaker)
