from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from covora.config import Settings
from covora.gateway.gateway import ModelGateway
from covora.memory.store import MemoryStore


@dataclass
class Services:
    settings: Settings
    sessionmaker: async_sessionmaker[AsyncSession]
    gateway: ModelGateway
    memory: MemoryStore


def get_services(request: Request) -> Services:
    return request.app.state.services


async def get_session(services: Services = Depends(get_services)) -> AsyncIterator[AsyncSession]:
    async with services.sessionmaker() as session:
        yield session
