import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BadRequest
from app.models import ABSENCE_KINDS, Absence, Company, Employee, MonthClosure, Punch, PunchType
from app.repositories.calendar_repository import ClosureRepository, HolidayRepository
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.punch_repository import PunchRepository
from app.schemas.absence import DayAbsence
from app.schemas.employee import EmployeeRef
from app.schemas.punch import PunchOut
from app.schemas.report import ClosureOut, DayReport, DayStatus, MonthReport, ReopeningOut, SummaryRow
from app.services.audit import AuditLog
from app.services.rules import RuleBook, load_rules
from app.services.shifts import Shift, pair_shifts
from app.utils.dates import month_bounds, night_time, parse_month, to_local

STATUS_LABEL = {
    DayStatus.OK: "OK",
    DayStatus.INCOMPLETO: "Incompleto",
    DayStatus.FALTA: "Falta",
    DayStatus.FOLGA: "Folga",
    DayStatus.FERIADO: "Feriado",
    DayStatus.FORA: "Fora do contrato",
    DayStatus.ANTES: "Antes do controle",
    DayStatus.AUSENCIA: "Ausência",
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


def counted_time(shift: Shift, rules: RuleBook | None = None) -> tuple[timedelta, timedelta]:
    """(horas trabalhadas, horas noturnas), as duas com a hora noturna reduzida (CLT art. 73 §1º).

    Vale o horário noturno da regra em vigor no dia da jornada.
    """
    if not shift.complete:
        return ZERO, ZERO
    rules = rules or RuleBook()
    rule = rules.on(shift.day)
    night_real = night_time(shift.start, shift.punches[1].ts, rule.night_start_hour, rule.night_end_hour, rules.tz)
    night = night_real * (60 / rule.night_hour_minutes)
    return shift.worked - night_real + night, night


def expected_for(
    employee: Employee, day: date, holidays: dict[date, str], control_from: date | None = None
) -> timedelta:
    """Jornada prevista no dia: zero fora do contrato, antes do controle, em feriado e nos dias sem trabalho."""
    if not employee.employed_on(day) or day in holidays or (control_from and day < control_from):
        return ZERO
    schedule = employee.schedule_on(day)
    return timedelta(minutes=schedule.minutes_on(day)) if schedule else ZERO


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
    rules: RuleBook | None = None,
    control_from: date | None = None,
    absences: dict[date, Absence] | None = None,
) -> list[DayReport]:
    """Um DayReport por dia de `first` a `last` (inclusive). `shifts` em ordem, de todo o histórico.

    Cada dia usa a regra da empresa em vigor nele (`rules`; sem ela, os valores do .env). Antes de
    `control_from` (início do controle no sistema) os dias aparecem, mas não entram no saldo.
    `absences` (dia → ausência): o dia não é falta; se a ausência abona, a jornada (ou as horas
    abonadas) conta como trabalhada; a folga do banco tira a jornada do banco de horas.
    """
    absences = absences or {}
    rules = rules or RuleBook()
    today = to_local(now, rules.tz).date()

    by_day: dict[date, list[Shift]] = {}
    previous_of: dict[date, Shift | None] = {}  # jornada anterior à primeira do dia (para o descanso de 11h)
    for i, s in enumerate(shifts):
        if first <= s.day <= last:
            if s.day not in by_day:
                previous_of[s.day] = shifts[i - 1] if i else None
            by_day.setdefault(s.day, []).append(s)
    deleted_by_day: dict[date, list[Punch]] = {}
    for p in deleted:
        deleted_by_day.setdefault(to_local(p.ts, rules.tz).date(), []).append(p)

    days = []
    day = first
    while day <= last:
        day_shifts = by_day.get(day, [])
        counted = night = ZERO
        for s in day_shifts:
            c, n = counted_time(s, rules)
            counted, night = counted + c, night + n
        expected = expected_for(employee, day, holidays, control_from)
        before_control = bool(control_from and day < control_from and employee.employed_on(day))
        absence = None if before_control else absences.get(day)
        credited = ZERO
        if absence and absence.credits:
            credited = min(expected, timedelta(minutes=absence.minutes)) if absence.minutes else expected
        still_open = any(s.is_open(now, rules.max_shift_at(s.start)) for s in day_shifts)
        closed = day < today and not still_open

        if before_control:
            status = DayStatus.ANTES
        elif not closed:
            status = DayStatus.ANDAMENTO
        elif any(not s.complete for s in day_shifts):
            status = DayStatus.INCOMPLETO
        elif day_shifts:
            status = DayStatus.OK
        elif expected and absence:
            status = DayStatus.AUSENCIA
        elif expected:
            status = DayStatus.FALTA
        elif not employee.employed_on(day):
            status = DayStatus.FORA
        elif day in holidays:
            status = DayStatus.FERIADO
        else:
            status = DayStatus.FOLGA

        balance = ZERO
        if closed and not before_control:
            balance = counted + credited - expected
            if status == DayStatus.OK and expected and abs(balance) <= rules.on(day).tolerance:
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
                alerts=(
                    day_alerts(day_shifts, previous_of.get(day), counted, expected)
                    if closed and day_shifts and not before_control
                    else []
                ),
                absence=DayAbsence.model_validate(absence) if absence else None,
                credited_ms=_ms(credited) if closed else 0,
            )
        )
        day += timedelta(days=1)
    return days


class ReportService:
    def __init__(self, db: Session, company_id: int):
        self.db = db
        self.company_id = company_id
        self.employees = EmployeeRepository(db, company_id)
        self.punches = PunchRepository(db)
        self.holidays = HolidayRepository(db, company_id)
        self.closures = ClosureRepository(db)
        self.rules = load_rules(db, company_id)
        company = db.get(Company, company_id)
        self.control_start = company.control_start if company else None

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
            for e in AuditLog(self.db, self.company_id).reopenings(employee.id, month)
        ]
        return report

    def build(self, employee: Employee, month: str, closure: MonthClosure | None) -> MonthReport:
        now = datetime.now(timezone.utc)
        rules = self.rules
        start, end = month_bounds(*parse_month(month), rules.tz)
        first_day = start.date()
        last_day = min((end - timedelta(days=1)).date(), to_local(now, rules.tz).date())

        # Histórico inteiro: o banco de horas soma todos os meses anteriores
        punches = self.punches.list_for_employee(employee.id, end + rules.longest_shift, include_deleted=True)
        shifts = pair_shifts([p for p in punches if not p.deleted_at], rules.max_shift_at, rules.tz)
        deleted = [p for p in punches if p.deleted_at]

        control_from = employee.counting_from(self.control_start)
        # O banco só soma a partir do início do controle (antes dele os dias não contam). Sem data de
        # controle (empresas de antes da opção), o histórico começa como sempre começou.
        if employee.control_start or self.control_start:
            history_start = control_from
        else:
            history_start = min([employee.hired_on] + [s.day for s in shifts[:1]])
        holidays = self.holidays.all_between(min(history_start, first_day), max(last_day, first_day))
        absences = self._absences_by_day(employee.id)
        days = build_days(shifts, deleted, employee, first_day, last_day, now, holidays, rules, control_from, absences)
        before = build_days(
            shifts, [], employee, history_start, first_day - timedelta(days=1), now, holidays, rules, control_from,
            absences,
        )

        closed = [d for d in days if d.closed]
        # Saldo trazido do controle anterior: vale a partir do mês em que o controle começa
        initial = employee.initial_balance_minutes * 60000 if last_day >= control_from else 0
        previous = initial + sum(d.balance_ms for d in before)
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
            initial_balance_ms=employee.initial_balance_minutes * 60000,
            control_from=control_from,
            credited_ms=sum(d.credited_ms for d in closed),
            absence_days=_absence_days(days),
            closure=ClosureOut.model_validate(closure) if closure else None,
        )

    def _absences_by_day(self, employee_id: int) -> dict[date, Absence]:
        result = {}
        for a in self.db.scalars(select(Absence).where(Absence.employee_id == employee_id)):
            day = a.first_day
            while day <= a.last_day:
                result[day] = a
                day += timedelta(days=1)
        return result

    def summary(self, month: str) -> list[SummaryRow]:
        """Resumo do mês de todos os funcionários com contrato em algum dia do mês."""
        check_month(month)
        start, end = month_bounds(*parse_month(month), self.rules.tz)
        first_day, last_day = start.date(), (end - timedelta(days=1)).date()
        closures = self.closures.list_for_month(month, self.company_id)
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
                    credited_ms=r.credited_ms,
                    absence_days=r.absence_days,
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

    def to_csv(self, report: MonthReport) -> str:
        hours = self._hours
        tz = self.rules.tz

        def stamp(p: PunchOut, day: str) -> str:
            local = to_local(p.ts, tz)
            next_day = " (+1)" if local.date().isoformat() != day else ""
            kind = "E" if p.type == PunchType.ENTRADA else "S"
            marks = ("*" if p.manual else "") + (" (offline)" if p.offline else "") + (" (cel)" if p.source == "app" else "")
            return f"{kind} {local:%H:%M}{next_day}{marks}"

        lines = ["Data;Dia;Batidas;Trabalhado;Noturno;Previsto;Abonado;Saldo;Situação;Alertas"]
        for d in report.days:
            batidas = " | ".join(stamp(p, d.date) for p in d.punches if not p.deleted_at)
            weekday = WEEKDAYS[date.fromisoformat(d.date).weekday()]
            saldo = hours(d.balance_ms, signed=True) if d.closed and (d.expected_ms or d.worked_ms) else ""
            label = STATUS_LABEL[d.status] if not d.absence or d.status == DayStatus.OK else d.absence.label
            if d.absence and d.status == DayStatus.OK:
                label += f" · {d.absence.label}"
            situacao = _text(label + (f" ({d.holiday})" if d.holiday else ""))
            abonado = hours(d.credited_ms) if d.credited_ms else ""
            lines.append(
                f"{d.date};{weekday};{batidas};{hours(d.worked_ms)};{hours(d.night_ms)};{hours(d.expected_ms)};"
                f"{abonado};{saldo};{situacao};{_text(' / '.join(d.alerts))}"
            )
        lines.append(
            f"Total;;;{hours(report.total_ms)};{hours(report.night_ms)};{hours(report.expected_ms)};"
            f"{hours(report.credited_ms)};{hours(report.balance_ms, True)};;"
        )
        lines.append(f"Banco de horas anterior;;;;;;;{hours(report.previous_balance_ms, True)};;")
        lines.append(f"Banco de horas ao fim do mês;;;;;;;{hours(report.bank_ms, True)};;")
        lines.append(
            "* lançamento ou correção manual; (+1) batida no dia seguinte; (cel) feita no app de celular;"
            " horas noturnas com hora reduzida; abonado: ausência justificada que conta como trabalhado;"
            f" tolerância de {self._tolerance_label(report)} por dia;;;;;;"
        )
        return "﻿" + "\r\n".join(lines)

    def _tolerance_label(self, report: MonthReport) -> str:
        """Tolerância do mês (mais de uma quando a regra mudou no meio dele)."""
        values = sorted({self.rules.on(date.fromisoformat(d.date)).tolerance_minutes for d in report.days})
        values = values or [self.rules.current.tolerance_minutes]
        return " ou ".join(f"{v} min" for v in values)

    def summary_csv(self, month: str, rows: list[SummaryRow]) -> str:
        hours = self._hours
        tz = self.rules.tz

        def when(ts: datetime | None) -> str:
            return f"{to_local(ts, tz):%d/%m/%Y %H:%M}" if ts else ""

        kinds = list(ABSENCE_KINDS)
        lines = [
            f"Resumo {month}" + ";" * (11 + len(kinds)),
            "Funcionário;Trabalhado;Noturno;Previsto;Abonado;Saldo do mês;Banco de horas;Faltas;"
            + "".join(f"{ABSENCE_KINDS[k][0]} (dias);" for k in kinds)
            + "Incompletos;Alertas;Mês fechado;Ciência do funcionário",
        ]
        for r in rows:
            closure = r.closure
            lines.append(
                f"{_text(r.employee.name)};{hours(r.total_ms)};{hours(r.night_ms)};{hours(r.expected_ms)};"
                f"{hours(r.credited_ms)};{hours(r.balance_ms, True)};{hours(r.bank_ms, True)};{r.absences};"
                + "".join(f"{r.absence_days.get(k, 0)};" for k in kinds)
                + f"{r.incomplete};{r.alerts};"
                f"{when(closure.closed_at) if closure else ''};{when(closure.acknowledged_at) if closure else ''}"
            )
        return "﻿" + "\r\n".join(lines)

    @staticmethod
    def csv_filename(report: MonthReport) -> str:
        return f"ponto-{re.sub(r'[^A-Za-z0-9_-]+', '_', report.employee.name)}-{report.month}.csv"


def _absence_days(days: list[DayReport]) -> dict[str, int]:
    """Dias de trabalho com ausência, por tipo (os dias sem jornada, como fins de semana nas férias, não contam)."""
    counts: dict[str, int] = {}
    for d in days:
        if d.absence and d.expected_ms:
            counts[d.absence.kind] = counts.get(d.absence.kind, 0) + 1
    return counts


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
