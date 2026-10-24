"""Rotas do painel de administração (exigem o login de um administrador)."""

from datetime import date

from fastapi import APIRouter, Depends, Response

from app.api.deps import AdminUser, DbSession, require_admin
from app.schemas.admin import AdminCreate, AdminOut, ClosureRequest, HolidayCreate, HolidayOut
from app.schemas.common import OkResponse
from app.schemas.employee import EmployeeCreate, EmployeeCreated, EmployeeOut, EmployeeUpdate
from app.schemas.punch import ManualPunchCreate, PunchChangeOut, PunchUpdate
from app.schemas.report import MonthReport, SummaryRow
from app.services.auth_service import AuthService
from app.services.calendar_service import ClosureService, HolidayService
from app.services.employee_service import EmployeeService
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
def create_employee(body: EmployeeCreate, db: DbSession):
    return EmployeeService(db).create(body)


@router.patch("/employees/{employee_id}", response_model=OkResponse)
def update_employee(employee_id: int, body: EmployeeUpdate, db: DbSession):
    EmployeeService(db).update(employee_id, body)
    return OkResponse()


@router.delete("/employees/{employee_id}", response_model=OkResponse)
def delete_employee(employee_id: int, db: DbSession):
    EmployeeService(db).delete(employee_id)
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
def reopen_month(employee_id: int, month: str, db: DbSession):
    ClosureService(db).reopen(employee_id, month)
    return OkResponse()


# ---------- Feriados ----------


@router.get("/holidays", response_model=list[HolidayOut])
def list_holidays(db: DbSession, year: int):
    return HolidayService(db).list(year)


@router.post("/holidays", response_model=OkResponse, status_code=201)
def add_holiday(body: HolidayCreate, db: DbSession):
    HolidayService(db).add(body)
    return OkResponse()


@router.delete("/holidays/{day}", response_model=OkResponse)
def delete_holiday(day: date, db: DbSession):
    HolidayService(db).delete(day)
    return OkResponse()


# ---------- Administradores e relógios ----------


@router.get("/admins", response_model=list[AdminOut])
def list_admins(db: DbSession):
    return AuthService(db).list_admins()


@router.post("/admins", response_model=OkResponse, status_code=201)
def create_admin(body: AdminCreate, db: DbSession):
    AuthService(db).create_admin(body.username, body.password)
    return OkResponse()


@router.delete("/admins/{admin_id}", response_model=OkResponse)
def delete_admin(admin_id: int, db: DbSession, user: AdminUser):
    AuthService(db).delete_admin(admin_id, user)
    return OkResponse()


@router.post("/kiosks/reset", response_model=OkResponse)
def reset_kiosks(db: DbSession):
    """Desliga todos os aparelhos liberados como relógio (ex.: tablet perdido)."""
    AuthService(db).reset_kiosks()
    return OkResponse()
