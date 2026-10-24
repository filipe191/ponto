from datetime import datetime

from app.core.config import settings
from app.models import Employee, Punch


def at(text: str) -> datetime:
    """'2026-03-02 08:00' no fuso configurado."""
    return datetime.fromisoformat(text).replace(tzinfo=settings.timezone)


def punches(*items: tuple[str, str]) -> list[Punch]:
    return [Punch(id=i, ts=at(ts), type=kind, manual=False) for i, (kind, ts) in enumerate(items, 1)]


def employee(daily_minutes: int = 480, workdays: str = "12345") -> Employee:
    return Employee(id=1, name="Ana", daily_minutes=daily_minutes, workdays=workdays, created_at=at("2026-01-01 00:00"))
