from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdminAccount(Base):
    """Login de um administrador. O primeiro é criado a partir do .env na primeira subida."""

    __tablename__ = "admin_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Empresa que o admin administra. O superadmin cria e administra todas e escolhe uma por vez
    # no painel; a dele (se houver) é só a que abre ao entrar.
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="RESTRICT"))
    superadmin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("FALSE"))
    username: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Senha fora da política (ex.: a inicial do .env, ou criada por outro admin): trocar antes de usar o painel
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("FALSE"))
    # Verificação em duas etapas: segredo cifrado (ver core/twofactor.py), o pendente de confirmação
    # e o último passo de tempo usado (um código não pode ser reaproveitado)
    totp_secret: Mapped[str | None] = mapped_column(String)
    totp_pending: Mapped[str | None] = mapped_column(String)
    totp_last_step: Mapped[int | None] = mapped_column(BigInteger)


class AdminSession(Base):
    """Sessão de um admin guardada no servidor: sair, trocar a senha ou encerrar a invalida na hora."""

    __tablename__ = "admin_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admin_account.id", ondelete="CASCADE"))
    # Empresa aberta no painel nesta sessão (só o superadmin troca)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    token_hash: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String)
    user_agent: Mapped[str | None] = mapped_column(String)


class AdminRecoveryCode(Base):
    """Código de recuperação de uso único, para entrar quando o celular com o autenticador se perder."""

    __tablename__ = "admin_recovery_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admin_account.id", ondelete="CASCADE"))
    code_hash: Mapped[str] = mapped_column(String)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
