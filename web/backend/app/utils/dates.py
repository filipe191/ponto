"""Limites de dia e mês no fuso configurado."""

from datetime import date, datetime, timedelta

from app.core.config import settings


def now_local() -> datetime:
    return datetime.now(settings.timezone)


def to_local(ts: datetime) -> datetime:
    return ts.astimezone(settings.timezone)


def local_at(d: date, hour: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, hour, tzinfo=settings.timezone)


def day_bounds(d: date) -> tuple[datetime, datetime]:
    start = local_at(d)
    return start, start + timedelta(days=1)


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=settings.timezone)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=settings.timezone)
    return start, end


def month_of(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def parse_month(month: str) -> tuple[int, int]:
    year, mon = map(int, month.split("-"))
    return year, mon


def night_time(start: datetime, end: datetime) -> timedelta:
    """Quanto do intervalo [start, end) cai no horário noturno (22h–5h por padrão)."""
    total = timedelta(0)
    begin, finish = settings.night_start_hour, settings.night_end_hour
    day = to_local(start).date() - timedelta(days=1)
    while local_at(day, begin) < end:
        window_start = local_at(day, begin)
        window_end = local_at(day + timedelta(days=1 if finish <= begin else 0), finish)
        overlap = min(end, window_end) - max(start, window_start)
        if overlap > timedelta(0):
            total += overlap
        day += timedelta(days=1)
    return total
