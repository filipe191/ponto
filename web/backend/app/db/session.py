"""Engine e sessões do SQLAlchemy."""

import logging
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

log = logging.getLogger("ponto")

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db


def init_db() -> None:
    """Confere a configuração, aplica as migrações e cria o login na primeira subida."""
    if not settings.pin_key:
        raise RuntimeError("Defina PIN_KEY no .env (gere com: openssl rand -hex 32)")
    if not settings.secret_key_from_env:
        log.warning("SECRET_KEY não definida: os logins e relógios caem a cada reinício do backend")

    from app.db.migrate import run_migrations

    run_migrations(engine)

    from app.services.auth_service import AuthService

    with SessionLocal() as db:
        AuthService(db).ensure_setup()
