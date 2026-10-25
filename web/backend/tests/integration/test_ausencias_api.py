"""Ausências pela API: lançar, ver no espelho e no resumo, remover; mês fechado e outras empresas."""

from tests.integration.conftest import ORIGIN, add_employee, login, new_company

HOUR = 3_600_000


def day(r: dict, iso: str) -> dict:
    return next(d for d in r["days"] if d["date"] == iso)


def test_atestado_e_folga_pela_api(superadmin):
    _, adm = new_company(superadmin, "Ausencias")
    client = login(adm)
    emp = add_employee(client, "Bel", "919191", hired_on="2026-03-01")
    atestado = {"employee_id": emp, "kind": "atestado", "first_day": "2026-03-02", "last_day": "2026-03-03", "note": "papel no RH"}
    response = client.post("/api/admin/absences", json=atestado, headers=ORIGIN)
    assert response.status_code == 201, response.text
    absence_id = response.json()["id"]
    folga = {"employee_id": emp, "kind": "folga", "first_day": "2026-03-04", "last_day": "2026-03-04"}
    assert client.post("/api/admin/absences", json=folga, headers=ORIGIN).status_code == 201
    # Sobreposição é recusada
    assert client.post("/api/admin/absences", json={**folga, "kind": "abonada"}, headers=ORIGIN).status_code == 400

    r = client.get(f"/api/admin/report?employee={emp}&month=2026-03").json()
    assert day(r, "2026-03-02")["status"] == "ausencia" and day(r, "2026-03-02")["balanceMs"] == 0
    assert day(r, "2026-03-04")["balanceMs"] == -8 * HOUR
    assert r["absenceDays"] == {"atestado": 2, "folga": 1} and r["creditedMs"] == 16 * HOUR
    summary = client.get("/api/admin/summary?month=2026-03").json()
    row = next(x for x in summary if x["employee"]["id"] == emp)
    assert row["absences"] == sum(d["status"] == "falta" for d in r["days"]) and row["creditedMs"] == 16 * HOUR
    csv = client.get("/api/admin/summary?month=2026-03&format=csv").text
    assert "Atestado médico (dias)" in csv

    listed = client.get(f"/api/admin/employees/{emp}/absences").json()
    assert [a["kind"] for a in listed] == ["folga", "atestado"]
    actions = [a["action"] for a in client.get("/api/admin/audit").json()]
    assert actions.count("ausencia.lancada") == 2

    assert client.delete(f"/api/admin/absences/{absence_id}", headers=ORIGIN).status_code == 200
    r = client.get(f"/api/admin/report?employee={emp}&month=2026-03").json()
    assert day(r, "2026-03-02")["status"] == "falta"


def test_mes_fechado_e_outra_empresa(superadmin):
    _, adm_a = new_company(superadmin, "Ausencias A")
    _, adm_b = new_company(superadmin, "Ausencias B")
    a, b = login(adm_a), login(adm_b)
    emp = add_employee(a, "Gil", "929292", hired_on="2026-03-01")
    ok = {"employee_id": emp, "kind": "ferias", "first_day": "2026-04-06", "last_day": "2026-04-10"}
    created = a.post("/api/admin/absences", json=ok, headers=ORIGIN).json()
    # A outra empresa não lança, não lista e não remove
    assert b.post("/api/admin/absences", json={**ok, "first_day": "2026-05-04", "last_day": "2026-05-04"}, headers=ORIGIN).status_code == 404
    assert b.get(f"/api/admin/employees/{emp}/absences").status_code == 404
    assert b.delete(f"/api/admin/absences/{created['id']}", headers=ORIGIN).status_code == 404

    assert a.post("/api/admin/closures", json={"month": "2026-04", "employee_id": emp}, headers=ORIGIN).status_code == 200
    response = a.delete(f"/api/admin/absences/{created['id']}", headers=ORIGIN)
    assert response.status_code == 400 and "04/2026" in response.json()["error"]
    late = {"employee_id": emp, "kind": "atestado", "first_day": "2026-04-30", "last_day": "2026-05-02"}
    assert a.post("/api/admin/absences", json=late, headers=ORIGIN).status_code == 400
    # Março não está fechado: pode
    assert a.post("/api/admin/absences", json={**late, "first_day": "2026-03-30", "last_day": "2026-03-31"}, headers=ORIGIN).status_code == 201
