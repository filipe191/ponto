"""Ausências justificadas (atestado, férias, licença, falta abonada, folga do banco de horas).

Mudam o saldo de dias passados, então seguem as regras das batidas: nada num mês fechado, e cada
lançamento ou remoção vai para a auditoria.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BadRequest, NotFound
from app.models import Absence, Employee
from app.repositories.employee_repository import EmployeeRepository
from app.schemas.absence import AbsenceIn
from app.services.audit import AuditLog
from app.services.rules import ensure_months_open


def _period(a: Absence) -> str:
    if a.first_day == a.last_day:
        return f"em {a.first_day:%d/%m/%Y}"
    return f"de {a.first_day:%d/%m/%Y} a {a.last_day:%d/%m/%Y}"


def _describe(a: Absence) -> str:
    hours = f", {a.minutes // 60}h{a.minutes % 60:02d} por dia" if a.minutes else ""
    return f"{a.label.lower()} {_period(a)}{hours}"


class AbsenceService:
    def __init__(self, db: Session, company_id: int):
        self.db = db
        self.company_id = company_id
        self.employees = EmployeeRepository(db, company_id)
        self.audit = AuditLog(db, company_id)

    def list(self, employee_id: int) -> list[Absence]:
        employee = self._employee(employee_id)
        return list(
            self.db.scalars(
                select(Absence).where(Absence.employee_id == employee.id).order_by(Absence.first_day.desc())
            )
        )

    def create(self, data: AbsenceIn, user: str) -> Absence:
        employee = self._employee(data.employee_id)
        if employee.anonymized_at:
            raise BadRequest("Cadastro anonimizado (LGPD) não pode ser alterado")
        if data.first_day < employee.hired_on or (employee.terminated_on and data.last_day > employee.terminated_on):
            raise BadRequest("A ausência precisa ficar dentro do período de contrato")
        overlap = self.db.scalar(
            select(Absence).where(
                Absence.employee_id == employee.id,
                Absence.first_day <= data.last_day,
                Absence.last_day >= data.first_day,
            )
        )
        if overlap:
            raise BadRequest(f"Já há {_describe(overlap)} nesse período: remova antes de lançar outra")
        ensure_months_open(self.db, self.company_id, data.first_day, "a ausência", employee.id, data.last_day)
        absence = Absence(
            employee_id=employee.id,
            kind=data.kind,
            first_day=data.first_day,
            last_day=data.last_day,
            minutes=data.minutes,
            note=data.note.strip(),
            created_by=user,
        )
        self.db.add(absence)
        self.db.flush()
        self.audit.record(
            user,
            "ausencia.lancada",
            f"Lançou {_describe(absence)} para {employee.name}" + (f" ({absence.note})" if absence.note else ""),
            employee_id=employee.id,
            details={"id": absence.id, "kind": absence.kind, "first_day": absence.first_day,
                     "last_day": absence.last_day, "minutes": absence.minutes},
        )
        self.db.commit()
        return absence

    def delete(self, absence_id: int, user: str) -> None:
        absence = self.db.get(Absence, absence_id)
        employee = self.employees.get(absence.employee_id) if absence else None
        if not absence or not employee:  # outra empresa: como se não existisse
            raise NotFound("Ausência não encontrada")
        ensure_months_open(self.db, self.company_id, absence.first_day, "a ausência", employee.id, absence.last_day)
        self.audit.record(
            user,
            "ausencia.removida",
            f"Removeu {_describe(absence)} de {employee.name}",
            employee_id=employee.id,
            details={"id": absence.id, "kind": absence.kind, "first_day": absence.first_day,
                     "last_day": absence.last_day, "minutes": absence.minutes, "note": absence.note},
        )
        self.db.delete(absence)
        self.db.commit()

    def _employee(self, employee_id: int) -> Employee:
        employee = self.employees.get(employee_id)
        if not employee:
            raise NotFound("Funcionário não encontrado")
        return employee
