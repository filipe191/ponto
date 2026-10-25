"""Início do controle e saldo inicial do banco de horas: dias antes do sistema não viram falta."""

from tests.integration.conftest import ORIGIN, add_employee, add_punch, login, new_company, open_company

HOUR = 3_600_000


def report(client, emp: int, month: str) -> dict:
    return client.get(f"/api/admin/report?employee={emp}&month={month}").json()


def day(r: dict, iso: str) -> dict:
    return next(d for d in r["days"] if d["date"] == iso)


def test_dias_antes_do_controle_nao_viram_falta(superadmin):
    company, adm = new_company(superadmin, "Controle Antigo")
    open_company(superadmin, company)
    # Admitida em janeiro, mas a empresa só começa a usar o sistema em 02/03
    emp = add_employee(superadmin, "Vera", "565656", hired_on="2026-01-05")
    assert superadmin.patch("/api/admin/rules/settings", json={"control_start": "2026-03-02"}, headers=ORIGIN).status_code == 200
    add_punch(superadmin, emp, "2026-03-02T08:00:00-03:00", "entrada")
    add_punch(superadmin, emp, "2026-03-02T17:00:00-03:00", "saida")

    fev = report(superadmin, emp, "2026-02")
    assert {d["status"] for d in fev["days"]} == {"antes"} and fev["bankMs"] == 0
    mar = report(superadmin, emp, "2026-03")
    assert mar["previousBalanceMs"] == 0 and mar["controlFrom"] == "2026-03-02"
    assert day(mar, "2026-03-02")["balanceMs"] == HOUR  # 9h num dia de 8h
    assert day(mar, "2026-03-03")["status"] == "falta"  # depois do início, falta é falta

    rules = login(adm).get("/api/admin/rules").json()
    assert rules["control_start"] == "2026-03-02"
    # Voltar a "desde a admissão" traz de volta as faltas de janeiro e fevereiro
    assert superadmin.patch("/api/admin/rules/settings", json={"control_start": None}, headers=ORIGIN).status_code == 200
    assert report(superadmin, emp, "2026-03")["previousBalanceMs"] < 0


def test_inicio_do_funcionario_e_saldo_inicial(superadmin):
    company, adm = new_company(superadmin, "Controle Saldo")
    client = login(adm)
    emp = add_employee(client, "Davi", "676767", hired_on="2025-06-01")
    body = {"control_start": "2026-04-01", "initial_balance_minutes": 750, "initial_balance_note": "planilha 2025"}
    assert client.patch(f"/api/admin/employees/{emp}", json=body, headers=ORIGIN).status_code == 200

    mar = report(client, emp, "2026-03")
    assert mar["bankMs"] == 0  # antes do início: nem o saldo inicial nem faltas
    abr = report(client, emp, "2026-04")
    assert abr["previousBalanceMs"] == 750 * 60_000 and abr["initialBalanceMs"] == 750 * 60_000
    out = next(e for e in client.get("/api/admin/employees").json() if e["id"] == emp)
    assert (out["control_start"], out["initial_balance_minutes"]) == ("2026-04-01", 750)
    audit = [a["action"] for a in client.get("/api/admin/audit").json()]
    assert "funcionario.saldo_inicial" in audit

    # Saldo sem motivo é recusado
    response = client.patch(f"/api/admin/employees/{emp}", json={"initial_balance_minutes": 10, "initial_balance_note": ""}, headers=ORIGIN)
    assert response.status_code == 400


def test_mes_fechado_trava_inicio_e_saldo(superadmin):
    company, adm = new_company(superadmin, "Controle Fechado")
    client = login(adm)
    emp = add_employee(client, "Ivo", "787878", hired_on="2026-01-05")
    assert client.post("/api/admin/closures", json={"month": "2026-02", "employee_id": emp}, headers=ORIGIN).status_code == 200
    response = client.patch(f"/api/admin/employees/{emp}", json={"control_start": "2026-03-01"}, headers=ORIGIN)
    assert response.status_code == 400 and "02/2026" in response.json()["error"]
    body = {"initial_balance_minutes": 60, "initial_balance_note": "acerto"}
    assert client.patch(f"/api/admin/employees/{emp}", json=body, headers=ORIGIN).status_code == 400
