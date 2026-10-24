"""Rotas da tela do relógio (aparelho liberado como relógio ou admin logado)."""

from fastapi import APIRouter, Depends, Request

from app.api.deps import DbSession, client_ip, require_clock
from app.core.errors import NotFound, TooManyRequests
from app.core.ratelimit import AttemptLimiter
from app.schemas.common import OkResponse
from app.schemas.punch import MyReportRequest, PunchRequest, PunchResult, TodayPunch
from app.schemas.report import MonthReport
from app.services.calendar_service import PortalService
from app.services.punch_service import PunchService

router = APIRouter(tags=["relógio"], dependencies=[Depends(require_clock)])

# Dificulta adivinhar PINs no relógio: 10 PINs errados em 5 minutos pausam o aparelho
pin_attempts = AttemptLimiter(max_attempts=10, window_seconds=300)


def _with_pin_limit(request: Request, action):
    ip = client_ip(request)
    if pin_attempts.blocked(ip):
        raise TooManyRequests("Muitos PINs errados neste aparelho. Aguarde alguns minutos e tente de novo.")
    try:
        return action()
    except NotFound:
        pin_attempts.fail(ip)
        raise


@router.post("/punch", response_model=PunchResult, status_code=201)
def punch(body: PunchRequest, request: Request, db: DbSession):
    return _with_pin_limit(request, lambda: PunchService(db).register(body.pin, body.offline_ts))


@router.get("/today", response_model=list[TodayPunch])
def today(db: DbSession):
    return PunchService(db).today()


# ---------- Espelho do próprio funcionário (com o PIN) ----------


@router.post("/portal/report", response_model=MonthReport)
def my_report(body: MyReportRequest, request: Request, db: DbSession):
    return _with_pin_limit(request, lambda: PortalService(db).report(body.pin, body.month))


@router.post("/portal/ack", response_model=OkResponse)
def acknowledge(body: MyReportRequest, request: Request, db: DbSession):
    _with_pin_limit(request, lambda: PortalService(db).acknowledge(body.pin, body.month))
    return OkResponse()
