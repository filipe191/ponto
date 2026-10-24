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

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    pin_hash: Mapped[str] = mapped_column(String, unique=True)
    # PIN de 4 ou 5 dígitos, de antes da regra de 6: continua valendo, mas o admin deve trocar
    pin_short: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("FALSE"))
    # Dados pessoais apagados depois do prazo de guarda (LGPD); as batidas ficam, sem o nome
    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Fora do período de contrato não há jornada prevista (nem faltas)
    hired_on: Mapped[date] = mapped_column(Date)
    terminated_on: Mapped[date | None] = mapped_column(Date)

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

    # Jornada em vigor hoje (usada na listagem e no cadastro)
    @property
    def daily_minutes(self) -> int:
        current = self.schedule_on(now_local().date())
        return current.daily_minutes if current else 0

    @property
    def workdays(self) -> str:
        current = self.schedule_on(now_local().date())
        return current.workdays if current else ""


class EmployeeSchedule(Base):
    """Jornada prevista a partir de uma data. Mudar a jornada cria uma nova vigência e não altera o passado."""

    __tablename__ = "employee_schedules"
    __table_args__ = (UniqueConstraint("employee_id", "valid_from", name="employee_schedules_emp_from_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    valid_from: Mapped[date] = mapped_column(Date)
    # Minutos por dia nos dias de trabalho (dias da semana ISO, "1"=seg … "7"=dom)
    daily_minutes: Mapped[int] = mapped_column(Integer)
    workdays: Mapped[str] = mapped_column(String)
