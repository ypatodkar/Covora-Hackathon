from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from covora.services import Services

__all__ = ["Services", "get_services", "get_session"]


def get_services(request: Request) -> Services:
    return request.app.state.services


async def get_session(services: Services = Depends(get_services)) -> AsyncIterator[AsyncSession]:
    async with services.sessionmaker() as session:
        yield session
