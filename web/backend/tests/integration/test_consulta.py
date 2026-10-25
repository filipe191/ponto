"""Administrador só de consulta: vê o espelho, o resumo, os CSVs e a auditoria; o backend recusa alterações."""

from tests.integration.conftest import ORIGIN, PASSWORD, add_employee, login, new_company, set_password


def test_consulta_ve_mas_nao_altera(superadmin):
    _, adm = new_company(superadmin, "Consulta")
    client = login(adm)
    emp = add_employee(client, "Rosa", "303030")
    body = {"username": "contador-consulta", "password": PASSWORD, "read_only": True}
    assert client.post("/api/admin/admins", json=body, headers=ORIGIN).status_code == 201
    set_password("contador-consulta")
    listed = {a["username"]: a for a in client.get("/api/admin/admins").json()}
    assert listed["contador-consulta"]["read_only"] is True and listed[adm]["read_only"] is False

    contador = login("contador-consulta")
    assert contador.get("/api/auth/admin").json()["read_only"] is True
    for path in ("/api/admin/employees", f"/api/admin/report?employee={emp}&month=2026-03",
                 "/api/admin/summary?month=2026-03", "/api/admin/audit", "/api/admin/rules", "/api/admin/holidays?year=2026"):
        assert contador.get(path).status_code == 200, path
    assert contador.get(f"/api/admin/report?employee={emp}&month=2026-03&format=csv").status_code == 200

    # Toda alteração é recusada no backend
    tries = [
        ("post", "/api/admin/employees", {"name": "X", "pin": "404040"}),
        ("patch", f"/api/admin/employees/{emp}", {"name": "Outra"}),
        ("post", "/api/admin/punches", {"employee_id": emp, "ts": "2026-03-02T08:00:00-03:00", "type": "entrada", "note": "x"}),
        ("post", "/api/admin/closures", {"month": "2026-03", "employee_id": emp}),
        ("post", "/api/admin/holidays", {"date": "2026-06-13", "name": "Santo Antônio"}),
        ("post", "/api/admin/absences", {"employee_id": emp, "kind": "ferias", "first_day": "2026-03-02", "last_day": "2026-03-03"}),
        ("post", "/api/admin/admins", {"username": "outro", "password": PASSWORD}),
        ("post", "/api/admin/kiosks/reset", None),
        ("post", "/api/auth/kiosk", None),
    ]
    for method, path, payload in tries:
        response = getattr(contador, method)(path, json=payload, headers=ORIGIN)
        assert response.status_code == 403, (path, response.status_code)
    assert client.get(f"/api/admin/employees").json()[0]["name"] == "Rosa"

    # A exportação fica na auditoria, com quem baixou
    exports = [a for a in client.get("/api/admin/audit?action=exportacao.").json()]
    assert exports and exports[0]["user"] == "contador-consulta"
