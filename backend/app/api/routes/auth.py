"""Login do admin e liberação de aparelhos como relógio, em cookies HttpOnly."""

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from app.api.deps import AdminUser, CurrentAccess, DbSession, client_ip, require_admin, require_clock
from app.core.config import settings
from app.core.errors import TooManyRequests, Unauthorized
from app.core.ratelimit import AttemptLimiter
from app.core.security import KIOSK_COOKIE, SESSION_COOKIE
from app.models import AdminAccount
from app.schemas.common import OkResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["login"])

# 5 senhas erradas em 5 minutos bloqueiam o IP até a janela passar
login_attempts = AttemptLimiter(max_attempts=5, window_seconds=300)


class LoginRequest(BaseModel):
    username: str = ""
    password: str = ""


class PasswordChange(BaseModel):
    current_password: str = ""
    new_password: str = ""


class Me(BaseModel):
    user: str | None  # admin logado, ou None quando é só o relógio
    admin: bool
    kiosk: bool


def _set_cookie(response: Response, name: str, token: str, seconds: int) -> None:
    response.set_cookie(
        name,
        token,
        max_age=seconds,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def _start_admin_session(response: Response, auth: AuthService, account: AdminAccount, on_kiosk: bool) -> None:
    # No aparelho do relógio o login do admin dura pouco, para não ficar aberto aos funcionários
    seconds = settings.admin_on_kiosk_minutes * 60 if on_kiosk else settings.session_days * 86400
    _set_cookie(response, SESSION_COOKIE, auth.new_session(account, seconds), seconds)


@router.post("/login", response_model=OkResponse)
def login(body: LoginRequest, request: Request, response: Response, db: DbSession, access: CurrentAccess):
    ip = client_ip(request)
    if login_attempts.blocked(ip):
        raise TooManyRequests("Muitas tentativas erradas. Aguarde alguns minutos e tente de novo.")
    auth = AuthService(db)
    account = auth.authenticate(body.username.strip(), body.password)
    if not account:
        login_attempts.fail(ip)
        raise Unauthorized()
    login_attempts.reset(ip)
    _start_admin_session(response, auth, account, on_kiosk=access.kiosk)
    return OkResponse()


@router.post("/logout", response_model=OkResponse)
def logout(response: Response):
    """Sai da conta do admin; se o aparelho for um relógio, ele continua funcionando."""
    response.delete_cookie(SESSION_COOKIE, path="/")
    return OkResponse()


@router.get("/me", response_model=Me, dependencies=[Depends(require_clock)])
def me(access: CurrentAccess):
    """Usado também pelo nginx (auth_request) para proteger a tela do relógio."""
    return Me(user=access.admin_user, admin=bool(access.admin_user), kiosk=access.kiosk)


@router.get("/admin", response_model=Me, dependencies=[Depends(require_admin)])
def admin_me(access: CurrentAccess):
    """Usado pelo nginx (auth_request) para proteger /admin e /senha."""
    return Me(user=access.admin_user, admin=True, kiosk=access.kiosk)


@router.post("/kiosk", response_model=OkResponse, dependencies=[Depends(require_admin)])
def enable_kiosk(response: Response, db: DbSession):
    """Libera este aparelho como relógio e desconecta o admin dele."""
    _set_cookie(response, KIOSK_COOKIE, AuthService(db).new_kiosk(), settings.kiosk_days * 86400)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return OkResponse()


@router.delete("/kiosk", response_model=OkResponse, dependencies=[Depends(require_admin)])
def disable_kiosk(response: Response):
    response.delete_cookie(KIOSK_COOKIE, path="/")
    return OkResponse()


@router.post("/password", response_model=OkResponse)
def change_password(body: PasswordChange, response: Response, db: DbSession, access: CurrentAccess, user: AdminUser):
    """Troca a senha do admin logado; as outras sessões dele caem e esta recebe um cookie novo."""
    auth = AuthService(db)
    account = auth.change_password(user, body.current_password, body.new_password)
    _start_admin_session(response, auth, account, on_kiosk=access.kiosk)
    return OkResponse()
