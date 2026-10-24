"""Rotas do painel de administração (exigem o login de um administrador)."""

from datetime import date

from fastapi import APIRouter, Depends, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.api.deps import AdminUser, DbSession, require_admin
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

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _csv(content: str, filename: str) -> Response:
    return Response(
        content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- Funcionários ----------


@router.get("/employees", response_model=list[EmployeeOut])
def list_employees(db: DbSession):
    return EmployeeService(db).list()


@router.post("/employees", response_model=EmployeeCreated, status_code=201)
def create_employee(body: EmployeeCreate, db: DbSession, user: AdminUser):
    return EmployeeService(db).create(body, user)


@router.patch("/employees/{employee_id}", response_model=OkResponse)
def update_employee(employee_id: int, body: EmployeeUpdate, db: DbSession, user: AdminUser):
    EmployeeService(db).update(employee_id, body, user)
    return OkResponse()


@router.get("/employees/{employee_id}/export")
def export_employee(employee_id: int, db: DbSession, user: AdminUser):
    """LGPD: tudo o que o sistema guarda sobre o funcionário, em JSON (pedido de acesso aos dados)."""
    data = EmployeeService(db).export(employee_id, user)
    return JSONResponse(
        jsonable_encoder(data),
        headers={"Content-Disposition": f'attachment; filename="dados-funcionario-{employee_id}.json"'},
    )


@router.post("/employees/{employee_id}/anonymize", response_model=OkResponse)
def anonymize_employee(employee_id: int, db: DbSession, user: AdminUser):
    """LGPD: apaga os dados pessoais de quem saiu há mais que o prazo de guarda."""
    EmployeeService(db).anonymize(employee_id, user)
    return OkResponse()


@router.delete("/employees/{employee_id}", response_model=OkResponse)
def delete_employee(employee_id: int, db: DbSession, user: AdminUser):
    EmployeeService(db).delete(employee_id, user)
    return OkResponse()


# ---------- Batidas (toda correção fica no histórico) ----------


@router.post("/punches", response_model=OkResponse, status_code=201)
def create_manual_punch(body: ManualPunchCreate, db: DbSession, user: AdminUser):
    PunchService(db).add_manual(body, user)
    return OkResponse()


@router.patch("/punches/{punch_id}", response_model=OkResponse)
def update_punch(punch_id: int, body: PunchUpdate, db: DbSession, user: AdminUser):
    PunchService(db).update(punch_id, body, user)
    return OkResponse()


@router.delete("/punches/{punch_id}", response_model=OkResponse)
def delete_punch(punch_id: int, db: DbSession, user: AdminUser, note: str = ""):
    PunchService(db).delete(punch_id, user, note)
    return OkResponse()


@router.post("/punches/{punch_id}/restore", response_model=OkResponse)
def restore_punch(punch_id: int, db: DbSession, user: AdminUser):
    PunchService(db).restore(punch_id, user)
    return OkResponse()


@router.get("/punches/{punch_id}/history", response_model=list[PunchChangeOut])
def punch_history(punch_id: int, db: DbSession):
    return PunchService(db).history(punch_id)


# ---------- Relatórios ----------


@router.get("/report", response_model=MonthReport)
def report(db: DbSession, employee: int = 0, month: str = "", format: str = "json"):
    service = ReportService(db)
    result = service.monthly(employee, month)
    if format == "csv":
        return _csv(service.to_csv(result), service.csv_filename(result))
    return result


@router.get("/summary", response_model=list[SummaryRow])
def summary(db: DbSession, month: str = "", format: str = "json"):
    """Resumo do mês de todos os funcionários (para a contabilidade)."""
    service = ReportService(db)
    rows = service.summary(month)
    if format == "csv":
        return _csv(service.summary_csv(month, rows), f"ponto-resumo-{month}.csv")
    return rows


# ---------- Fechamento do mês ----------


@router.post("/closures", response_model=OkResponse)
def close_month(body: ClosureRequest, db: DbSession, user: AdminUser):
    ClosureService(db).close(body.month, body.employee_id, user)
    return OkResponse()


@router.delete("/closures/{employee_id}/{month}", response_model=OkResponse)
def reopen_month(employee_id: int, month: str, db: DbSession, user: AdminUser, note: str = ""):
    """O motivo é obrigatório; o fechamento e a ciência anteriores ficam na auditoria."""
    ClosureService(db).reopen(employee_id, month, user, note)
    return OkResponse()


# ---------- Feriados ----------


@router.get("/holidays", response_model=list[HolidayOut])
def list_holidays(db: DbSession, year: int):
    return HolidayService(db).list(year)


@router.post("/holidays", response_model=OkResponse, status_code=201)
def add_holiday(body: HolidayCreate, db: DbSession, user: AdminUser):
    HolidayService(db).add(body, user)
    return OkResponse()


@router.delete("/holidays/{day}", response_model=OkResponse)
def delete_holiday(day: date, db: DbSession, user: AdminUser):
    HolidayService(db).delete(day, user)
    return OkResponse()


# ---------- App de celular: chaves e solicitações ----------


@router.get("/employees/{employee_id}/devices", response_model=list[DeviceOut])
def list_devices(employee_id: int, db: DbSession):
    return DeviceService(db).list(employee_id)


@router.post("/employees/{employee_id}/devices", response_model=DeviceCreated, status_code=201)
def create_device(employee_id: int, body: DeviceCreate, db: DbSession, user: AdminUser):
    """Gera a chave de acesso do app. Ela só aparece nesta resposta."""
    return DeviceService(db).create(employee_id, body.name, user)


@router.delete("/devices/{device_id}", response_model=OkResponse)
def revoke_device(device_id: int, db: DbSession, user: AdminUser):
    DeviceService(db).revoke(device_id, user)
    return OkResponse()


@router.get("/requests", response_model=list[RequestOut])
def list_requests(db: DbSession, status: str = "pendente"):
    return RequestService(db).list(status)


@router.post("/requests/{request_id}/approve", response_model=OkResponse)
def approve_request(request_id: int, body: RequestDecision, db: DbSession, user: AdminUser):
    RequestService(db).approve(request_id, user, body.note)
    return OkResponse()


@router.post("/requests/{request_id}/reject", response_model=OkResponse)
def reject_request(request_id: int, body: RequestDecision, db: DbSession, user: AdminUser):
    RequestService(db).reject(request_id, user, body.note)
    return OkResponse()


# ---------- Administradores e relógios ----------


@router.get("/admins", response_model=list[AdminOut])
def list_admins(db: DbSession):
    return AuthService(db).list_admins()


@router.post("/admins", response_model=OkResponse, status_code=201)
def create_admin(body: AdminCreate, db: DbSession, user: AdminUser):
    AuthService(db).create_admin(body.username, body.password, user)
    return OkResponse()


@router.delete("/admins/{admin_id}", response_model=OkResponse)
def delete_admin(admin_id: int, db: DbSession, user: AdminUser):
    AuthService(db).delete_admin(admin_id, user)
    return OkResponse()


@router.post("/kiosks/reset", response_model=OkResponse)
def reset_kiosks(db: DbSession, user: AdminUser):
    """Desliga todos os aparelhos liberados como relógio (ex.: tablet perdido)."""
    AuthService(db).reset_kiosks(user)
    return OkResponse()


# ---------- Auditoria e alertas ----------


@router.get("/audit", response_model=list[AuditOut])
def audit(db: DbSession, employee: int = 0, action: str = "", before: int = 0, limit: int = 50):
    """Mais recentes primeiro; `before` (id) pagina para trás."""
    return AuditLog(db).list(employee or None, action, before or None, limit)


@router.get("/alerts", response_model=Alerts)
def alerts(db: DbSession):
    """Avisos do topo do painel: bloqueios do relógio, PINs curtos, chaves vencendo e prazo de guarda."""
    employees = EmployeeService(db).list()
    return Alerts(
        pin_blocks=AuditLog(db).recent(PIN_BLOCKED, hours=24),
        short_pins=sum(e.pin_short and e.active for e in employees),
        devices_expiring=DeviceService(db).expiring(),
        retention_due=sum(e.retention_due for e in employees),
    )
