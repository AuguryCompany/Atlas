"""Augury Atlas API entry point: ``uvicorn atlas.main:app``."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .audit import AuditMiddleware
from .config import Settings, get_settings
from .db import Database
from .routers import analysis, hazards, infrastructure, logistics, platform


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        app.state.db.close()

    app = FastAPI(
        title="Augury Atlas API",
        description="Geospatial Intelligence Platform — See the Bigger Picture.",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = Database(settings.db_path)
    app.state.db.seed_if_empty()

    app.add_middleware(AuditMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (platform, infrastructure, hazards, analysis, logistics):
        app.include_router(module.router)
    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = create_app()
