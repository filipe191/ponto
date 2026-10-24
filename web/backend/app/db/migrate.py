"""Aplica as migrações do Alembic na subida do backend."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
BASELINE = "0001"


def run_migrations(engine: Engine) -> None:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        tables = inspect(conn)
        # Banco criado antes do Alembic (create_all): já está na versão inicial
        if not tables.has_table("alembic_version") and tables.has_table("employees"):
            command.stamp(config, BASELINE)
        command.upgrade(config, "head")
