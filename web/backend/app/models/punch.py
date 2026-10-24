from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.employee import Employee


class PunchType(StrEnum):
    ENTRADA = "entrada"
    SAIDA = "saida"


class PunchSource(StrEnum):
    RELOGIO = "relogio"
    APP = "app"
    ADMIN = "admin"


class RequestAction(StrEnum):
    INCLUIR = "incluir"
    ALTERAR = "alterar"
    EXCLUIR = "excluir"


class RequestStatus(StrEnum):
    PENDENTE = "pendente"
    APROVADA = "aprovada"
    RECUSADA = "recusada"


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
    # Batida guardada no relógio sem conexão: o horário veio do aparelho e merece conferência
    offline: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("FALSE"))
    note: Mapped[str | None] = mapped_column(String)
    # Horário/tipo registrados pelo relógio, guardados na primeira correção feita pelo admin
    original_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    original_type: Mapped[str | None] = mapped_column(String)
    # Exclusão lógica: a batida some do espelho e das horas, mas continua no banco
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # De onde veio: relógio (tablet), app (celular) ou admin (lançamento manual)
    source: Mapped[str] = mapped_column(String, default=PunchSource.RELOGIO, server_default=PunchSource.RELOGIO)
    # Só nas batidas do celular: id gerado no aparelho (o reenvio não duplica), quando o servidor
    # recebeu (o horário da batida vem do aparelho), tempo desde o boot e nome do aparelho
    client_id: Mapped[str | None] = mapped_column(String, unique=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    device_uptime_ms: Mapped[int | None] = mapped_column(BigInteger)
    device: Mapped[str | None] = mapped_column(String)

    employee: Mapped["Employee"] = relationship(back_populates="punches")

    @property
    def public_id(self) -> str:
        """Id que o app enxerga: o UUID que ele mesmo gerou, ou "web-N" para as demais batidas."""
        return self.client_id or f"web-{self.id}"

    @property
    def clock_suspect(self) -> bool:
        """Horário do aparelho à frente do servidor: o relógio do celular provavelmente está errado."""
        return bool(self.received_at and self.ts - self.received_at > timedelta(minutes=1))

    @property
    def receipt(self) -> str:
        """Código do comprovante: só o sistema consegue gerar, então confirma que a batida é autêntica."""
        from app.core.security import receipt_code

        return receipt_code(self.id, self.employee_id, self.original_ts or self.ts)


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


class PunchRequest(Base):
    """Pedido do funcionário pelo app: incluir uma batida esquecida, alterar ou excluir uma batida.

    Nada muda no ponto até o admin aprovar; a aprovação passa pelas mesmas regras das correções do admin.
    """

    __tablename__ = "punch_requests"
    __table_args__ = (
        CheckConstraint("action IN ('incluir', 'alterar', 'excluir')", name="punch_requests_action_check"),
        CheckConstraint("status IN ('pendente', 'aprovada', 'recusada')", name="punch_requests_status_check"),
        Index("idx_punch_requests_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"))
    device_id: Mapped[int | None] = mapped_column(ForeignKey("employee_devices.id", ondelete="RESTRICT"))
    punch_id: Mapped[int | None] = mapped_column(ForeignKey("punches.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String)
    # Horário/tipo pedidos (incluir e alterar)
    ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    type: Mapped[str | None] = mapped_column(String)
    # Id gerado no celular para a batida a incluir (o reenvio do lote não duplica o pedido)
    client_id: Mapped[str | None] = mapped_column(String, unique=True)
    note: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default=RequestStatus.PENDENTE, server_default=RequestStatus.PENDENTE)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(String)
    decision_note: Mapped[str | None] = mapped_column(String)

    employee: Mapped["Employee"] = relationship()
    punch: Mapped[Punch | None] = relationship()
