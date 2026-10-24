import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BadRequest
from app.models import Employee, MonthClosure, Punch, PunchType
from app.repositories.calendar_repository import ClosureRepository, HolidayRepository
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.punch_repository import PunchRepository
from app.schemas.employee import EmployeeRef
from app.schemas.punch import PunchOut
from app.schemas.report import ClosureOut, DayReport, DayStatus, MonthReport, ReopeningOut, SummaryRow
from app.services.audit import AuditLog
from app.services.shifts import Shift, pair_shifts
from app.utils.dates import month_bounds, night_time, parse_month, to_local

STATUS_LABEL = {
    DayStatus.OK: "OK",
    DayStatus.INCOMPLETO: "Incompleto",
    DayStatus.FALTA: "Falta",
    DayStatus.FOLGA: "Folga",
    DayStatus.FERIADO: "Feriado",
    DayStatus.FORA: "Fora do contrato",
    DayStatus.ANDAMENTO: "Em andamento",
}
WEEKDAYS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
ZERO = timedelta(0)


def _ms(delta: timedelta) -> int:
    return int(delta.total_seconds() * 1000)


def check_month(month: str) -> str:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month or ""):
        raise BadRequest("Mês inválido (use AAAA-MM)")
    return month


def counted_time(shift: Shift) -> tuple[timedelta, timedelta]:
    """(horas trabalhadas, horas noturnas), as duas com a hora noturna reduzida (CLT art. 73 §1º)."""
    if not shift.complete:
        return ZERO, ZERO
    night_real = night_time(shift.start, shift.punches[1].ts)
    night = night_real * (60 / settings.night_hour_minutes)
    return shift.worked - night_real + night, night


def expected_for(employee: Employee, day: date, holidays: dict[date, str]) -> timedelta:
    """Jornada prevista no dia: zero fora do contrato, em feriado e nos dias sem trabalho."""
    if not employee.employed_on(day) or day in holidays:
        return ZERO
    schedule = employee.schedule_on(day)
    if not schedule or str(day.isoweekday()) not in schedule.workdays:
        return ZERO
    return timedelta(minutes=schedule.daily_minutes)


def day_alerts(day_shifts: list[Shift], previous: Shift | None, counted: timedelta, expected: timedelta) -> list[str]:
    """Avisos da CLT para conferência (não alteram o saldo)."""
    alerts = []
    done = [s for s in day_shifts if s.complete]
    real = sum((s.worked for s in done), ZERO)
    gaps = [b.start - a.punches[-1].ts for a, b in zip(done, done[1:])]
    biggest_gap = max(gaps, default=ZERO)
    if real > timedelta(hours=6) and biggest_gap < timedelta(hours=1):
        alerts.append("Intervalo de almoço menor que 1h")  # art. 71
    elif real > timedelta(hours=4) and biggest_gap < timedelta(minutes=15):
        alerts.append("Intervalo menor que 15 min")  # art. 71 §1º
    if previous and previous.complete and day_shifts[0].start - previous.punches[-1].ts < timedelta(hours=11):
        alerts.append("Menos de 11h de descanso desde a jornada anterior")  # art. 66
    if expected and counted - expected > timedelta(hours=2):
        alerts.append("Mais de 2h extras no dia")  # art. 59
    if not expected and counted > ZERO:
        alerts.append("Trabalho em dia sem jornada prevista")
    return alerts


def build_days(
    shifts: list[Shift],
    deleted: list[Punch],
    employee: Employee,
    first: date,
    last: date,
    now: datetime,
    holidays: dict[date, str],
) -> list[DayReport]:
    """Um DayReport por dia de `first` a `last` (inclusive). `shifts` em ordem, de todo o histórico."""
    today = to_local(now).date()
    tolerance = timedelta(minutes=settings.tolerance_minutes)

    by_day: dict[date, list[Shift]] = {}
    previous_of: dict[date, Shift | None] = {}  # jornada anterior à primeira do dia (para o descanso de 11h)
    for i, s in enumerate(shifts):
        if first <= s.day <= last:
            if s.day not in by_day:
                previous_of[s.day] = shifts[i - 1] if i else None
            by_day.setdefault(s.day, []).append(s)
    deleted_by_day: dict[date, list[Punch]] = {}
    for p in deleted:
        deleted_by_day.setdefault(to_local(p.ts).date(), []).append(p)

    days = []
    day = first
    while day <= last:
        day_shifts = by_day.get(day, [])
        counted = night = ZERO
        for s in day_shifts:
            c, n = counted_time(s)
            counted, night = counted + c, night + n
        expected = expected_for(employee, day, holidays)
        still_open = any(s.is_open(now, settings.max_shift) for s in day_shifts)
        closed = day < today and not still_open

        if not closed:
            status = DayStatus.ANDAMENTO
        elif any(not s.complete for s in day_shifts):
            status = DayStatus.INCOMPLETO
        elif day_shifts:
            status = DayStatus.OK
        elif expected:
            status = DayStatus.FALTA
        elif not employee.employed_on(day):
            status = DayStatus.FORA
        elif day in holidays:
            status = DayStatus.FERIADO
        else:
            status = DayStatus.FOLGA

        balance = ZERO
        if closed:
            balance = counted - expected
            if status == DayStatus.OK and expected and abs(balance) <= tolerance:
                balance = ZERO  # tolerância do art. 58 §1º

        punches = [p for s in day_shifts for p in s.punches] + deleted_by_day.get(day, [])
        days.append(
            DayReport(
                date=day.isoformat(),
                punches=[PunchOut.model_validate(p) for p in sorted(punches, key=lambda p: p.ts)],
                worked_ms=_ms(counted),
                night_ms=_ms(night),
                expected_ms=_ms(expected),
                balance_ms=_ms(balance),
                status=status,
                closed=closed,
                holiday=holidays.get(day),
                alerts=day_alerts(day_shifts, previous_of.get(day), counted, expected) if closed and day_shifts else [],
            )
        )
        day += timedelta(days=1)
    return days


class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.employees = EmployeeRepository(db)
        self.punches = PunchRepository(db)
        self.holidays = HolidayRepository(db)
        self.closures = ClosureRepository(db)

    def monthly(self, employee_id: int, month: str) -> MonthReport:
        employee = self.employees.get(employee_id)
        if not employee:
            raise BadRequest("Funcionário inválido")
        check_month(month)
        report = self.build(employee, month, self.closures.get(employee.id, month))
        report.reopenings = [
            ReopeningOut(
                reopened_at=e.at,
                reopened_by=e.user,
                note=e.details.get("note"),
                closed_at=e.details.get("closed_at"),
                closed_by=e.details.get("closed_by"),
                acknowledged_at=e.details.get("acknowledged_at"),
            )
            for e in AuditLog(self.db).reopenings(employee.id, month)
        ]
        return report

    def build(self, employee: Employee, month: str, closure: MonthClosure | None) -> MonthReport:
        now = datetime.now(timezone.utc)
        start, end = month_bounds(*parse_month(month))
        first_day = start.date()
        last_day = min((end - timedelta(days=1)).date(), to_local(now).date())

        # Histórico inteiro: o banco de horas soma todos os meses anteriores
        punches = self.punches.list_for_employee(employee.id, end + settings.max_shift, include_deleted=True)
        shifts = pair_shifts([p for p in punches if not p.deleted_at], settings.max_shift)
        deleted = [p for p in punches if p.deleted_at]

        history_start = min([employee.hired_on] + [s.day for s in shifts[:1]])
        holidays = self.holidays.all_between(min(history_start, first_day), max(last_day, first_day))
        days = build_days(shifts, deleted, employee, first_day, last_day, now, holidays)
        before = build_days(shifts, [], employee, history_start, first_day - timedelta(days=1), now, holidays)

        closed = [d for d in days if d.closed]
        previous = sum(d.balance_ms for d in before)
        balance = sum(d.balance_ms for d in closed)
        return MonthReport(
            employee=EmployeeRef.model_validate(employee),
            month=month,
            days=days,
            total_ms=sum(d.worked_ms for d in days),
            night_ms=sum(d.night_ms for d in days),
            expected_ms=sum(d.expected_ms for d in closed),
            balance_ms=balance,
            previous_balance_ms=previous,
            bank_ms=previous + balance,
            closure=ClosureOut.model_validate(closure) if closure else None,
        )

    def summary(self, month: str) -> list[SummaryRow]:
        """Resumo do mês de todos os funcionários com contrato em algum dia do mês."""
        check_month(month)
        start, end = month_bounds(*parse_month(month))
        first_day, last_day = start.date(), (end - timedelta(days=1)).date()
        closures = self.closures.list_for_month(month)
        rows = []
        for employee in self.employees.list():
            if employee.hired_on > last_day or (employee.terminated_on and employee.terminated_on < first_day):
                continue
            r = self.build(employee, month, closures.get(employee.id))
            rows.append(
                SummaryRow(
                    employee=r.employee,
                    total_ms=r.total_ms,
                    night_ms=r.night_ms,
                    expected_ms=r.expected_ms,
                    balance_ms=r.balance_ms,
                    bank_ms=r.bank_ms,
                    absences=sum(d.status == DayStatus.FALTA for d in r.days),
                    incomplete=sum(d.status == DayStatus.INCOMPLETO for d in r.days),
                    alerts=sum(len(d.alerts) for d in r.days),
                    closure=r.closure,
                )
            )
        return rows

    # ---------- CSV ----------
    # Separado por ";" (padrão do Excel em português). Textos digitados (nomes, feriados) passam por _text.

    @staticmethod
    def _hours(ms: int, signed: bool = False) -> str:
        minutes = round(abs(ms) / 60000)
        sign = ("-" if ms < 0 else "+") if signed and minutes else ""
        return f"{sign}{minutes // 60}:{minutes % 60:02d}"

    @classmethod
    def to_csv(cls, report: MonthReport) -> str:
        hours = cls._hours

        def stamp(p: PunchOut, day: str) -> str:
            local = to_local(p.ts)
            next_day = " (+1)" if local.date().isoformat() != day else ""
            kind = "E" if p.type == PunchType.ENTRADA else "S"
            marks = ("*" if p.manual else "") + (" (offline)" if p.offline else "") + (" (cel)" if p.source == "app" else "")
            return f"{kind} {local:%H:%M}{next_day}{marks}"

        lines = ["Data;Dia;Batidas;Trabalhado;Noturno;Previsto;Saldo;Situação;Alertas"]
        for d in report.days:
            batidas = " | ".join(stamp(p, d.date) for p in d.punches if not p.deleted_at)
            weekday = WEEKDAYS[date.fromisoformat(d.date).weekday()]
            saldo = hours(d.balance_ms, signed=True) if d.closed and (d.expected_ms or d.worked_ms) else ""
            situacao = _text(STATUS_LABEL[d.status] + (f" ({d.holiday})" if d.holiday else ""))
            lines.append(
                f"{d.date};{weekday};{batidas};{hours(d.worked_ms)};{hours(d.night_ms)};{hours(d.expected_ms)};"
                f"{saldo};{situacao};{_text(' / '.join(d.alerts))}"
            )
        lines.append(
            f"Total;;;{hours(report.total_ms)};{hours(report.night_ms)};{hours(report.expected_ms)};"
            f"{hours(report.balance_ms, True)};;"
        )
        lines.append(f"Banco de horas anterior;;;;;;{hours(report.previous_balance_ms, True)};;")
        lines.append(f"Banco de horas ao fim do mês;;;;;;{hours(report.bank_ms, True)};;")
        lines.append(
            "* lançamento ou correção manual; (+1) batida no dia seguinte; (cel) feita no app de celular;"
            " horas noturnas com hora reduzida;"
            f" tolerância de {settings.tolerance_minutes} min por dia;;;;;"
        )
        return "﻿" + "\r\n".join(lines)

    @classmethod
    def summary_csv(cls, month: str, rows: list[SummaryRow]) -> str:
        hours = cls._hours

        def when(ts: datetime | None) -> str:
            return f"{to_local(ts):%d/%m/%Y %H:%M}" if ts else ""

        lines = [
            f"Resumo {month};;;;;;;;;;",
            "Funcionário;Trabalhado;Noturno;Previsto;Saldo do mês;Banco de horas;Faltas;Incompletos;Alertas;"
            "Mês fechado;Ciência do funcionário",
        ]
        for r in rows:
            closure = r.closure
            lines.append(
                f"{_text(r.employee.name)};{hours(r.total_ms)};{hours(r.night_ms)};{hours(r.expected_ms)};"
                f"{hours(r.balance_ms, True)};{hours(r.bank_ms, True)};{r.absences};{r.incomplete};{r.alerts};"
                f"{when(closure.closed_at) if closure else ''};{when(closure.acknowledged_at) if closure else ''}"
            )
        return "﻿" + "\r\n".join(lines)

    @staticmethod
    def csv_filename(report: MonthReport) -> str:
        return f"ponto-{re.sub(r'[^A-Za-z0-9_-]+', '_', report.employee.name)}-{report.month}.csv"


def _text(value: str) -> str:
    """Célula de texto livre no CSV.

    - Começando com = + - @ (ou tab/CR), o Excel trataria como fórmula: ganha um ' na frente.
    - Com ; aspas ou quebra de linha, vai entre aspas para não criar colunas ou linhas novas.
    """
    if value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        value = "'" + value
    if any(c in value for c in ';"\r\n'):
        value = '"' + value.replace('"', '""') + '"'
    return value
