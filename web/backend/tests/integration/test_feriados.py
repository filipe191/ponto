"""Feriados da empresa: os que repetem todo ano, os móveis (Páscoa) e a trava de mês fechado."""

from tests.integration.conftest import ORIGIN, add_employee, login, new_company

HOUR = 3_600_000


def names(client, year: int) -> dict[str, str]:
    return {h["date"]: h["name"] for h in client.get(f"/api/admin/holidays?year={year}").json() if not h["national"]}


def test_feriado_que_repete_todo_ano(superadmin):
    _, adm = new_company(superadmin, "Feriados Anuais")
    client = login(adm)
    emp = add_employee(client, "Ciro", "515151", hired_on="2026-01-01")
    body = {"date": "2026-06-13", "name": "Santo Antônio", "yearly": True}
    assert client.post("/api/admin/holidays", json=body, headers=ORIGIN).status_code == 201
    assert names(client, 2026) == {"2026-06-13": "Santo Antônio"}
    assert names(client, 2028) == {"2028-06-13": "Santo Antônio"}
    assert names(client, 2025) == {}  # não volta para antes do cadastro
    listed = next(h for h in client.get("/api/admin/holidays?year=2027").json() if h["date"] == "2027-06-13")
    assert listed["yearly"] and listed["since"] == "2026-06-13"
    r = client.get(f"/api/admin/report?employee={emp}&month=2026-06").json()
    assert next(d for d in r["days"] if d["date"] == "2026-06-13")["holiday"] == "Santo Antônio"

    # Remover em 2028: para de repetir a partir de 2028; 2026 e 2027 continuam
    assert client.delete("/api/admin/holidays/2028-06-13", headers=ORIGIN).status_code == 200
    assert names(client, 2027) == {"2027-06-13": "Santo Antônio"} and names(client, 2028) == {}
    # Duplicado é recusado (projeção de 2027)
    assert client.post("/api/admin/holidays", json={"date": "2027-06-13", "name": "Outro"}, headers=ORIGIN).status_code == 409


def test_carnaval_e_corpus_christi_calculados(superadmin):
    _, adm = new_company(superadmin, "Feriados Moveis")
    client = login(adm)
    body = {"year": 2027, "items": ["carnaval", "corpus_christi"]}
    assert client.post("/api/admin/holidays/movable", json=body, headers=ORIGIN).status_code == 201
    # Páscoa de 2027: 28/03 → Carnaval 08 e 09/02, Corpus Christi 27/05
    assert names(client, 2027) == {
        "2027-02-08": "Carnaval (segunda-feira)",
        "2027-02-09": "Carnaval (terça-feira)",
        "2027-05-27": "Corpus Christi",
    }
    # De novo não duplica
    assert client.post("/api/admin/holidays/movable", json=body, headers=ORIGIN).status_code == 201
    assert len(names(client, 2027)) == 3


def test_feriado_em_mes_fechado_e_recusado(superadmin):
    _, adm = new_company(superadmin, "Feriados Fechado")
    client = login(adm)
    emp = add_employee(client, "Edu", "525252", hired_on="2026-01-01")
    assert client.post("/api/admin/closures", json={"month": "2026-03", "employee_id": emp}, headers=ORIGIN).status_code == 200
    response = client.post("/api/admin/holidays", json={"date": "2026-03-19", "name": "São José"}, headers=ORIGIN)
    assert response.status_code == 400 and "03/2026" in response.json()["error"]
    assert client.post("/api/admin/holidays", json={"date": "2026-04-23", "name": "São Jorge"}, headers=ORIGIN).status_code == 201
