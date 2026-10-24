from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Employee, Holiday, MonthClosure
from app.utils.holidays import national_holidays


class HolidayRepository:
    """Feriados cadastrados por uma empresa."""

    def __init__(self, db: Session, company_id: int):
        self.db = db
        self.company_id = company_id

    def custom_between(self, first: date, last: date) -> list[Holiday]:
        return list(
            self.db.scalars(
                select(Holiday)
                .where(Holiday.company_id == self.company_id, Holiday.date >= first, Holiday.date <= last)
                .order_by(Holiday.date)
            )
        )

    def all_between(self, first: date, last: date) -> dict[date, str]:
        """Feriados nacionais + cadastrados (os cadastrados têm prioridade no nome)."""
        result: dict[date, str] = {}
        for year in range(first.year, last.year + 1):
            result.update({d: n for d, n in national_holidays(year).items() if first <= d <= last})
        result.update({h.date: h.name for h in self.custom_between(first, last)})
        return result

    def get(self, day: date) -> Holiday | None:
        return self.db.get(Holiday, (self.company_id, day))

    def add(self, holiday: Holiday) -> None:
        holiday.company_id = self.company_id
        self.db.add(holiday)

    def delete(self, holiday: Holiday) -> None:
        self.db.delete(holiday)


class ClosureRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, employee_id: int, month: str) -> MonthClosure | None:
        return self.db.get(MonthClosure, (employee_id, month))

    def list_for_month(self, month: str, company_id: int) -> dict[int, MonthClosure]:
        query = (
            select(MonthClosure)
            .join(Employee, Employee.id == MonthClosure.employee_id)
            .where(MonthClosure.month == month, Employee.company_id == company_id)
        )
        return {c.employee_id: c for c in self.db.scalars(query)}

    def add(self, closure: MonthClosure) -> None:
        self.db.add(closure)

    def delete(self, closure: MonthClosure) -> None:
        self.db.delete(closure)
