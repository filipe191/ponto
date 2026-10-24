"""Limites de dia e mês no fuso configurado."""

from datetime import date, datetime, timedelta

from app.core.config import settings


def now_local() -> datetime:
    return datetime.now(settings.timezone)


def to_local(ts: datetime) -> datetime:
    return ts.astimezone(settings.timezone)


def day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime(d.year, d.month, d.day, tzinfo=settings.timezone)
    return start, start + timedelta(days=1)


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=settings.timezone)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=settings.timezone)
    return start, end
