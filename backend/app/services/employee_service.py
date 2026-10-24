from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound
from app.core.security import hash_pin
from app.models import Employee
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.punch_repository import PunchRepository
from app.schemas.employee import EmployeeCreate, EmployeeUpdate

PIN_IN_USE = "Este PIN já está em uso"


class EmployeeService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = EmployeeRepository(db)
        self.punches = PunchRepository(db)

    def list(self) -> list[Employee]:
        return self.repo.list()

    def create(self, data: EmployeeCreate) -> Employee:
        employee = Employee(
            name=data.name,
            pin_hash=hash_pin(data.pin),
            daily_minutes=data.daily_minutes,
            workdays=data.workdays,
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
        if data.daily_minutes is not None:
            employee.daily_minutes = data.daily_minutes
        if data.workdays is not None:
            employee.workdays = data.workdays
        self._commit()

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
