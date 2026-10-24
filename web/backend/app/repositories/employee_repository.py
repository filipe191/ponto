from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Employee


class EmployeeRepository:
    """Funcionários de uma empresa: nada aqui enxerga os de outra."""

    def __init__(self, db: Session, company_id: int):
        self.db = db
        self.company_id = company_id

    def get(self, employee_id: int) -> Employee | None:
        employee = self.db.get(Employee, employee_id)
        return employee if employee and employee.company_id == self.company_id else None

    def get_by_pin_hash(self, pin_hash: str, lock: bool = False) -> Employee | None:
        """Com lock=True trava a linha até o commit (serializa batidas do mesmo funcionário)."""
        query = select(Employee).where(Employee.company_id == self.company_id, Employee.pin_hash == pin_hash)
        return self.db.scalar(query.with_for_update() if lock else query)

    def list(self) -> list[Employee]:
        return list(
            self.db.scalars(select(Employee).where(Employee.company_id == self.company_id).order_by(Employee.name))
        )

    def add(self, employee: Employee) -> Employee:
        employee.company_id = self.company_id
        self.db.add(employee)
        self.db.flush()
        return employee

    def delete(self, employee: Employee) -> None:
        self.db.delete(employee)
