"""Rotas do painel de administração (exigem o login de um administrador)."""

from datetime import date

from fastapi import APIRouter, Depends, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.api.deps import CompanyAdmin, CurrentAccess, DbSession, SuperCompany, require_admin
from app.schemas.admin import (
    AdminCreate,
    AdminOut,
    Alerts,
    AuditOut,
    ClosureRequest,
    DeviceCreate,
    DeviceCreated,
    DeviceOut,
    HolidayCreate,
    HolidayOut,
    RequestDecision,
    RequestOut,
    RulePeriodIn,
    RulesOut,
    RulesSettingsIn,
)
from app.schemas.common import OkResponse
from app.schemas.employee import EmployeeCreate, EmployeeCreated, EmployeeOut, EmployeeUpdate
from app.schemas.punch import ManualPunchCreate, PunchChangeOut, PunchUpdate
from app.schemas.report import MonthReport, SummaryRow
from app.services.audit import PIN_BLOCKED, AuditLog
from app.services.auth_service import AuthService
from app.services.calendar_service import ClosureService, HolidayService
from app.services.employee_service import EmployeeService
from app.services.mobile_service import DeviceService, RequestService
from app.services.punch_service import PunchService
from app.services.report_service import ReportService
from app.services.rules import RulePeriod, RulesService

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _csv(content: str, filename: str) -> Response:
    return Response(
        content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- Funcionários ----------


@router.get("/employees", response_model=list[EmployeeOut])
def list_employees(db: DbSession, t: CompanyAdmin):
    return EmployeeService(db, t.company_id).list()


@router.post("/employees", response_model=EmployeeCreated, status_code=201)
def create_employee(body: EmployeeCreate, db: DbSession, t: CompanyAdmin):
    return EmployeeService(db, t.company_id).create(body, t.user)


@router.patch("/employees/{employee_id}", response_model=OkResponse)
def update_employee(employee_id: int, body: EmployeeUpdate, db: DbSession, t: CompanyAdmin):
    EmployeeService(db, t.company_id).update(employee_id, body, t.user)
    return OkResponse()


@router.get("/employees/{employee_id}/export")
def export_employee(employee_id: int, db: DbSession, t: CompanyAdmin):
    """LGPD: tudo o que o sistema guarda sobre o funcionário, em JSON (pedido de acesso aos dados)."""
    data = EmployeeService(db, t.company_id).export(employee_id, t.user)
    return JSONResponse(
        jsonable_encoder(data),
        headers={"Content-Disposition": f'attachment; filename="dados-funcionario-{employee_id}.json"'},
    )


@router.post("/employees/{employee_id}/anonymize", response_model=OkResponse)
def anonymize_employee(employee_id: int, db: DbSession, t: CompanyAdmin):
    """LGPD: apaga os dados pessoais de quem saiu há mais que o prazo de guarda."""
    EmployeeService(db, t.company_id).anonymize(employee_id, t.user)
    return OkResponse()


@router.delete("/employees/{employee_id}", response_model=OkResponse)
def delete_employee(employee_id: int, db: DbSession, t: CompanyAdmin):
    EmployeeService(db, t.company_id).delete(employee_id, t.user)
    return OkResponse()


# ---------- Batidas (toda correção fica no histórico) ----------


@router.post("/punches", response_model=OkResponse, status_code=201)
def create_manual_punch(body: ManualPunchCreate, db: DbSession, t: CompanyAdmin):
    PunchService(db, t.company_id).add_manual(body, t.user)
    return OkResponse()


@router.patch("/punches/{punch_id}", response_model=OkResponse)
def update_punch(punch_id: int, body: PunchUpdate, db: DbSession, t: CompanyAdmin):
    PunchService(db, t.company_id).update(punch_id, body, t.user)
    return OkResponse()


@router.delete("/punches/{punch_id}", response_model=OkResponse)
def delete_punch(punch_id: int, db: DbSession, t: CompanyAdmin, note: str = ""):
    PunchService(db, t.company_id).delete(punch_id, t.user, note)
    return OkResponse()


@router.post("/punches/{punch_id}/restore", response_model=OkResponse)
def restore_punch(punch_id: int, db: DbSession, t: CompanyAdmin):
    PunchService(db, t.company_id).restore(punch_id, t.user)
    return OkResponse()


@router.get("/punches/{punch_id}/history", response_model=list[PunchChangeOut])
def punch_history(punch_id: int, db: DbSession, t: CompanyAdmin):
    return PunchService(db, t.company_id).history(punch_id)


# ---------- Relatórios ----------


@router.get("/report", response_model=MonthReport)
def report(db: DbSession, t: CompanyAdmin, employee: int = 0, month: str = "", format: str = "json"):
    service = ReportService(db, t.company_id)
    result = service.monthly(employee, month)
    if format == "csv":
        return _csv(service.to_csv(result), service.csv_filename(result))
    return result


@router.get("/summary", response_model=list[SummaryRow])
def summary(db: DbSession, t: CompanyAdmin, month: str = "", format: str = "json"):
    """Resumo do mês de todos os funcionários (para a contabilidade)."""
    service = ReportService(db, t.company_id)
    rows = service.summary(month)
    if format == "csv":
        return _csv(service.summary_csv(month, rows), f"ponto-resumo-{month}.csv")
    return rows


# ---------- Fechamento do mês ----------


@router.post("/closures", response_model=OkResponse)
def close_month(body: ClosureRequest, db: DbSession, t: CompanyAdmin):
    ClosureService(db, t.company_id).close(body.month, body.employee_id, t.user)
    return OkResponse()


@router.delete("/closures/{employee_id}/{month}", response_model=OkResponse)
def reopen_month(employee_id: int, month: str, db: DbSession, t: CompanyAdmin, note: str = ""):
    """O motivo é obrigatório; o fechamento e a ciência anteriores ficam na auditoria."""
    ClosureService(db, t.company_id).reopen(employee_id, month, t.user, note)
    return OkResponse()


# ---------- Feriados ----------


@router.get("/holidays", response_model=list[HolidayOut])
def list_holidays(db: DbSession, t: CompanyAdmin, year: int):
    return HolidayService(db, t.company_id).list(year)


@router.post("/holidays", response_model=OkResponse, status_code=201)
def add_holiday(body: HolidayCreate, db: DbSession, t: CompanyAdmin):
    HolidayService(db, t.company_id).add(body, t.user)
    return OkResponse()


@router.delete("/holidays/{day}", response_model=OkResponse)
def delete_holiday(day: date, db: DbSession, t: CompanyAdmin):
    HolidayService(db, t.company_id).delete(day, t.user)
    return OkResponse()


# ---------- Regras de jornada (o superadmin altera; os admins da empresa consultam) ----------


@router.get("/rules", response_model=RulesOut)
def rules(db: DbSession, t: CompanyAdmin, access: CurrentAccess):
    service = RulesService(db, t.company_id)
    company = service.company()
    return RulesOut(
        timezone=company.timezone,
        offline_max_hours=company.offline_max_hours,
        periods=service.periods(),
        can_edit=access.account.superadmin,
    )


@router.post("/rules", response_model=OkResponse, status_code=201)
def add_rules(body: RulePeriodIn, db: DbSession, t: SuperCompany):
    """Novas regras a partir de uma data; o passado e o banco de horas acumulado não mudam."""
    RulesService(db, t.company_id).add_period(RulePeriod(**body.model_dump()), t.user)
    return OkResponse()


@router.patch("/rules/settings", response_model=OkResponse)
def update_rules_settings(body: RulesSettingsIn, db: DbSession, t: SuperCompany):
    RulesService(db, t.company_id).update_settings(t.user, body.timezone, body.offline_max_hours)
    return OkResponse()


# ---------- App de celular: chaves e solicitações ----------


@router.get("/employees/{employee_id}/devices", response_model=list[DeviceOut])
def list_devices(employee_id: int, db: DbSession, t: CompanyAdmin):
    return DeviceService(db, t.company_id).list(employee_id)


@router.post("/employees/{employee_id}/devices", response_model=DeviceCreated, status_code=201)
def create_device(employee_id: int, body: DeviceCreate, db: DbSession, t: CompanyAdmin):
    """Gera a chave de acesso do app. Ela só aparece nesta resposta."""
    return DeviceService(db, t.company_id).create(employee_id, body.name, t.user)


@router.delete("/devices/{device_id}", response_model=OkResponse)
def revoke_device(device_id: int, db: DbSession, t: CompanyAdmin):
    DeviceService(db, t.company_id).revoke(device_id, t.user)
    return OkResponse()


@router.get("/requests", response_model=list[RequestOut])
def list_requests(db: DbSession, t: CompanyAdmin, status: str = "pendente"):
    return RequestService(db, t.company_id).list(status)


@router.post("/requests/{request_id}/approve", response_model=OkResponse)
def approve_request(request_id: int, body: RequestDecision, db: DbSession, t: CompanyAdmin):
    RequestService(db, t.company_id).approve(request_id, t.user, body.note)
    return OkResponse()


@router.post("/requests/{request_id}/reject", response_model=OkResponse)
def reject_request(request_id: int, body: RequestDecision, db: DbSession, t: CompanyAdmin):
    RequestService(db, t.company_id).reject(request_id, t.user, body.note)
    return OkResponse()


# ---------- Administradores e relógios ----------


@router.get("/admins", response_model=list[AdminOut])
def list_admins(db: DbSession, t: CompanyAdmin):
    return AuthService(db).list_admins(t.company_id)


@router.post("/admins", response_model=OkResponse, status_code=201)
def create_admin(body: AdminCreate, db: DbSession, t: CompanyAdmin):
    AuthService(db).create_admin(t.company_id, body.username, body.password, t.user)
    return OkResponse()


@router.delete("/admins/{admin_id}", response_model=OkResponse)
def delete_admin(admin_id: int, db: DbSession, t: CompanyAdmin):
    AuthService(db).delete_admin(t.company_id, admin_id, t.user)
    return OkResponse()


@router.post("/kiosks/reset", response_model=OkResponse)
def reset_kiosks(db: DbSession, t: CompanyAdmin):
    """Desliga todos os aparelhos liberados como relógio (ex.: tablet perdido)."""
    AuthService(db).reset_kiosks(t.company_id, t.user)
    return OkResponse()


# ---------- Auditoria e alertas ----------


@router.get("/audit", response_model=list[AuditOut])
def audit(db: DbSession, t: CompanyAdmin, employee: int = 0, action: str = "", before: int = 0, limit: int = 50):
    """Mais recentes primeiro; `before` (id) pagina para trás."""
    return AuditLog(db, t.company_id).list(employee or None, action, before or None, limit)


@router.get("/alerts", response_model=Alerts)
def alerts(db: DbSession, t: CompanyAdmin):
    """Avisos do topo do painel: bloqueios do relógio, PINs curtos, chaves vencendo e prazo de guarda."""
    employees = EmployeeService(db, t.company_id).list()
    return Alerts(
        pin_blocks=AuditLog(db, t.company_id).recent(PIN_BLOCKED, hours=24),
        short_pins=sum(e.pin_short and e.active for e in employees),
        devices_expiring=DeviceService(db, t.company_id).expiring(),
        retention_due=sum(e.retention_due for e in employees),
    )
