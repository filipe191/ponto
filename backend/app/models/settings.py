from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AppSetting(Base):
    """Valores gerados pelo próprio sistema (ex.: segredo que assina os relógios)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)


class Holiday(Base):
    """Feriado cadastrado pelo admin (municipal, estadual, ponto facultativo...).

    Os feriados nacionais são calculados em app/utils/holidays.py e não ficam no banco.
    """

    __tablename__ = "holidays"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    name: Mapped[str] = mapped_column(String)


class MonthClosure(Base):
    """Mês fechado (conferido) de um funcionário: as batidas desse mês não podem mais ser alteradas."""

    __tablename__ = "month_closures"

    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"), primary_key=True)
    month: Mapped[str] = mapped_column(String, primary_key=True)  # AAAA-MM
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_by: Mapped[str] = mapped_column(String)
    # Ciência do funcionário, dada no relógio com o PIN
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
