"""Limites de dia e mês no fuso da empresa (sem `tz`, o fuso padrão do .env)."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings


def _tz(tz: ZoneInfo | None) -> ZoneInfo:
    return tz or settings.timezone


def now_local(tz: ZoneInfo | None = None) -> datetime:
    return datetime.now(_tz(tz))


def to_local(ts: datetime, tz: ZoneInfo | None = None) -> datetime:
    return ts.astimezone(_tz(tz))


def with_tz(ts: datetime, tz: ZoneInfo | None = None) -> datetime:
    """Horário sem fuso (vindo de um formulário ou do celular) é entendido no fuso da empresa."""
    return ts if ts.tzinfo else ts.replace(tzinfo=_tz(tz))


def local_at(d: date, hour: int = 0, tz: ZoneInfo | None = None) -> datetime:
    return datetime(d.year, d.month, d.day, hour, tzinfo=_tz(tz))


def day_bounds(d: date, tz: ZoneInfo | None = None) -> tuple[datetime, datetime]:
    start = local_at(d, tz=tz)
    return start, start + timedelta(days=1)


def month_bounds(year: int, month: int, tz: ZoneInfo | None = None) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=_tz(tz))
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=_tz(tz))
    return start, end


def month_of(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def parse_month(month: str) -> tuple[int, int]:
    year, mon = map(int, month.split("-"))
    return year, mon


def night_time(
    start: datetime,
    end: datetime,
    begin: int | None = None,
    finish: int | None = None,
    tz: ZoneInfo | None = None,
) -> timedelta:
    """Quanto do intervalo [start, end) cai no horário noturno (`begin`h–`finish`h; 22h–5h por padrão)."""
    total = timedelta(0)
    begin = settings.night_start_hour if begin is None else begin
    finish = settings.night_end_hour if finish is None else finish
    day = to_local(start, tz).date() - timedelta(days=1)
    while local_at(day, begin, tz) < end:
        window_start = local_at(day, begin, tz)
        window_end = local_at(day + timedelta(days=1 if finish <= begin else 0), finish, tz)
        overlap = min(end, window_end) - max(start, window_start)
        if overlap > timedelta(0):
            total += overlap
        day += timedelta(days=1)
    return total
