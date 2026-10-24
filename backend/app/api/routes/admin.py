"""Rotas do painel de administração (exigem o login do admin)."""

from fastapi import APIRouter, Depends, Response

from app.api.deps import AdminUser, DbSession, require_admin
from app.schemas.common import OkResponse
from app.schemas.employee import EmployeeCreate, EmployeeCreated, EmployeeOut, EmployeeUpdate
from app.schemas.punch import ManualPunchCreate, PunchChangeOut, PunchUpdate
from app.schemas.report import MonthReport
from app.services.employee_service import EmployeeService
from app.services.punch_service import PunchService
from app.services.report_service import ReportService

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


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


# ---------- Relatório ----------


@router.get("/report", response_model=MonthReport)
def report(db: DbSession, employee: int = 0, month: str = "", format: str = "json"):
    service = ReportService(db)
    result = service.monthly(employee, month)
    if format == "csv":
        return Response(
            service.to_csv(result),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{service.csv_filename(result)}"'},
        )
    return result
