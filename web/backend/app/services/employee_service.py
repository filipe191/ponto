from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Conflict, NotFound
from app.core.security import hash_pin
from app.models import Employee, EmployeeSchedule
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.punch_repository import PunchRepository
from app.schemas.employee import EmployeeCreate, EmployeeUpdate
from app.services.audit import AuditLog
from app.utils.dates import now_local

PIN_IN_USE = "Este PIN já está em uso"

_WEEK = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
_FIELDS = {"name": "nome", "hired_on": "admissão", "terminated_on": "desligamento"}


def schedule_label(minutes: int, workdays: str) -> str:
    """Ex.: "8h00 · seg, ter, qua, qui, sex"."""
    days = ", ".join(_WEEK[int(d) - 1] for d in workdays) or "sem dias de trabalho"
    return f"{minutes // 60}h{minutes % 60:02d} · {days}"


class EmployeeService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = EmployeeRepository(db)
        self.punches = PunchRepository(db)
        self.audit = AuditLog(db)

    def list(self) -> list[Employee]:
        return self.repo.list()

    def create(self, data: EmployeeCreate, user: str) -> Employee:
        hired_on = data.hired_on or now_local().date()
        employee = Employee(name=data.name, pin_hash=hash_pin(data.pin), hired_on=hired_on)
        employee.schedules.append(
            EmployeeSchedule(valid_from=hired_on, daily_minutes=data.daily_minutes, workdays=data.workdays)
        )

        def add():
            self.repo.add(employee)
            self.db.flush()
            self.audit.record(
                user,
                "funcionario.criado",
                f"Cadastrou {employee.name} (admissão {hired_on:%d/%m/%Y}, "
                f"jornada {schedule_label(data.daily_minutes, data.workdays)})",
                employee_id=employee.id,
                details={"hired_on": hired_on, "daily_minutes": data.daily_minutes, "workdays": data.workdays},
            )

        self._commit(add)
        return employee

    def update(self, employee_id: int, data: EmployeeUpdate, user: str) -> None:
        employee = self._get(employee_id)
        before = {field: getattr(employee, field) for field in _FIELDS}
        name_before = employee.name

        if data.name is not None:
            employee.name = data.name
        if data.hired_on is not None:
            employee.hired_on = data.hired_on
        if "terminated_on" in data.model_fields_set:
            employee.terminated_on = data.terminated_on
        if employee.terminated_on and employee.terminated_on < employee.hired_on:
            raise BadRequest("O desligamento não pode ser antes da admissão")

        changes = {f: [before[f], getattr(employee, f)] for f in _FIELDS if before[f] != getattr(employee, f)}
        if changes:
            self.audit.record(
                user,
                "funcionario.alterado",
                f"Alterou o cadastro de {name_before}: "
                + "; ".join(f"{_FIELDS[f]} {_show(old)} → {_show(new)}" for f, (old, new) in changes.items()),
                employee_id=employee.id,
                details={"changes": changes},
            )
        if data.active is not None and data.active != employee.active:
            employee.active = data.active
            self.audit.record(
                user,
                "funcionario.ativado" if data.active else "funcionario.desativado",
                f"{'Ativou' if data.active else 'Desativou'} {employee.name}",
                employee_id=employee.id,
            )
        if data.pin is not None:
            employee.pin_hash = hash_pin(data.pin)
            employee.pin_short = False
            # O PIN em si nunca vai para a auditoria
            self.audit.record(user, "funcionario.pin_trocado", f"Trocou o PIN de {employee.name}", employee_id=employee.id)
        if data.daily_minutes is not None or data.workdays is not None:
            self._set_schedule(employee, data, user)
        self._commit()

    def _set_schedule(self, employee: Employee, data: EmployeeUpdate, user: str) -> None:
        """Nova jornada a partir de `schedule_from`; a anterior continua valendo antes dessa data."""
        start = data.schedule_from or now_local().date()
        current = employee.schedule_on(start)
        minutes = data.daily_minutes if data.daily_minutes is not None else (current.daily_minutes if current else 480)
        workdays = data.workdays if data.workdays is not None else (current.workdays if current else "12345")
        if current and current.daily_minutes == minutes and current.workdays == workdays:
            return
        same_day = next((s for s in employee.schedules if s.valid_from == start), None)
        if same_day:
            same_day.daily_minutes, same_day.workdays = minutes, workdays
        else:
            employee.schedules.append(EmployeeSchedule(valid_from=start, daily_minutes=minutes, workdays=workdays))
            employee.schedules.sort(key=lambda s: s.valid_from)
        old = schedule_label(current.daily_minutes, current.workdays) if current else "—"
        self.audit.record(
            user,
            "jornada.alterada",
            f"Mudou a jornada de {employee.name} a partir de {start:%d/%m/%Y}: "
            f"{old} → {schedule_label(minutes, workdays)}",
            employee_id=employee.id,
            details={
                "valid_from": start,
                "old": {"daily_minutes": current.daily_minutes, "workdays": current.workdays} if current else None,
                "new": {"daily_minutes": minutes, "workdays": workdays},
            },
        )

    def delete(self, employee_id: int, user: str) -> None:
        """Só para cadastros feitos por engano: quem já tem registros de ponto é desativado, não excluído."""
        employee = self._get(employee_id)
        if self.punches.has_any(employee.id):
            raise Conflict("Este funcionário tem registros de ponto e não pode ser excluído. Desative-o.")
        self.audit.record(
            user, "funcionario.excluido", f"Excluiu o cadastro de {employee.name}", employee_id=employee.id
        )
        self.repo.delete(employee)
        self.db.commit()

    def _get(self, employee_id: int) -> Employee:
        employee = self.repo.get(employee_id)
        if not employee:
            raise NotFound("Funcionário não encontrado")
        return employee

    def _commit(self, action=None) -> None:
        try:
            if action:
                action()
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise Conflict(PIN_IN_USE)


def _show(value) -> str:
    if value is None:
        return "—"
    return f"{value:%d/%m/%Y}" if hasattr(value, "strftime") else str(value)
