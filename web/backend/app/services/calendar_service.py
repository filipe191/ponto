from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Conflict, NotFound
from app.core.security import hash_pin
from app.models import Employee, Holiday, MonthClosure
from app.repositories.calendar_repository import ClosureRepository, HolidayRepository
from app.repositories.employee_repository import EmployeeRepository
from app.schemas.admin import HolidayCreate, HolidayOut, MovableHolidays
from app.schemas.report import MonthReport
from app.services.audit import EMPLOYEE_USER, AuditLog
from app.services.report_service import ReportService, check_month
from app.services.rules import ensure_months_open, load_rules
from app.utils.dates import month_bounds, now_local, parse_month, to_local
from app.utils.holidays import easter, national_holidays


class HolidayService:
    def __init__(self, db: Session, company_id: int):
        self.db = db
        self.repo = HolidayRepository(db, company_id)
        self.audit = AuditLog(db, company_id)
        self.company_id = company_id

    def list(self, year: int) -> list[HolidayOut]:
        national = national_holidays(year)
        custom = self.repo.custom_on_years(date(year, 1, 1), date(year, 12, 31))
        items = [HolidayOut(date=d, name=n, national=True) for d, n in national.items()]
        items += [
            HolidayOut(date=d, name=h.name, national=False, yearly=h.yearly, since=h.date if h.yearly else None)
            for d, h in custom.items()
            if d not in national
        ]
        return sorted(items, key=lambda h: h.date)

    def add(self, data: HolidayCreate, user: str) -> None:
        if data.date in national_holidays(data.date.year):
            raise Conflict("Essa data já é feriado nacional")
        if data.date in self.repo.custom_on_years(data.date, data.date):
            raise Conflict("Já existe um feriado cadastrado nessa data")
        # O feriado tira a jornada do dia (e, se repete, dos anos seguintes): nada disso pode estar fechado
        ensure_months_open(self.db, self.company_id, data.date, "o feriado", until=None if data.yearly else data.date)
        self.repo.add(Holiday(date=data.date, name=data.name, yearly=data.yearly))
        every = " (repete todo ano)" if data.yearly else ""
        self.audit.record(
            user,
            "feriado.adicionado",
            f"Cadastrou o feriado {data.name} em {data.date:%d/%m/%Y}{every}",
            details={"date": data.date, "name": data.name, "yearly": data.yearly},
        )
        self.db.commit()

    def add_movable(self, data: MovableHolidays, user: str) -> int:
        """Pontos facultativos que dependem da Páscoa (mudam de data todo ano), calculados para o ano."""
        days = {
            "carnaval": [
                (easter(data.year) - timedelta(days=48), "Carnaval (segunda-feira)"),
                (easter(data.year) - timedelta(days=47), "Carnaval (terça-feira)"),
            ],
            "corpus_christi": [(easter(data.year) + timedelta(days=60), "Corpus Christi")],
        }
        added = 0
        for item in data.items:
            for day, name in days[item]:
                if day in self.repo.custom_on_years(day, day):
                    continue
                self.add(HolidayCreate(date=day, name=name), user)
                added += 1
        return added

    def delete(self, day: date, user: str) -> None:
        """Remove o feriado do dia. Se ele repete todo ano, para de repetir a partir deste ano (o passado fica)."""
        holiday = self.repo.custom_on_years(day, day).get(day)
        if not holiday:
            raise NotFound("Feriado não encontrado (os nacionais não podem ser removidos)")
        ensure_months_open(self.db, self.company_id, day, "o feriado", until=None if holiday.yearly else day)
        if holiday.yearly and day.year > holiday.date.year:
            holiday.until_year = day.year - 1
            summary = f"Parou de repetir o feriado {holiday.name} a partir de {day.year} (valeu de {holiday.date.year} a {day.year - 1})"
        else:
            self.repo.delete(holiday)
            summary = f"Removeu o feriado {holiday.name} de {day:%d/%m/%Y}" + (" (repetia todo ano)" if holiday.yearly else "")
        self.audit.record(
            user, "feriado.removido", summary, details={"date": day, "name": holiday.name, "yearly": holiday.yearly}
        )
        self.db.commit()

    def missing_next_year(self, today: date) -> int | None:
        """Em dezembro: o ano seguinte, se a empresa ainda não tem nenhum feriado próprio nele."""
        if today.month != 12:
            return None
        year = today.year + 1
        has_any = self.repo.custom_on_years(date(year, 1, 1), date(year, 12, 31))
        return None if has_any else year


class ClosureService:
    """Fechamento do mês: trava as batidas e libera a ciência do funcionário no relógio."""

    def __init__(self, db: Session, company_id: int):
        self.db = db
        self.repo = ClosureRepository(db)
        self.employees = EmployeeRepository(db, company_id)
        self.audit = AuditLog(db, company_id)
        self.tz = load_rules(db, company_id).tz

    def close(self, month: str, employee_id: int | None, user: str) -> int:
        check_month(month)
        start, end = month_bounds(*parse_month(month), self.tz)
        first_day, last_day = start.date(), (end - timedelta(days=1)).date()
        if last_day >= now_local(self.tz).date():
            raise BadRequest("Só é possível fechar um mês que já terminou")
        if employee_id is not None:
            employee = self.employees.get(employee_id)
            if not employee:
                raise NotFound("Funcionário não encontrado")
            targets = [employee]
        else:
            targets = [e for e in self.employees.list() if _employed_in(e, first_day, last_day)]
        closed = 0
        for employee in targets:
            if not self.repo.get(employee.id, month):
                self.repo.add(MonthClosure(employee_id=employee.id, month=month, closed_by=user))
                self.audit.record(
                    user,
                    "mes.fechado",
                    f"Fechou {_month_label(month)} de {employee.name}",
                    employee_id=employee.id,
                    details={"month": month},
                )
                closed += 1
        self.db.commit()
        return closed

    def reopen(self, employee_id: int, month: str, user: str, note: str) -> None:
        """Reabre o mês. O fechamento e a ciência dados até aqui ficam guardados na auditoria."""
        employee = self.employees.get(employee_id)
        closure = self.repo.get(employee_id, check_month(month)) if employee else None
        if not closure:
            raise NotFound("Este mês não está fechado")
        note = note.strip()
        if not note:
            raise BadRequest("Informe o motivo da reabertura")
        ack = (
            f"ciência do funcionário em {to_local(closure.acknowledged_at, self.tz):%d/%m/%Y %H:%M}"
            if closure.acknowledged_at
            else "sem ciência do funcionário"
        )
        self.audit.record(
            user,
            "mes.reaberto",
            f"Reabriu {_month_label(month)} de {employee.name} ({ack}). Motivo: {note}",
            employee_id=employee_id,
            details={
                "month": month,
                "closed_at": closure.closed_at,
                "closed_by": closure.closed_by,
                "acknowledged_at": closure.acknowledged_at,
                "note": note,
            },
        )
        self.repo.delete(closure)
        self.db.commit()


class PortalService:
    """O funcionário consulta o próprio espelho e dá ciência no relógio, identificando-se pelo PIN."""

    def __init__(self, db: Session, company_id: int):
        self.db = db
        self.company_id = company_id
        self.employees = EmployeeRepository(db, company_id)
        self.closures = ClosureRepository(db)
        self.audit = AuditLog(db, company_id)

    def report(self, pin: str, month: str) -> MonthReport:
        employee = self._by_pin(pin)
        return ReportService(self.db, self.company_id).build(employee, check_month(month), self.closures.get(employee.id, month))

    def acknowledge(self, pin: str, month: str, ip: str | None = None) -> None:
        employee = self._by_pin(pin)
        closure = self.closures.get(employee.id, check_month(month))
        if not closure:
            raise BadRequest("Este mês ainda não foi fechado pelo administrador")
        if not closure.acknowledged_at:
            closure.acknowledged_at = datetime.now(timezone.utc)
            self.audit.record(
                EMPLOYEE_USER,
                "mes.ciencia",
                f"{employee.name} deu ciência do espelho de {_month_label(month)} no relógio",
                employee_id=employee.id,
                details={"month": month, "closed_at": closure.closed_at, "closed_by": closure.closed_by},
                ip=ip,
            )
            self.db.commit()

    def _by_pin(self, pin: str) -> Employee:
        employee = self.employees.get_by_pin_hash(hash_pin(pin))
        if not employee or not employee.active:
            raise NotFound("PIN não reconhecido")
        return employee


def _month_label(month: str) -> str:
    year, number = month.split("-")
    return f"{number}/{year}"


def _employed_in(employee: Employee, first: date, last: date) -> bool:
    return employee.hired_on <= last and (employee.terminated_on is None or employee.terminated_on >= first)
