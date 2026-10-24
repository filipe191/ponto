from datetime import date, datetime

from app.core.config import settings
from app.models import Employee, EmployeeSchedule, Punch


def at(text: str) -> datetime:
    """'2026-03-02 08:00' no fuso configurado."""
    return datetime.fromisoformat(text).replace(tzinfo=settings.timezone)


def punches(*items: tuple[str, str]) -> list[Punch]:
    return [Punch(id=i, employee_id=1, ts=at(ts), type=kind, manual=False, offline=False, source="relogio") for i, (kind, ts) in enumerate(items, 1)]


def employee(
    daily_minutes: int = 480,
    workdays: str = "12345",
    hired_on: date = date(2026, 1, 1),
    terminated_on: date | None = None,
    schedules: list[tuple[date, int, str]] | None = None,
) -> Employee:
    emp = Employee(id=1, name="Ana", hired_on=hired_on, terminated_on=terminated_on, created_at=at("2026-01-01 00:00"))
    for valid_from, minutes, days in schedules or [(hired_on, daily_minutes, workdays)]:
        emp.schedules.append(EmployeeSchedule(valid_from=valid_from, daily_minutes=minutes, workdays=days))
    return emp
