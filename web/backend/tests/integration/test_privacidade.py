"""Link público do aviso de privacidade: cada empresa tem o seu, com um código aleatório."""

from fastapi.testclient import TestClient

from app.core.security import KIOSK_COOKIE
from app.main import app
from tests.integration.conftest import ORIGIN, kiosk_client, login, new_company


def test_link_mostra_a_empresa_sem_login(superadmin):
    company, adm = new_company(superadmin, "Privada", "rh@privada")
    code = login(adm).get("/api/auth/admin").json()["privacy_code"]
    assert code and len(code) >= 12
    assert next(c for c in superadmin.get("/api/companies").json() if c["id"] == company)["public_code"] == code
    info = TestClient(app).get(f"/api/privacidade?e={code}").json()
    assert (info["empresa"], info["contato"]) == ("Privada", "rh@privada")


def test_codigo_errado_ou_empresa_desativada_dao_o_texto_generico(superadmin):
    company, adm = new_company(superadmin, "Privada Off", "rh@off")
    code = login(adm).get("/api/auth/admin").json()["privacy_code"]
    assert TestClient(app).get("/api/privacidade?e=nao-existe").json()["empresa"] == ""
    superadmin.patch(f"/api/companies/{company}", json={"active": False}, headers=ORIGIN)
    assert TestClient(app).get(f"/api/privacidade?e={code}").json()["empresa"] == ""
    superadmin.patch(f"/api/companies/{company}", json={"active": True}, headers=ORIGIN)


def test_relogio_nao_recebe_o_codigo(superadmin):
    _, adm = new_company(superadmin, "Privada Relogio")
    token = login(adm).post("/api/auth/kiosk", headers=ORIGIN).cookies.get(KIOSK_COOKIE)
    me = kiosk_client(token).get("/api/auth/me").json()
    assert me["company"] == "Privada Relogio" and me["privacy_code"] is None
