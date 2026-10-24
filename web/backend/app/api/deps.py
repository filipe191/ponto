from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import Forbidden, Unauthorized
from app.core.security import KIOSK_COOKIE, SESSION_COOKIE
from app.db.session import get_db
from app.models import AdminAccount, AdminSession
from app.services.auth_service import PENDING_2FA, AuthService

DbSession = Annotated[Session, Depends(get_db)]

SessionCookie = Annotated[str | None, Cookie(alias=SESSION_COOKIE)]
KioskCookie = Annotated[str | None, Cookie(alias=KIOSK_COOKIE)]


@dataclass
class Access:
    account: AdminAccount | None  # admin logado neste aparelho
    session: AdminSession | None
    kiosk: bool  # aparelho liberado como relógio
    pending: str | None  # o que o admin precisa resolver antes de usar o painel ("senha" ou "2fa")

    @property
    def admin_user(self) -> str | None:
        return self.account.username if self.account else None


def get_access(db: DbSession, session: SessionCookie = None, kiosk: KioskCookie = None) -> Access:
    auth = AuthService(db)
    found = auth.session_account(session)
    account, admin_session = found if found else (None, None)
    return Access(
        account=account,
        session=admin_session,
        kiosk=auth.is_kiosk(kiosk),
        pending=auth.pending(account) if account else None,
    )


CurrentAccess = Annotated[Access, Depends(get_access)]


def require_clock(access: CurrentAccess) -> Access:
    """Tela do relógio: aparelho liberado como relógio ou admin logado."""
    if not (access.account or access.kiosk):
        raise Unauthorized("Entre com seu usuário e senha para continuar")
    return access


def require_admin_session(access: CurrentAccess) -> Access:
    """Admin logado, mesmo com pendência: usado nas rotas que resolvem a pendência (senha, duas etapas)."""
    if not access.account:
        raise Unauthorized("Entre com a conta de administrador para continuar")
    return access


def require_admin(access: CurrentAccess) -> str:
    """Admin logado e sem pendência: o painel só abre depois de trocar a senha fraca e ativar as duas etapas."""
    if not access.account:
        raise Unauthorized("Entre com a conta de administrador para continuar")
    if access.pending:
        message = (
            "Ative a verificação em duas etapas para continuar"
            if access.pending == PENDING_2FA
            else "Troque sua senha para continuar"
        )
        raise Forbidden(message, pending=access.pending)
    return access.admin_user


AdminUser = Annotated[str, Depends(require_admin)]
AdminAccess = Annotated[Access, Depends(require_admin_session)]


def client_ip(request: Request) -> str:
    """IP real do aparelho (o nginx manda no X-Forwarded-For e o uvicorn confia nele)."""
    return request.client.host if request.client else "?"
