"""Stable Web startup interface; implementation lives with its owning modules."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .runtime import Settings
from .service import Service
from .http import install_http


def create_app(settings: Settings) -> FastAPI:
    service = Service(settings)

    @asynccontextmanager
    async def lifespan(app):
        yield
        service.atlas_mapping.shutdown()
        service.execution.shutdown()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.service = service
    install_http(app, service, settings)
    return app
