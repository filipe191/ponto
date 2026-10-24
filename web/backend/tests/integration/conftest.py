"""Testes de ponta a ponta contra um Postgres de verdade.

Rodam só com um banco descartável: PGDATABASE precisa conter "test" (o banco é apagado e recriado).
Sem isso, os testes desta pasta são ignorados. Ex.: PGHOST=localhost PGDATABASE=ponto_test pytest
"""

import os

import pytest

if "test" not in os.environ.get("PGDATABASE", ""):
    collect_ignore_glob = ["test_*.py"]
else:
    from alembic import command
    from alembic.config import Config
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from app.core.config import settings
    from app.core.security import ROLE_KIOSK, create_session, hash_password, hash_pin
    from app.db.migrate import MIGRATIONS_DIR
    from app.db.session import SessionLocal, engine
    from app.main import app

PASSWORD = "Senha-Bem-Forte-2026"
ORIGIN = {"Origin": "http://testserver"}
LEGACY_KIOSK_SECRET = "segredo-dos-relogios-antigos"


def _migrate_to(revision: str) -> None:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        command.upgrade(config, revision)


@pytest.fixture(scope="session")
def legacy():
    """Banco como estava antes das várias empresas (0007), com dados, migrado para a versão atual.

    Devolve o token de um relógio liberado antes da mudança.
    """
    settings.admin_2fa_required = False
    settings.empresa_nome = "Padaria"
    settings.privacidade_contato = "rh@padaria"
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    _migrate_to("0007")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_settings (key, value) VALUES ('kiosk_secret', :s)"), {"s": LEGACY_KIOSK_SECRET})
        conn.execute(
            text("INSERT INTO admin_account (username, password_hash) VALUES ('admin', :h), ('beto', :h)"),
            {"h": hash_password(PASSWORD)},
        )
        conn.execute(
            text("INSERT INTO employees (name, pin_hash, hired_on) VALUES ('Ana', :h, '2026-01-01')"),
            {"h": hash_pin("123456")},
        )
        conn.execute(
            text(
                "INSERT INTO employee_schedules (employee_id, valid_from, daily_minutes, workdays) "
                "VALUES (1, '2026-01-01', 480, '12345')"
            )
        )
        conn.execute(text("INSERT INTO punches (employee_id, ts, type) VALUES (1, now() - interval '2 hours', 'entrada')"))
        conn.execute(text("INSERT INTO holidays (date, name) VALUES ('2026-06-13', 'Santo Antônio')"))
        conn.execute(text("""INSERT INTO audit_log ("user", action, summary) VALUES ('admin', 'feriado.adicionado', 'antigo')"""))
    with TestClient(app):  # a subida aplica as migrações que faltam (0008 em diante)
        pass
    return {"kiosk": create_session(ROLE_KIOSK, "relogio", LEGACY_KIOSK_SECRET, 3600)}


def set_password(username: str) -> None:
    """Senha definitiva (sem a troca obrigatória do primeiro acesso)."""
    with SessionLocal() as db:
        db.execute(
            text("UPDATE admin_account SET password_hash = :h, must_change_password = FALSE WHERE username = :u"),
            {"h": hash_password(PASSWORD), "u": username},
        )
        db.commit()


def login(username: str, expected: int = 200) -> "TestClient":
    client = TestClient(app)
    response = client.post("/api/auth/login", json={"username": username, "password": PASSWORD}, headers=ORIGIN)
    assert response.status_code == expected, response.text
    return client


def kiosk_client(token: str) -> "TestClient":
    from app.core.security import KIOSK_COOKIE

    client = TestClient(app)
    client.cookies.set(KIOSK_COOKIE, token)
    return client


@pytest.fixture
def superadmin(legacy):
    set_password("admin")
    return login("admin")


def new_company(sa, name: str, contact: str = "") -> tuple[int, str]:
    """Cadastra a empresa com o primeiro admin (senha definitiva) e devolve (id, usuário do admin)."""
    username = "adm-" + name.lower().replace(" ", "-")
    response = sa.post(
        "/api/companies",
        json={"name": name, "privacy_contact": contact, "admin_username": username, "admin_password": PASSWORD},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    set_password(username)
    return response.json()["id"], username


def open_company(sa, company_id: int) -> None:
    assert sa.post("/api/auth/company", json={"company_id": company_id}, headers=ORIGIN).status_code == 200


def add_employee(client, name: str, pin: str, hired_on: str = "2026-01-01") -> int:
    response = client.post(
        "/api/admin/employees",
        json={"name": name, "pin": pin, "daily_minutes": 480, "workdays": "12345", "hired_on": hired_on},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def add_punch(client, employee_id: int, ts: str, kind: str) -> None:
    response = client.post(
        "/api/admin/punches",
        json={"employee_id": employee_id, "ts": ts, "type": kind, "note": "teste"},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
