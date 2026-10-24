from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.employee import Employee


class PunchType(StrEnum):
    ENTRADA = "entrada"
    SAIDA = "saida"


class PunchAction(StrEnum):
    CRIADA = "criada"
    ALTERADA = "alterada"
    EXCLUIDA = "excluida"
    RESTAURADA = "restaurada"


class Punch(Base):
    """Batida de ponto. Nunca é apagada nem perde o horário original: correções ficam registradas."""

    __tablename__ = "punches"
    __table_args__ = (
        CheckConstraint("type IN ('entrada', 'saida')", name="punches_type_check"),
        Index("idx_punches_emp_ts", "employee_id", "ts"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    type: Mapped[str] = mapped_column(String)
    manual: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("FALSE"))
    note: Mapped[str | None] = mapped_column(String)
    # Horário/tipo registrados pelo relógio, guardados na primeira correção feita pelo admin
    original_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    original_type: Mapped[str | None] = mapped_column(String)
    # Exclusão lógica: a batida some do espelho e das horas, mas continua no banco
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    employee: Mapped["Employee"] = relationship(back_populates="punches")


class PunchChange(Base):
    """Histórico de tudo que o admin fez numa batida (quem, quando, antes e depois)."""

    __tablename__ = "punch_changes"
    __table_args__ = (
        CheckConstraint(
            "action IN ('criada', 'alterada', 'excluida', 'restaurada')", name="punch_changes_action_check"
        ),
        Index("idx_punch_changes_punch", "punch_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    punch_id: Mapped[int] = mapped_column(ForeignKey("punches.id", ondelete="RESTRICT"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    old_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    old_type: Mapped[str | None] = mapped_column(String)
    new_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    new_type: Mapped[str | None] = mapped_column(String)
    note: Mapped[str | None] = mapped_column(String)
