from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditEvent(Base):
    """Quem fez o quê e quando, com o antes e o depois. O banco recusa alterar ou apagar (ver migração 0006)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Admin que fez a ação, ou "relógio" / "funcionário" para o que acontece na tela do relógio
    user: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)  # ex.: "funcionario.alterado", "mes.reaberto"
    summary: Mapped[str] = mapped_column(String)  # frase pronta para mostrar no painel
    employee_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String)
