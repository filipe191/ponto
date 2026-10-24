"""Auditoria do sistema e mais de um superadministrador."""

from tests.integration.conftest import ORIGIN, PASSWORD, login, new_company, open_company, set_password


def test_conta_do_superadmin_fica_na_auditoria_do_sistema(superadmin):
    system = superadmin.get("/api/companies/audit").json()
    assert any(x["action"] == "admin.login" and x["user"] == "admin" for x in system)
    # A empresa nº 1 (a "do" superadmin) não vê os logins dele
    open_company(superadmin, 1)
    company_actions = [(x["action"], x["user"]) for x in superadmin.get("/api/admin/audit").json()]
    assert ("admin.login", "admin") not in company_actions


def test_cadastro_de_empresa_aparece_nas_duas_auditorias(superadmin):
    company, adm = new_company(superadmin, "Auditada")
    assert superadmin.patch(f"/api/companies/{company}", json={"name": "Auditada Ltda"}, headers=ORIGIN).status_code == 200
    system = [x["summary"] for x in superadmin.get("/api/companies/audit").json()]
    assert "Cadastrou a empresa Auditada" in system
    assert any(s.startswith("Auditada Ltda: Alterou a empresa") for s in system)
    company_actions = [x["action"] for x in login(adm).get("/api/admin/audit").json()]
    assert {"empresa.criada", "empresa.alterada"} <= set(company_actions)


def test_segundo_superadmin(superadmin):
    response = superadmin.post("/api/companies/superadmins", json={"username": "sa2", "password": PASSWORD}, headers=ORIGIN)
    assert response.status_code == 201, response.text
    names = [x["username"] for x in superadmin.get("/api/companies/superadmins").json()]
    assert names == ["admin", "sa2"]
    weak = superadmin.post("/api/companies/superadmins", json={"username": "sa3", "password": "123"}, headers=ORIGIN)
    assert weak.status_code == 400

    set_password("sa2")
    sa2 = login("sa2")
    assert sa2.get("/api/auth/admin").json()["superadmin"] is True
    assert sa2.get("/api/companies").status_code == 200

    ids = {x["username"]: x["id"] for x in superadmin.get("/api/companies/superadmins").json()}
    assert superadmin.delete(f"/api/companies/superadmins/{ids['admin']}", headers=ORIGIN).status_code == 400  # a própria
    assert superadmin.delete(f"/api/companies/superadmins/{ids['sa2']}", headers=ORIGIN).status_code == 200
    assert sa2.get("/api/companies").status_code == 401  # a sessão cai junto com a conta
    actions = [x["action"] for x in superadmin.get("/api/companies/audit").json()]
    assert {"superadmin.criado", "superadmin.excluido"} <= set(actions)


def test_superadmin_nao_e_excluido_pelo_painel_da_empresa(superadmin):
    company, adm = new_company(superadmin, "Painel Comum")
    client = login(adm)
    ids = [x["id"] for x in superadmin.get("/api/companies/superadmins").json()]
    assert all(client.delete(f"/api/admin/admins/{i}", headers=ORIGIN).status_code == 404 for i in ids)
