from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AttemptFailure(Base):
    """Uma tentativa errada (PIN no relógio, senha no login, chave no app), para o limite de tentativas.

    Fica no banco para que reiniciar o backend não zere os bloqueios em andamento.
    """

    __tablename__ = "attempt_failures"
    __table_args__ = (Index("attempt_failures_scope_key_at_idx", "scope", "key", "at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String)  # pin, login, celular
    key: Mapped[str] = mapped_column(String)  # IP do aparelho
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AttemptBlock(Base):
    """Bloqueio crescente em andamento: quantos seguidos e até quando vale o último."""

    __tablename__ = "attempt_blocks"

    scope: Mapped[str] = mapped_column(String, primary_key=True)
    key: Mapped[str] = mapped_column(String, primary_key=True)
    strikes: Mapped[int] = mapped_column(Integer)
    until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
