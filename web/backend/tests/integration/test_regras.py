"""Regras de jornada por empresa, com vigência: mudar não altera o passado."""

from tests.integration.conftest import ORIGIN, add_employee, add_punch, login, new_company, open_company

URBANO = {"tolerance_minutes": 10, "night_start_hour": 22, "night_end_hour": 5, "night_hour_minutes": 52.5,
          "max_shift_hours": 16}
HOUR = 3_600_000


def rule(valid_from: str, **changes) -> dict:
    return {"valid_from": valid_from, **URBANO, **changes}


def day(report: dict, iso: str) -> dict:
    return next(d for d in report["days"] if d["date"] == iso)


def test_nova_regra_vale_so_a_partir_da_data(superadmin):
    company, adm = new_company(superadmin, "Regras Vigencia")
    open_company(superadmin, company)
    emp = add_employee(superadmin, "Rui", "121212")
    # 02/03 (seg) e 04/03 (qua), das 20h às 4h: 8 horas reais
    add_punch(superadmin, emp, "2026-03-02T20:00:00-03:00", "entrada")
    add_punch(superadmin, emp, "2026-03-03T04:00:00-03:00", "saida")
    add_punch(superadmin, emp, "2026-03-04T20:00:00-03:00", "entrada")
    add_punch(superadmin, emp, "2026-03-05T04:00:00-03:00", "saida")
    # 05/03 e 10/03: 8h05 trabalhadas (5 minutos a mais)
    for d in ("05", "10"):
        add_punch(superadmin, emp, f"2026-03-{d}T08:00:00-03:00", "entrada")
        add_punch(superadmin, emp, f"2026-03-{d}T16:05:00-03:00", "saida")

    before = superadmin.get(f"/api/admin/report?employee={emp}&month=2026-03").json()
    # Urbano: noturno 22h–4h = 6 horas reais, com hora de 52min30s
    assert day(before, "2026-03-02")["nightMs"] == round(6 * HOUR * 60 / 52.5)

    # Rural (pecuária) a partir de 04/03: noturno 20h–4h com hora de 60 min; tolerância zero a partir de 09/03
    response = superadmin.post(
        "/api/admin/rules", json=rule("2026-03-04", night_start_hour=20, night_end_hour=4, night_hour_minutes=60),
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    rural_sem_tolerancia = rule("2026-03-09", night_start_hour=20, night_end_hour=4, night_hour_minutes=60,
                                tolerance_minutes=0)
    assert superadmin.post("/api/admin/rules", json=rural_sem_tolerancia, headers=ORIGIN).status_code == 201

    after = superadmin.get(f"/api/admin/report?employee={emp}&month=2026-03").json()
    assert day(after, "2026-03-02")["nightMs"] == day(before, "2026-03-02")["nightMs"]  # o passado não muda
    assert day(after, "2026-03-04")["nightMs"] == 8 * HOUR
    assert day(after, "2026-03-05")["balanceMs"] == 0  # 5 min dentro da tolerância de 10
    assert day(after, "2026-03-10")["balanceMs"] == 5 * 60_000  # sem tolerância

    rules = login(adm).get("/api/admin/rules").json()
    assert [p["valid_from"] for p in rules["periods"]] == ["2000-01-01", "2026-03-04", "2026-03-09"]
    assert rules["can_edit"] is False
    actions = [x["action"] for x in superadmin.get("/api/admin/audit").json()]
    assert actions.count("regras.alteradas") == 2


def test_regra_nao_pode_comecar_em_mes_fechado(superadmin):
    company, _ = new_company(superadmin, "Regras Fechado")
    open_company(superadmin, company)
    emp = add_employee(superadmin, "Lia", "343434")
    closure = {"month": "2026-03", "employee_id": emp}
    assert superadmin.post("/api/admin/closures", json=closure, headers=ORIGIN).status_code == 200
    response = superadmin.post("/api/admin/rules", json=rule("2026-03-15", tolerance_minutes=0), headers=ORIGIN)
    assert response.status_code == 400 and "03/2026" in response.json()["error"]
    assert superadmin.post("/api/admin/rules", json=rule("2026-04-01", tolerance_minutes=0), headers=ORIGIN).status_code == 201


def test_regras_invalidas_sao_recusadas(superadmin):
    company, _ = new_company(superadmin, "Regras Invalidas")
    open_company(superadmin, company)
    for bad in (
        rule("2026-05-01", tolerance_minutes=90),
        rule("2026-05-01", night_start_hour=22, night_end_hour=22),
        rule("2026-05-01", night_hour_minutes=20),
        rule("2026-05-01", max_shift_hours=30),
        rule("1990-01-01"),
    ):
        assert superadmin.post("/api/admin/rules", json=bad, headers=ORIGIN).status_code == 400, bad


def test_fuso_da_empresa_define_o_dia(superadmin):
    company, _ = new_company(superadmin, "Fuso Manaus")
    open_company(superadmin, company)
    settings = {"timezone": "America/Manaus", "offline_max_hours": 12}
    assert superadmin.patch("/api/admin/rules/settings", json=settings, headers=ORIGIN).status_code == 200
    assert superadmin.get("/api/admin/rules").json()["timezone"] == "America/Manaus"
    emp = add_employee(superadmin, "Iara", "565656")
    # 00:30 de 03/03 em Brasília é 23:30 de 02/03 em Manaus: a batida conta no dia 02
    add_punch(superadmin, emp, "2026-03-03T00:30:00-03:00", "entrada")
    report = superadmin.get(f"/api/admin/report?employee={emp}&month=2026-03").json()
    assert len(day(report, "2026-03-02")["punches"]) == 1
    assert day(report, "2026-03-03")["punches"] == []
    # Com batidas registradas, o fuso não muda mais (mudaria o dia de cada batida)
    response = superadmin.patch("/api/admin/rules/settings", json={"timezone": "America/Sao_Paulo"}, headers=ORIGIN)
    assert response.status_code == 400
    bad_tz = superadmin.patch("/api/admin/rules/settings", json={"timezone": "Lua/Base"}, headers=ORIGIN)
    assert bad_tz.status_code == 400


def test_extras_pagas_pela_regra(superadmin):
    company, adm = new_company(superadmin, "Regras Extras")
    open_company(superadmin, company)
    emp = add_employee(superadmin, "Nei", "454545")
    add_punch(superadmin, emp, "2026-03-02T08:00:00-03:00", "entrada")
    add_punch(superadmin, emp, "2026-03-02T18:00:00-03:00", "saida")  # 10h: 2h a mais
    pay = rule("2026-03-01", overtime_mode="pagar", overtime_pct=60, rest_overtime_pct=100)
    assert superadmin.post("/api/admin/rules", json=pay, headers=ORIGIN).status_code == 201
    r = superadmin.get(f"/api/admin/report?employee={emp}&month=2026-03").json()
    assert day(r, "2026-03-02")["extraMs"] == 2 * HOUR and r["extraMs"] == 2 * HOUR
    assert r["balanceMs"] == 0  # nada vai para o banco
    csv = superadmin.get(f"/api/admin/report?employee={emp}&month=2026-03&format=csv").text
    assert "extras pagas: 60% no dia comum e 100% em domingo e feriado" in csv
    bad = rule("2026-04-01", overtime_mode="pagar", overtime_pct=40)
    assert superadmin.post("/api/admin/rules", json=bad, headers=ORIGIN).status_code == 400
    periods = login(adm).get("/api/admin/rules").json()["periods"]
    assert periods[-1]["overtime_mode"] == "pagar" and periods[-1]["overtime_pct"] == 60
