"""Ponto — API de registro de ponto (FastAPI + PostgreSQL)."""

from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.security import KIOSK_COOKIE, SESSION_COOKIE
from app.db.session import engine, init_db

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


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


@app.middleware("http")
async def check_origin(request: Request, call_next):
    """Proteção contra CSRF: requisição que altera dados só vale vinda das próprias páginas do ponto.

    Outros serviços no mesmo IP contam como "mesmo site" para o navegador, então só o cookie
    SameSite não basta. Navegadores sempre mandam Origin em POST/PUT/PATCH/DELETE; o app de celular
    não manda Origin nem cookie (usa a chave X-API-Key) e passa direto.
    """
    if request.method in UNSAFE_METHODS:
        origin = request.headers.get("origin")
        has_cookie = SESSION_COOKIE in request.cookies or KIOSK_COOKIE in request.cookies
        host = request.headers.get("host", "")
        if origin is not None:
            parts = urlsplit(origin)
            allowed = parts.netloc == host and (parts.scheme == "https" or not settings.cookie_secure)
        else:
            allowed = not has_cookie
        if not allowed:
            return JSONResponse({"error": "Origem da requisição não permitida"}, status_code=403)
    return await call_next(request)


app.include_router(api_router)
