from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.punch import Punch


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    pin_hash: Mapped[str] = mapped_column(String, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Jornada prevista: minutos por dia nos dias de trabalho (dias da semana ISO, "1"=seg … "7"=dom)
    daily_minutes: Mapped[int] = mapped_column(Integer, default=480, server_default=text("480"))
    workdays: Mapped[str] = mapped_column(String, default="12345", server_default=text("'12345'"))

    # Batidas nunca são apagadas junto com o funcionário (o banco recusa, ver EmployeeService.delete)
    punches: Mapped[list["Punch"]] = relationship(back_populates="employee", passive_deletes="all")
