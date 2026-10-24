from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Employee


class EmployeeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, employee_id: int) -> Employee | None:
        return self.db.get(Employee, employee_id)

    def get_by_pin_hash(self, pin_hash: str, lock: bool = False) -> Employee | None:
        """Com lock=True trava a linha até o commit (serializa batidas do mesmo funcionário)."""
        query = select(Employee).where(Employee.pin_hash == pin_hash)
        return self.db.scalar(query.with_for_update() if lock else query)

    def list(self) -> list[Employee]:
        return list(self.db.scalars(select(Employee).order_by(Employee.name)))

    def add(self, employee: Employee) -> Employee:
        self.db.add(employee)
        self.db.flush()
        return employee

    def delete(self, employee: Employee) -> None:
        self.db.delete(employee)
