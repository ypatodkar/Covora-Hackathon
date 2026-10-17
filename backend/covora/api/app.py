from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from covora.api.errors import install_error_handlers
from covora.api.routes import (
    campaigns,
    exports,
    health,
    icp,
    prospects,
    reps,
    runs,
    settings,
    templates,
    workspace,
)
from covora.config import Settings, get_settings
from covora.gateway.backend import ChatBackend
from covora.memory.prompts import sync_prompts
from covora.outreach.templates import sync_templates
from covora.services import build_services
from covora.workspace.service import ensure_workspace


def create_app(app_settings: Settings | None = None, *, backend: ChatBackend | None = None, research=None) -> FastAPI:
    app_settings = app_settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        services, engine = build_services(app_settings, backend=backend, research=research)
        async with services.sessionmaker() as session:
            await sync_prompts(session)
            workspace = await ensure_workspace(session)
            await sync_templates(session, workspace.id)
        app.state.services = services
        yield
        await engine.dispose()

    app = FastAPI(title="Covora API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=[app_settings.cors_origin], allow_methods=["*"], allow_headers=["*"]
    )
    install_error_handlers(app, app_settings)
    for module in (health, workspace, settings, icp, runs, campaigns, prospects, exports, templates, reps):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
