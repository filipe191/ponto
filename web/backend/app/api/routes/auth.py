"""Login do admin (senha + código do app autenticador), sessões e liberação de aparelhos como relógio."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from app.api.deps import AdminAccess, AdminUser, CurrentAccess, DbSession, client_ip, require_clock
from app.core.config import settings
from app.core.errors import TooManyRequests, Unauthorized
from app.core.passwords import MIN_LENGTH
from app.core.ratelimit import AttemptLimiter
from app.core.security import KIOSK_COOKIE, SESSION_COOKIE
from app.schemas.common import OkResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["login"])

# 5 tentativas erradas (senha ou código) em 5 minutos bloqueiam o IP até a janela passar
login_attempts = AttemptLimiter(max_attempts=5, window_seconds=300)


class LoginRequest(BaseModel):
    username: str = ""
    password: str = ""
    code: str = ""  # código do app autenticador ou de recuperação


class PasswordChange(BaseModel):
    current_password: str = ""
    new_password: str = ""


class Me(BaseModel):
    user: str | None  # admin logado, ou None quando é só o relógio
    admin: bool
    kiosk: bool
    pending: str | None = None  # "senha" ou "2fa": o que falta resolver antes de usar o painel


class SessionOut(BaseModel):
    id: int
    created_at: datetime
    last_seen_at: datetime
    ip: str | None
    user_agent: str | None
    current: bool


class TwoFactorStatus(BaseModel):
    enabled: bool
    required: bool
    recovery_codes_left: int
    min_password_length: int = MIN_LENGTH


class TwoFactorSetup(BaseModel):
    secret: str
    uri: str
    qr: str  # imagem do QR code (data URI SVG)


class CodeRequest(BaseModel):
    code: str = ""


class DisableRequest(BaseModel):
    password: str = ""
    code: str = ""


class RecoveryCodes(BaseModel):
    codes: list[str]


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


@router.post("/login", response_model=Me)
def login(body: LoginRequest, request: Request, response: Response, db: DbSession, access: CurrentAccess):
    ip = client_ip(request)
    if login_attempts.blocked(ip):
        raise TooManyRequests("Muitas tentativas erradas. Aguarde alguns minutos e tente de novo.")
    auth = AuthService(db)
    account = auth.authenticate(body.username.strip(), body.password, ip)
    if not account:
        login_attempts.fail(ip)
        raise Unauthorized()
    if account.totp_secret:
        if not body.code.strip():
            login_attempts.fail(ip)  # conta como tentativa: não dá para testar senhas de graça
            raise Unauthorized("Digite o código do app autenticador", otp_required=True)
        if not auth.check_second_factor(account, body.code):
            login_attempts.fail(ip)
            auth.log_login(account, False, ip, "código de verificação errado")
            raise Unauthorized("Código inválido", otp_required=True)
    login_attempts.reset(ip)
    auth.log_login(account, True, ip)
    # No aparelho do relógio o login do admin dura pouco, para não ficar aberto aos funcionários
    seconds = settings.admin_on_kiosk_minutes * 60 if access.kiosk else settings.session_days * 86400
    token = auth.start_session(account, seconds, ip, request.headers.get("user-agent"))
    _set_cookie(response, SESSION_COOKIE, token, seconds)
    return Me(user=account.username, admin=True, kiosk=access.kiosk, pending=auth.pending(account))


@router.post("/logout", response_model=OkResponse)
def logout(request: Request, response: Response, db: DbSession):
    """Encerra a sessão no servidor; se o aparelho for um relógio, ele continua funcionando."""
    AuthService(db).end_session(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return OkResponse()


@router.get("/me", response_model=Me, dependencies=[Depends(require_clock)])
def me(access: CurrentAccess):
    """Usado também pelo nginx (auth_request) para proteger a tela do relógio."""
    return Me(user=access.admin_user, admin=bool(access.account), kiosk=access.kiosk, pending=access.pending)


@router.get("/admin", response_model=Me)
def admin_me(access: AdminAccess):
    """Usado pelo nginx (auth_request) para proteger /admin e /senha (abre mesmo com pendência)."""
    return Me(user=access.admin_user, admin=True, kiosk=access.kiosk, pending=access.pending)


@router.post("/kiosk", response_model=OkResponse)
def enable_kiosk(request: Request, response: Response, db: DbSession, user: AdminUser):
    """Libera este aparelho como relógio e desconecta o admin dele."""
    auth = AuthService(db)
    _set_cookie(response, KIOSK_COOKIE, auth.new_kiosk(user, client_ip(request)), settings.kiosk_days * 86400)
    auth.end_session(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return OkResponse()


@router.delete("/kiosk", response_model=OkResponse)
def disable_kiosk(request: Request, response: Response, db: DbSession, user: AdminUser):
    AuthService(db).kiosk_disabled(user, client_ip(request))
    response.delete_cookie(KIOSK_COOKIE, path="/")
    return OkResponse()


@router.post("/password", response_model=OkResponse)
def change_password(body: PasswordChange, db: DbSession, access: AdminAccess):
    """Troca a senha do admin logado; as outras sessões dele caem, esta continua."""
    AuthService(db).change_password(access.account, body.current_password, body.new_password, access.session)
    return OkResponse()


# ---------- Sessões abertas ----------


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(db: DbSession, access: AdminAccess):
    return [
        SessionOut(
            id=s.id,
            created_at=s.created_at,
            last_seen_at=s.last_seen_at,
            ip=s.ip,
            user_agent=s.user_agent,
            current=s.id == access.session.id,
        )
        for s in AuthService(db).list_sessions(access.account)
    ]


@router.delete("/sessions/{session_id}", response_model=OkResponse)
def end_session(session_id: int, db: DbSession, access: AdminAccess):
    AuthService(db).end_session_by_id(access.account, session_id)
    return OkResponse()


@router.post("/sessions/end-others", response_model=OkResponse)
def end_other_sessions(db: DbSession, access: AdminAccess):
    """Sai de todos os outros aparelhos."""
    AuthService(db).end_other_sessions(access.account, access.session)
    return OkResponse()


# ---------- Verificação em duas etapas ----------


@router.get("/2fa", response_model=TwoFactorStatus)
def two_factor_status(db: DbSession, access: AdminAccess):
    return TwoFactorStatus(
        enabled=bool(access.account.totp_secret),
        required=settings.admin_2fa_required,
        recovery_codes_left=AuthService(db).recovery_codes_left(access.account),
    )


@router.post("/2fa/setup", response_model=TwoFactorSetup)
def two_factor_setup(db: DbSession, access: AdminAccess):
    return AuthService(db).totp_setup(access.account)


@router.post("/2fa/enable", response_model=RecoveryCodes)
def two_factor_enable(body: CodeRequest, db: DbSession, access: AdminAccess):
    """Confirma o app autenticador; devolve os códigos de recuperação (mostrados uma única vez)."""
    return RecoveryCodes(codes=AuthService(db).totp_enable(access.account, body.code))


@router.post("/2fa/disable", response_model=OkResponse)
def two_factor_disable(body: DisableRequest, db: DbSession, access: AdminAccess):
    AuthService(db).totp_disable(access.account, body.password, body.code)
    return OkResponse()


@router.post("/2fa/recovery", response_model=RecoveryCodes)
def two_factor_new_recovery(body: CodeRequest, db: DbSession, access: AdminAccess):
    """Gera códigos de recuperação novos (os anteriores deixam de valer)."""
    return RecoveryCodes(codes=AuthService(db).new_recovery_codes(access.account, body.code))
