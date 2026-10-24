import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BadRequest
from app.models import Employee, Punch, PunchType
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.punch_repository import PunchRepository
from app.schemas.employee import EmployeeRef
from app.schemas.punch import PunchOut
from app.schemas.report import DayReport, DayStatus, MonthReport
from app.services.shifts import Shift, pair_shifts
from app.utils.dates import month_bounds, to_local

STATUS_LABEL = {
    DayStatus.OK: "OK",
    DayStatus.INCOMPLETO: "Incompleto",
    DayStatus.FALTA: "Falta",
    DayStatus.FOLGA: "Folga",
    DayStatus.ANDAMENTO: "Em andamento",
}
WEEKDAYS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def _ms(delta: timedelta) -> int:
    return int(delta.total_seconds() * 1000)


def expected_for(employee: Employee, day: date) -> timedelta:
    """Jornada prevista do funcionário naquele dia da semana."""
    return timedelta(minutes=employee.daily_minutes) if str(day.isoweekday()) in employee.workdays else timedelta(0)


def build_days(
    shifts: list[Shift],
    deleted: list[Punch],
    employee: Employee,
    first: date,
    last: date,
    now: datetime,
    active_from: date | None = None,
) -> list[DayReport]:
    """Um DayReport por dia de `first` a `last` (inclusive), com horas, previsto e saldo.

    Antes de `active_from` (início do histórico do funcionário) não há jornada prevista.
    """
    today = to_local(now).date()
    by_day: dict[date, list[Shift]] = {}
    for s in shifts:
        if first <= s.day <= last:
            by_day.setdefault(s.day, []).append(s)
    deleted_by_day: dict[date, list[Punch]] = {}
    for p in deleted:
        deleted_by_day.setdefault(to_local(p.ts).date(), []).append(p)

    days = []
    day = first
    while day <= last:
        day_shifts = by_day.get(day, [])
        worked = sum((s.worked for s in day_shifts), timedelta(0))
        expected = expected_for(employee, day) if not active_from or day >= active_from else timedelta(0)
        still_open = any(s.is_open(now, settings.max_shift) for s in day_shifts)
        closed = day < today and not still_open

        if not closed:
            status = DayStatus.ANDAMENTO
        elif any(not s.complete for s in day_shifts):
            status = DayStatus.INCOMPLETO
        elif not day_shifts:
            status = DayStatus.FALTA if expected else DayStatus.FOLGA
        else:
            status = DayStatus.OK

        punches = [p for s in day_shifts for p in s.punches] + deleted_by_day.get(day, [])
        days.append(
            DayReport(
                date=day.isoformat(),
                punches=[PunchOut.model_validate(p) for p in sorted(punches, key=lambda p: p.ts)],
                worked_ms=_ms(worked),
                expected_ms=_ms(expected),
                balance_ms=_ms(worked - expected) if closed else 0,
                status=status,
                closed=closed,
            )
        )
        day += timedelta(days=1)
    return days


class ReportService:
    def __init__(self, db: Session):
        self.employees = EmployeeRepository(db)
        self.punches = PunchRepository(db)

    def monthly(self, employee_id: int, month: str) -> MonthReport:
        employee = self.employees.get(employee_id)
        if not employee:
            raise BadRequest("Funcionário inválido")
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
            raise BadRequest("Mês inválido (use AAAA-MM)")

        now = datetime.now(timezone.utc)
        year, mon = map(int, month.split("-"))
        start, end = month_bounds(year, mon)
        first_day = start.date()
        last_day = min((end - timedelta(days=1)).date(), to_local(now).date())

        # Histórico inteiro: o banco de horas soma todos os meses anteriores
        punches = self.punches.list_for_employee(employee.id, end + settings.max_shift, include_deleted=True)
        active = [p for p in punches if not p.deleted_at]
        shifts = pair_shifts(active, settings.max_shift)
        deleted = [p for p in punches if p.deleted_at]

        history_start = min([to_local(employee.created_at).date()] + [s.day for s in shifts[:1]])
        days = build_days(shifts, deleted, employee, first_day, last_day, now, active_from=history_start)
        before = build_days(shifts, [], employee, history_start, first_day - timedelta(days=1), now)

        closed = [d for d in days if d.closed]
        previous = sum(d.balance_ms for d in before)
        balance = sum(d.balance_ms for d in closed)
        return MonthReport(
            employee=EmployeeRef.model_validate(employee),
            month=month,
            days=days,
            total_ms=sum(d.worked_ms for d in days),
            expected_ms=sum(d.expected_ms for d in closed),
            balance_ms=balance,
            previous_balance_ms=previous,
            bank_ms=previous + balance,
        )

    @staticmethod
    def to_csv(report: MonthReport) -> str:
        def hours(ms: int, signed: bool = False) -> str:
            minutes = round(abs(ms) / 60000)
            sign = ("-" if ms < 0 else "+") if signed and minutes else ""
            return f"{sign}{minutes // 60}:{minutes % 60:02d}"

        def stamp(p: PunchOut, day: str) -> str:
            local = to_local(p.ts)
            next_day = " (+1)" if local.date().isoformat() != day else ""
            kind = "E" if p.type == PunchType.ENTRADA else "S"
            return f"{kind} {local:%H:%M}{next_day}{'*' if p.manual else ''}"

        lines = ["Data;Dia;Batidas;Trabalhado;Previsto;Saldo;Situação"]
        for d in report.days:
            batidas = " | ".join(stamp(p, d.date) for p in d.punches if not p.deleted_at)
            weekday = WEEKDAYS[date.fromisoformat(d.date).weekday()]
            saldo = hours(d.balance_ms, signed=True) if d.closed and (d.expected_ms or d.worked_ms) else ""
            lines.append(
                f"{d.date};{weekday};{batidas};{hours(d.worked_ms)};{hours(d.expected_ms)};{saldo};"
                f"{STATUS_LABEL[d.status]}"
            )
        lines.append(
            f"Total;;;{hours(report.total_ms)};{hours(report.expected_ms)};{hours(report.balance_ms, True)};"
        )
        lines.append(f"Banco de horas anterior;;;;;{hours(report.previous_balance_ms, True)};")
        lines.append(f"Banco de horas ao fim do mês;;;;;{hours(report.bank_ms, True)};")
        lines.append("* lançamento ou correção manual; (+1) batida no dia seguinte;;;;;;")
        return "﻿" + "\r\n".join(lines)

    @staticmethod
    def csv_filename(report: MonthReport) -> str:
        return f"ponto-{re.sub(r'[^A-Za-z0-9_-]+', '_', report.employee.name)}-{report.month}.csv"
