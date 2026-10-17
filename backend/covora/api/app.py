from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from covora.api.deps import Services
from covora.api.errors import install_error_handlers
from covora.api.routes import health, icp, runs, workspace
from covora.config import Settings, get_settings
from covora.db.session import make_engine, make_sessionmaker
from covora.gateway.backend import ChatBackend
from covora.gateway.gateway import ModelGateway
from covora.gateway.nvidia import NvidiaBackend
from covora.memory.prompts import sync_prompts
from covora.memory.store import MemoryStore
from covora.workspace.service import ensure_workspace


def create_app(settings: Settings | None = None, *, backend: ChatBackend | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = make_engine(settings.database_url)
        sessionmaker = make_sessionmaker(engine)
        gateway = ModelGateway(backend or NvidiaBackend(settings), settings)
        async with sessionmaker() as session:
            await sync_prompts(session)
            await ensure_workspace(session)
        app.state.services = Services(
            settings=settings, sessionmaker=sessionmaker, gateway=gateway, memory=MemoryStore(sessionmaker, gateway)
        )
        yield
        await engine.dispose()

    app = FastAPI(title="Covora API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=[settings.cors_origin], allow_methods=["*"], allow_headers=["*"]
    )
    install_error_handlers(app, settings)
    for module in (health, workspace, icp, runs):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
