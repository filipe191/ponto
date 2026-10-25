from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import ApiError, Forbidden, Unauthorized
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
    company_id: int | None  # empresa aberta no painel pelo admin
    kiosk_company_id: int | None  # empresa do aparelho liberado como relógio
    pending: str | None  # o que o admin precisa resolver antes de usar o painel ("senha" ou "2fa")

    @property
    def admin_user(self) -> str | None:
        return self.account.username if self.account else None

    @property
    def kiosk(self) -> bool:
        return self.kiosk_company_id is not None

    @property
    def clock_company_id(self) -> int | None:
        """Empresa da tela do relógio: a do aparelho liberado, ou a do admin logado nele."""
        return self.kiosk_company_id or self.company_id


def get_access(db: DbSession, session: SessionCookie = None, kiosk: KioskCookie = None) -> Access:
    auth = AuthService(db)
    found = auth.session_account(session)
    account, admin_session = found if found else (None, None)
    return Access(
        account=account,
        session=admin_session,
        company_id=auth.session_company(account, admin_session) if account else None,
        kiosk_company_id=auth.kiosk_company(kiosk),
        pending=auth.pending(account) if account else None,
    )


CurrentAccess = Annotated[Access, Depends(get_access)]


def require_clock(access: CurrentAccess) -> Access:
    """Tela do relógio: aparelho liberado como relógio ou admin logado (com uma empresa aberta)."""
    if not (access.account or access.kiosk):
        raise Unauthorized("Entre com seu usuário e senha para continuar")
    return access


def clock_company(access: Annotated[Access, Depends(require_clock)]) -> int:
    if not access.clock_company_id:
        raise _no_company()
    return access.clock_company_id


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


def _no_company() -> ApiError:
    return ApiError(409, "Escolha uma empresa para continuar", company_required=True)


@dataclass
class Tenant:
    """Admin sem pendência e a empresa aberta no painel: tudo o que ele vê e altera é dessa empresa."""

    company_id: int
    user: str


READ_METHODS = ("GET", "HEAD")


def require_company(request: Request, access: CurrentAccess, user: Annotated[str, Depends(require_admin)]) -> Tenant:
    if not access.company_id:
        raise _no_company()
    # Conta só de consulta: qualquer alteração na empresa é recusada aqui, não só escondida no painel
    if access.account.read_only and request.method not in READ_METHODS:
        raise Forbidden("Seu acesso é só de consulta: peça a um administrador da empresa para fazer essa alteração")
    return Tenant(company_id=access.company_id, user=user)


def require_superadmin(access: CurrentAccess, user: Annotated[str, Depends(require_admin)]) -> str:
    if not access.account.superadmin:
        raise Forbidden("Só o superadministrador pode fazer isso")
    return user


def require_super_company(
    tenant: Annotated[Tenant, Depends(require_company)], _user: Annotated[str, Depends(require_superadmin)]
) -> Tenant:
    """Superadmin com uma empresa aberta (ex.: mudar as regras de jornada dela)."""
    return tenant


AdminUser = Annotated[str, Depends(require_admin)]
AdminAccess = Annotated[Access, Depends(require_admin_session)]
CompanyAdmin = Annotated[Tenant, Depends(require_company)]
SuperAdmin = Annotated[str, Depends(require_superadmin)]
ClockCompany = Annotated[int, Depends(clock_company)]
SuperCompany = Annotated[Tenant, Depends(require_super_company)]


def client_ip(request: Request) -> str:
    """IP real do aparelho (o nginx manda no X-Forwarded-For e o uvicorn confia nele)."""
    return request.client.host if request.client else "?"
