from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import Unauthorized
from app.core.security import KIOSK_COOKIE, SESSION_COOKIE
from app.db.session import get_db
from app.services.auth_service import AuthService

DbSession = Annotated[Session, Depends(get_db)]

SessionCookie = Annotated[str | None, Cookie(alias=SESSION_COOKIE)]
KioskCookie = Annotated[str | None, Cookie(alias=KIOSK_COOKIE)]


@dataclass
class Access:
    admin_user: str | None  # admin logado neste aparelho
    kiosk: bool  # aparelho liberado como relógio


def get_access(db: DbSession, session: SessionCookie = None, kiosk: KioskCookie = None) -> Access:
    auth = AuthService(db)
    return Access(admin_user=auth.session_user(session), kiosk=auth.is_kiosk(kiosk))


CurrentAccess = Annotated[Access, Depends(get_access)]


def require_clock(access: CurrentAccess) -> Access:
    """Tela do relógio: aparelho liberado como relógio ou admin logado."""
    if not (access.admin_user or access.kiosk):
        raise Unauthorized("Entre com seu usuário e senha para continuar")
    return access


def require_admin(access: CurrentAccess) -> str:
    if not access.admin_user:
        raise Unauthorized("Entre com a conta de administrador para continuar")
    return access.admin_user


AdminUser = Annotated[str, Depends(require_admin)]


def client_ip(request: Request) -> str:
    """IP real do aparelho (o nginx manda no X-Forwarded-For e o uvicorn confia nele)."""
    return request.client.host if request.client else "?"
