"""Ponto — API de registro de ponto (FastAPI + PostgreSQL)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.db.session import engine, init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield
    engine.dispose()


app = FastAPI(
    title="Ponto",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.api_docs else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.api_docs else None,
)
register_error_handlers(app)
app.include_router(api_router)
