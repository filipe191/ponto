"""Uma empresa não enxerga nem altera os dados de outra."""

from fastapi.testclient import TestClient

from app.core.security import KIOSK_COOKIE
from app.main import app
from tests.integration.conftest import ORIGIN, add_employee, kiosk_client, login, new_company, open_company


def test_admin_de_uma_empresa_nao_ve_a_outra(superadmin):
    a, adm_a = new_company(superadmin, "Isola A")
    b, adm_b = new_company(superadmin, "Isola B")
    client_a, client_b = login(adm_a), login(adm_b)
    ana = add_employee(client_a, "Ana A", "222333")
    add_employee(client_b, "Bruno B", "222333")  # o mesmo PIN em outra empresa é aceito
    client_a.post(
        "/api/admin/punches",
        json={"employee_id": ana, "ts": "2026-09-01T08:00:00-03:00", "type": "entrada", "note": "x"},
        headers=ORIGIN,
    )
    punch_id = client_a.get(f"/api/admin/report?employee={ana}&month=2026-09").json()["days"][0]["punches"][0]["id"]

    assert [e["name"] for e in client_b.get("/api/admin/employees").json()] == ["Bruno B"]
    assert client_b.get(f"/api/admin/report?employee={ana}&month=2026-09").status_code == 400
    assert client_b.patch(f"/api/admin/employees/{ana}", json={"name": "x"}, headers=ORIGIN).status_code == 404
    assert client_b.get(f"/api/admin/employees/{ana}/export").status_code == 404
    assert client_b.get(f"/api/admin/employees/{ana}/devices").status_code == 404
    assert client_b.post(f"/api/admin/employees/{ana}/devices", json={"name": "x"}, headers=ORIGIN).status_code == 404
    assert client_b.get(f"/api/admin/punches/{punch_id}/history").status_code == 404
    assert client_b.delete(f"/api/admin/punches/{punch_id}", headers=ORIGIN).status_code == 404
    assert client_b.post(f"/api/admin/punches/{punch_id}/restore", headers=ORIGIN).status_code == 404
    response = client_b.post(
        "/api/admin/punches",
        json={"employee_id": ana, "ts": "2026-09-02T08:00:00-03:00", "type": "entrada", "note": "x"},
        headers=ORIGIN,
    )
    assert response.status_code == 400
    closure = {"month": "2026-09", "employee_id": ana}
    assert client_b.post("/api/admin/closures", json=closure, headers=ORIGIN).status_code == 404
    assert client_b.delete(f"/api/admin/closures/{ana}/2026-09?note=x", headers=ORIGIN).status_code == 404
    admin_ids = [x["id"] for x in client_a.get("/api/admin/admins").json()]
    assert all(client_b.delete(f"/api/admin/admins/{i}", headers=ORIGIN).status_code == 404 for i in admin_ids)
    assert [x["username"] for x in client_b.get("/api/admin/admins").json()] == [adm_b]
    assert all("Ana A" not in x["summary"] for x in client_b.get("/api/admin/audit").json())
    assert [r["employee"]["name"] for r in client_b.get("/api/admin/summary?month=2026-09").json()] == ["Bruno B"]


def test_feriados_separados(superadmin):
    a, adm_a = new_company(superadmin, "Feriado A")
    b, adm_b = new_company(superadmin, "Feriado B")
    client_a, client_b = login(adm_a), login(adm_b)
    assert client_a.post("/api/admin/holidays", json={"date": "2026-08-20", "name": "Da A"}, headers=ORIGIN).status_code == 201
    assert client_b.post("/api/admin/holidays", json={"date": "2026-08-20", "name": "Da B"}, headers=ORIGIN).status_code == 201
    custom = [h["name"] for h in client_b.get("/api/admin/holidays?year=2026").json() if not h["national"]]
    assert custom == ["Da B"]


def test_admin_de_empresa_nao_age_como_superadmin(superadmin):
    _, adm = new_company(superadmin, "Sem Poder")
    client = login(adm)
    assert client.get("/api/companies").status_code == 403
    assert client.get("/api/companies/audit").status_code == 403
    assert client.get("/api/companies/superadmins").status_code == 403
    assert client.post("/api/auth/company", json={"company_id": 1}, headers=ORIGIN).status_code == 403
    rule = {"valid_from": "2026-12-01", "tolerance_minutes": 5, "night_start_hour": 22, "night_end_hour": 5,
            "night_hour_minutes": 52.5, "max_shift_hours": 16}
    assert client.post("/api/admin/rules", json=rule, headers=ORIGIN).status_code == 403


def test_relogio_bate_o_ponto_so_da_propria_empresa(superadmin):
    a, adm_a = new_company(superadmin, "Relogio A", "rh@a")
    b, adm_b = new_company(superadmin, "Relogio B", "rh@b")
    add_employee(login(adm_a), "Ana Relógio", "445566")
    client_b = login(adm_b)
    add_employee(client_b, "Bruno Relógio", "445566")
    token = client_b.post("/api/auth/kiosk", headers=ORIGIN).cookies.get(KIOSK_COOKIE)
    clock = kiosk_client(token)
    response = clock.post("/api/punch", json={"pin": "445566"}, headers=ORIGIN)
    assert response.status_code == 201 and response.json()["name"] == "Bruno Relógio"
    assert clock.get("/api/privacidade").json()["contato"] == "rh@b"
    assert TestClient(app).get("/api/privacidade").json()["empresa"] == ""

    # "Desligar todos os relógios" de uma empresa não derruba os da outra
    token_a = login(adm_a).post("/api/auth/kiosk", headers=ORIGIN).cookies.get(KIOSK_COOKIE)
    assert login(adm_b).post("/api/admin/kiosks/reset", headers=ORIGIN).status_code == 200
    assert clock.get("/api/auth/me").status_code == 401
    assert kiosk_client(token_a).get("/api/auth/me").status_code == 200


def test_empresa_desativada_para_tudo(superadmin):
    company, adm = new_company(superadmin, "Desligada")
    client = login(adm)
    employee = add_employee(client, "Clara", "778899")
    key = client.post(f"/api/admin/employees/{employee}/devices", json={"name": "Cel"}, headers=ORIGIN).json()["key"]
    clock = kiosk_client(client.post("/api/auth/kiosk", headers=ORIGIN).cookies.get(KIOSK_COOKIE))
    client = login(adm)
    phone = {"X-API-Key": key}
    assert TestClient(app).get("/api/pontos/ultima", headers=phone).status_code == 200

    assert superadmin.patch(f"/api/companies/{company}", json={"active": False}, headers=ORIGIN).status_code == 200
    assert client.get("/api/admin/employees").status_code == 401
    login(adm, expected=403)
    assert clock.post("/api/punch", json={"pin": "778899"}, headers=ORIGIN).status_code == 401
    assert TestClient(app).get("/api/pontos/ultima", headers=phone).status_code == 401

    assert superadmin.patch(f"/api/companies/{company}", json={"active": True}, headers=ORIGIN).status_code == 200
    login(adm)


def test_superadmin_troca_de_empresa_e_fica_registrado(superadmin):
    company, adm = new_company(superadmin, "Visitada")
    open_company(superadmin, company)
    assert superadmin.get("/api/auth/admin").json()["company"] == "Visitada"
    actions = [x["action"] for x in login(adm).get("/api/admin/audit").json()]
    assert "admin.empresa_aberta" in actions
