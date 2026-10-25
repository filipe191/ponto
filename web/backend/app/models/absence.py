from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Tipo → (nome, abona). Abona: o dia conta como jornada cumprida (atestado, férias, licença, faltas
# legais da CLT art. 473). Folga do banco: o dia não é falta, mas a jornada sai do banco de horas.
ABSENCE_KINDS: dict[str, tuple[str, bool]] = {
    "atestado": ("Atestado médico", True),
    "ferias": ("Férias", True),
    "licenca": ("Licença", True),
    "abonada": ("Falta abonada", True),
    "folga": ("Folga do banco de horas", False),
}


class Absence(Base):
    """Ausência justificada de um funcionário, de `first_day` a `last_day` (inclusive).

    `minutes` vazio = dias inteiros; preenchido = só essas horas por dia são abonadas (ex.: consulta de 2h).
    """

    __tablename__ = "absences"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"), index=True)
    kind: Mapped[str] = mapped_column(String)
    first_day: Mapped[date] = mapped_column(Date)
    last_day: Mapped[date] = mapped_column(Date)
    minutes: Mapped[int | None] = mapped_column(Integer)
    # Sem diagnóstico (CID): é dado de saúde e só o necessário fica no sistema (LGPD)
    note: Mapped[str] = mapped_column(String, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str] = mapped_column(String)

    @property
    def label(self) -> str:
        return ABSENCE_KINDS[self.kind][0]

    @property
    def credits(self) -> bool:
        return ABSENCE_KINDS[self.kind][1]
