"""A migração para várias empresas preserva o que já existia."""

from sqlalchemy import text

from app.db.session import SessionLocal
from tests.integration.conftest import ORIGIN, kiosk_client


def rows(sql: str) -> list[tuple]:
    with SessionLocal() as db:
        return [tuple(r) for r in db.execute(text(sql)).all()]


def test_dados_viram_a_empresa_1(legacy):
    assert rows("SELECT id, name, privacy_contact FROM companies ORDER BY id")[0] == (1, "Padaria", "rh@padaria")
    assert rows("SELECT name, company_id FROM employees WHERE id = 1") == [("Ana", 1)]
    assert rows("SELECT name, company_id FROM holidays") == [("Santo Antônio", 1)]
    assert rows("SELECT company_id FROM audit_log WHERE summary = 'antigo'") == [(1,)]
    assert rows("SELECT key FROM app_settings WHERE key = 'kiosk_secret'") == []


def test_admin_mais_antigo_vira_superadmin(legacy):
    assert rows("SELECT username, company_id, superadmin FROM admin_account ORDER BY id") == [
        ("admin", 1, True),
        ("beto", 1, False),
    ]


def test_empresas_recebem_as_regras_do_env(legacy):
    from app.core.config import settings

    assert rows("SELECT timezone, offline_max_hours FROM companies WHERE id = 1") == [
        (settings.tz, settings.offline_max_hours)
    ]
    assert rows("SELECT valid_from::text, tolerance_minutes, max_shift_hours FROM company_rules WHERE company_id = 1") == [
        ("2000-01-01", settings.tolerance_minutes, settings.max_shift_hours)
    ]


def test_relogio_liberado_antes_continua_valendo(legacy):
    clock = kiosk_client(legacy["kiosk"])
    me = clock.get("/api/auth/me").json()
    assert me["kiosk"] and me["company"] == "Padaria"
    response = clock.post("/api/portal/report", json={"pin": "123456", "month": "2026-10"}, headers=ORIGIN)
    assert response.status_code == 200 and response.json()["employee"]["name"] == "Ana"
    privacy = clock.get("/api/privacidade").json()
    assert (privacy["empresa"], privacy["contato"]) == ("Padaria", "rh@padaria")


def test_auditoria_continua_so_aceitando_inclusoes(legacy):
    import pytest
    from sqlalchemy.exc import DBAPIError

    with SessionLocal() as db, pytest.raises(DBAPIError):
        db.execute(text("UPDATE audit_log SET company_id = 99"))


def test_jornada_antiga_vira_minutos_por_dia(legacy):
    # Ana tinha 8h de segunda a sexta (480, "12345"): a migração 0014 mantém o mesmo previsto
    assert rows("SELECT kind, day_minutes, cycle_start FROM employee_schedules WHERE employee_id = 1") == [
        ("semana", "480,480,480,480,480,0,0", None)
    ]


def test_regra_antiga_fica_sem_prorrogacao_noturna(legacy):
    # A migração 0019 não muda o cálculo de quem já existia
    assert rows("SELECT night_extension FROM company_rules WHERE company_id = 1") == [(False,)]
