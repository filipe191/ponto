from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Conflict, NotFound
from app.core.security import hash_pin
from app.models import Employee, EmployeeSchedule
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.punch_repository import PunchRepository
from app.schemas.employee import EmployeeCreate, EmployeeUpdate
from app.utils.dates import now_local

PIN_IN_USE = "Este PIN já está em uso"


class EmployeeService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = EmployeeRepository(db)
        self.punches = PunchRepository(db)

    def list(self) -> list[Employee]:
        return self.repo.list()

    def create(self, data: EmployeeCreate) -> Employee:
        hired_on = data.hired_on or now_local().date()
        employee = Employee(name=data.name, pin_hash=hash_pin(data.pin), hired_on=hired_on)
        employee.schedules.append(
            EmployeeSchedule(valid_from=hired_on, daily_minutes=data.daily_minutes, workdays=data.workdays)
        )
        self._commit(lambda: self.repo.add(employee))
        return employee

    def update(self, employee_id: int, data: EmployeeUpdate) -> None:
        employee = self._get(employee_id)
        if data.name is not None:
            employee.name = data.name
        if data.active is not None:
            employee.active = data.active
        if data.pin is not None:
            employee.pin_hash = hash_pin(data.pin)
        if data.hired_on is not None:
            employee.hired_on = data.hired_on
        if "terminated_on" in data.model_fields_set:
            employee.terminated_on = data.terminated_on
        if employee.terminated_on and employee.terminated_on < employee.hired_on:
            raise BadRequest("O desligamento não pode ser antes da admissão")
        if data.daily_minutes is not None or data.workdays is not None:
            self._set_schedule(employee, data)
        self._commit()

    def _set_schedule(self, employee: Employee, data: EmployeeUpdate) -> None:
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

    def delete(self, employee_id: int) -> None:
        """Só para cadastros feitos por engano: quem já tem registros de ponto é desativado, não excluído."""
        employee = self._get(employee_id)
        if self.punches.has_any(employee.id):
            raise Conflict("Este funcionário tem registros de ponto e não pode ser excluído. Desative-o.")
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
