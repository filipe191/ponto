from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils.dates import now_local

if TYPE_CHECKING:
    from app.models.punch import Punch


class Employee(Base):
    __tablename__ = "employees"
    # O PIN identifica o funcionário no relógio da empresa: só precisa ser único dentro dela
    __table_args__ = (UniqueConstraint("company_id", "pin_hash", name="employees_company_pin_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String)
    pin_hash: Mapped[str] = mapped_column(String)
    # PIN de 4 ou 5 dígitos, de antes da regra de 6: continua valendo, mas o admin deve trocar
    pin_short: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("FALSE"))
    # Dados pessoais apagados depois do prazo de guarda (LGPD); as batidas ficam, sem o nome
    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Fora do período de contrato não há jornada prevista (nem faltas)
    hired_on: Mapped[date] = mapped_column(Date)
    terminated_on: Mapped[date | None] = mapped_column(Date)
    # Início do controle só deste funcionário (vazio = o da empresa). Antes dele nenhum dia conta.
    control_start: Mapped[date | None] = mapped_column(Date)
    # Saldo do banco de horas trazido do controle anterior (planilha, outro sistema), em minutos
    initial_balance_minutes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    initial_balance_note: Mapped[str] = mapped_column(String, default="", server_default="")

    # Batidas nunca são apagadas junto com o funcionário (o banco recusa, ver EmployeeService.delete)
    punches: Mapped[list["Punch"]] = relationship(back_populates="employee", passive_deletes="all")
    schedules: Mapped[list["EmployeeSchedule"]] = relationship(
        order_by="EmployeeSchedule.valid_from", lazy="selectin", cascade="all, delete-orphan"
    )

    def schedule_on(self, day: date) -> "EmployeeSchedule | None":
        """Jornada em vigor no dia (a mais recente que começou até ele)."""
        current = None
        for s in self.schedules:
            if s.valid_from <= day:
                current = s
        return current or (self.schedules[0] if self.schedules else None)

    @property
    def retention_due(self) -> bool:
        """Desligado há mais que o prazo de guarda (LGPD) e ainda com os dados pessoais."""
        from app.core.config import settings

        if self.anonymized_at or not self.terminated_on:
            return False
        today = now_local().date()
        try:
            limit = today.replace(year=today.year - settings.retention_years)
        except ValueError:  # 29/02
            limit = today.replace(year=today.year - settings.retention_years, day=28)
        return self.terminated_on <= limit

    def employed_on(self, day: date) -> bool:
        return self.hired_on <= day and (self.terminated_on is None or day <= self.terminated_on)

    def counting_from(self, company_start: date | None) -> date:
        """Primeiro dia que conta no espelho e no banco: a admissão ou o início do controle, o que vier depois."""
        start = self.control_start or company_start
        return max(self.hired_on, start) if start else self.hired_on

    # Jornada em vigor hoje (usada na listagem e no cadastro)
    @property
    def daily_minutes(self) -> int:
        current = self.schedule_on(now_local().date())
        return current.daily_minutes if current else 0

    @property
    def workdays(self) -> str:
        current = self.schedule_on(now_local().date())
        return current.workdays if current else ""

    @property
    def schedule_label(self) -> str:
        current = self.schedule_on(now_local().date())
        return current.label if current else "sem jornada"


SCHEDULE_WEEK = "semana"  # minutos de cada dia da semana (seg … dom)
SCHEDULE_CYCLE = "ciclo"  # escala que se repete a cada N dias (ex.: 12x36), a partir de `cycle_start`
_WEEK = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
# Escalas conhecidas pelo nome (minutos de cada dia do ciclo)
_NAMED_CYCLES = {(720, 0): "12x36", (1440, 0, 0): "24x48", (720, 720, 0, 0): "12x36 em dupla"}


def hours_label(minutes: int) -> str:
    return f"{minutes // 60}h{minutes % 60:02d}"


class EmployeeSchedule(Base):
    """Jornada prevista a partir de uma data. Mudar a jornada cria uma nova vigência e não altera o passado.

    Semanal: 7 valores (seg … dom), 0 = folga. Escala em ciclo: N valores que se repetem a partir de
    `cycle_start` (o dia que corresponde ao primeiro valor), ex.: 12x36 = [720, 0].
    """

    __tablename__ = "employee_schedules"
    __table_args__ = (UniqueConstraint("employee_id", "valid_from", name="employee_schedules_emp_from_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    valid_from: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String, default=SCHEDULE_WEEK, server_default=SCHEDULE_WEEK)
    day_minutes: Mapped[str] = mapped_column(String)  # minutos separados por vírgula
    cycle_start: Mapped[date | None] = mapped_column(Date)

    @classmethod
    def weekly(cls, valid_from: date, daily_minutes: int, workdays: str) -> "EmployeeSchedule":
        """Jornada no formato antigo: os mesmos minutos em cada dia de trabalho ("1"=seg … "7"=dom)."""
        minutes = [daily_minutes if str(d) in workdays else 0 for d in range(1, 8)]
        return cls(valid_from=valid_from, kind=SCHEDULE_WEEK, day_minutes=",".join(map(str, minutes)))

    @property
    def minutes(self) -> list[int]:
        return [int(m) for m in self.day_minutes.split(",")]

    def minutes_on(self, day: date) -> int:
        values = self.minutes
        if self.kind == SCHEDULE_CYCLE:
            return values[(day - (self.cycle_start or self.valid_from)).days % len(values)]
        return values[day.weekday()]

    # Formato antigo (listagem, app e relatórios que ainda o usam): o maior dia e os dias com jornada
    @property
    def daily_minutes(self) -> int:
        return max(self.minutes, default=0)

    @property
    def workdays(self) -> str:
        if self.kind == SCHEDULE_CYCLE:
            return ""
        return "".join(str(i + 1) for i, m in enumerate(self.minutes) if m)

    @property
    def label(self) -> str:
        """Ex.: "8h00 · seg a sex", "seg a sex 8h00 · sáb 4h00", "12x36 (12h00 em dias alternados)"."""
        values = self.minutes
        if self.kind == SCHEDULE_CYCLE:
            name = _NAMED_CYCLES.get(tuple(values))
            days = ", ".join(hours_label(m) if m else "folga" for m in values)
            return f"escala {name} ({days})" if name else f"escala de {len(values)} dias ({days})"
        groups: list[tuple[int, int, int]] = []  # (primeiro dia, último dia, minutos)
        for i, m in enumerate(values):
            if m and groups and groups[-1][1] == i - 1 and groups[-1][2] == m:
                groups[-1] = (groups[-1][0], i, m)
            elif m:
                groups.append((i, i, m))
        if not groups:
            return "sem dias de trabalho"

        def span(a: int, b: int) -> str:
            return _WEEK[a] if a == b else f"{_WEEK[a]} {'e' if b == a + 1 else 'a'} {_WEEK[b]}"

        if len({m for _, _, m in groups}) == 1:
            return f"{hours_label(groups[0][2])} · " + ", ".join(span(a, b) for a, b, _ in groups)
        return " · ".join(f"{span(a, b)} {hours_label(m)}" for a, b, m in groups)

    @property
    def weekly_minutes(self) -> int | None:
        """Total da semana (só na jornada semanal)."""
        return sum(self.minutes) if self.kind == SCHEDULE_WEEK else None
