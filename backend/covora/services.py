"""Everything an API request or a worker job needs, built once per process."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from covora.config import Settings
from covora.db.session import make_engine, make_sessionmaker
from covora.gateway.backend import ChatBackend
from covora.gateway.gateway import ModelGateway
from covora.gateway.nvidia import NvidiaBackend
from covora.memory.store import MemoryStore


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
    services = Services(
        settings=settings,
        sessionmaker=sessionmaker,
        gateway=gateway,
        memory=MemoryStore(sessionmaker, gateway),
        research=research,
    )
    return services, engine
