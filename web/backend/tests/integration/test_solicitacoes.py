"""E-mail de aviso das solicitações do app: um por empresa a cada intervalo, sem dados dos funcionários."""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from tests.integration.conftest import ORIGIN, add_employee, login, new_company


@pytest.fixture
def smtp():
    settings.smtp_host = "smtp.teste"
    with patch("app.services.notify.send_email") as send:
        yield send
    settings.smtp_host = ""


def _phone(superadmin, name: str, email: str) -> tuple[int, dict]:
    company, adm = new_company(superadmin, name)
    assert superadmin.patch(f"/api/companies/{company}", json={"notify_email": email}, headers=ORIGIN).status_code == 200
    client = login(adm)
    employee = add_employee(client, "Bia " + name, "135790")
    key = client.post(f"/api/admin/employees/{employee}/devices", json={"name": "Cel"}, headers=ORIGIN).json()["key"]
    return company, {"X-API-Key": key}


def _forgot(phone: dict, ts: str = "2026-03-02T08:00:00-03:00") -> None:
    batida = {"id": str(uuid.uuid4()), "tipo": "ENTRADA", "ocorridoEm": ts, "manual": True}
    response = TestClient(app).post("/api/pontos/lote", json={"batidas": [batida]}, headers=phone)
    assert response.status_code == 200 and response.json()["aceitas"], response.text


def test_solicitacao_avisa_a_empresa_uma_vez_por_intervalo(superadmin, smtp):
    _, phone = _phone(superadmin, "Avisada", "rh@avisada.com, dono@avisada.com")
    _forgot(phone)
    smtp.assert_called_once()
    to, subject, body = smtp.call_args.args
    assert to == ["rh@avisada.com", "dono@avisada.com"]
    assert subject == "Ponto: 1 solicitação pendente" and "Avisada" in body
    assert "Bia" not in subject + body  # nenhum dado do funcionário no e-mail
    _forgot(phone, "2026-03-03T08:00:00-03:00")
    smtp.assert_called_once()  # dentro do intervalo: não manda outro


def test_sem_email_ou_sem_smtp_nao_envia(superadmin, smtp):
    _, phone = _phone(superadmin, "Calada", "")
    _forgot(phone)
    smtp.assert_not_called()
    settings.smtp_host = ""
    _, phone = _phone(superadmin, "Sem Smtp", "rh@semsmtp.com")
    _forgot(phone)
    smtp.assert_not_called()


def test_email_invalido_e_recusado(superadmin):
    company, _ = new_company(superadmin, "Email Ruim")
    response = superadmin.patch(f"/api/companies/{company}", json={"notify_email": "rh@"}, headers=ORIGIN)
    assert response.status_code == 400
    response = superadmin.patch(f"/api/companies/{company}", json={"notify_email": " rh@ok.com "}, headers=ORIGIN)
    assert response.json()["notify_email"] == "rh@ok.com"
