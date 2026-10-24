"""Rotas da tela do relógio (aparelho liberado como relógio ou admin logado)."""

from fastapi import APIRouter, Depends, Request

from app.api.deps import ClockCompany, DbSession, client_ip, require_clock
from app.core.errors import NotFound, TooManyRequests
from app.core.ratelimit import EscalatingLimiter
from app.schemas.common import OkResponse
from app.schemas.punch import MyReportRequest, PunchRequest, PunchResult
from app.schemas.report import MonthReport
from app.services.audit import CLOCK_USER, PIN_BLOCKED, AuditLog
from app.services.calendar_service import PortalService
from app.services.punch_service import PunchService

router = APIRouter(tags=["relógio"], dependencies=[Depends(require_clock)])

# Dificulta adivinhar PINs no relógio: 10 PINs errados em 5 minutos pausam o aparelho por 5 minutos;
# cada nova rodada de erros dobra a pausa (10, 20, 40 min... até 24h). Cada bloqueio vai para a auditoria.
pin_attempts = EscalatingLimiter(
    max_attempts=10, window_seconds=300, base_block=300, max_block=86400, forget_after=86400
)


def _wait_text(seconds: int) -> str:
    minutes = -(-seconds // 60)
    if minutes < 60:
        return f"{minutes} minuto{'s' if minutes > 1 else ''}"
    hours = -(-minutes // 60)
    return f"{hours} hora{'s' if hours > 1 else ''}"


def _with_pin_limit(request: Request, db: DbSession, company_id: int, action):
    ip = client_ip(request)
    wait = pin_attempts.blocked_for(ip)
    if wait:
        raise TooManyRequests(f"Muitos PINs errados neste aparelho. Tente de novo em {_wait_text(wait)}.")
    try:
        return action()
    except NotFound:
        db.rollback()
        blocked = pin_attempts.fail(ip)
        if blocked:
            AuditLog(db, company_id).record(
                CLOCK_USER,
                PIN_BLOCKED,
                f"Relógio bloqueado por {_wait_text(blocked)} depois de vários PINs errados seguidos",
                details={"seconds": blocked},
                ip=ip,
            )
            db.commit()
        raise


@router.post("/punch", response_model=PunchResult, status_code=201)
def punch(body: PunchRequest, request: Request, db: DbSession, company_id: ClockCompany):
    return _with_pin_limit(
        request, db, company_id, lambda: PunchService(db, company_id).register(body.pin, body.offline_ts)
    )


# ---------- Espelho do próprio funcionário (com o PIN) ----------


@router.post("/portal/report", response_model=MonthReport)
def my_report(body: MyReportRequest, request: Request, db: DbSession, company_id: ClockCompany):
    return _with_pin_limit(
        request, db, company_id, lambda: PortalService(db, company_id).report(body.pin, body.month)
    )


@router.post("/portal/ack", response_model=OkResponse)
def acknowledge(body: MyReportRequest, request: Request, db: DbSession, company_id: ClockCompany):
    portal = PortalService(db, company_id)
    _with_pin_limit(request, db, company_id, lambda: portal.acknowledge(body.pin, body.month, client_ip(request)))
    return OkResponse()
