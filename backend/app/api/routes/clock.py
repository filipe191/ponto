"""Rotas da tela do relógio (aparelho liberado como relógio ou admin logado)."""

from fastapi import APIRouter, Depends, Request

from app.api.deps import DbSession, client_ip, require_clock
from app.core.errors import NotFound, TooManyRequests
from app.core.ratelimit import AttemptLimiter
from app.schemas.punch import PunchRequest, PunchResult, TodayPunch
from app.services.punch_service import PunchService

router = APIRouter(tags=["relógio"], dependencies=[Depends(require_clock)])

# Dificulta adivinhar PINs no relógio: 10 PINs errados em 5 minutos pausam o aparelho
pin_attempts = AttemptLimiter(max_attempts=10, window_seconds=300)


@router.post("/punch", response_model=PunchResult, status_code=201)
def punch(body: PunchRequest, request: Request, db: DbSession):
    ip = client_ip(request)
    if pin_attempts.blocked(ip):
        raise TooManyRequests("Muitos PINs errados neste aparelho. Aguarde alguns minutos e tente de novo.")
    try:
        return PunchService(db).register(body.pin)
    except NotFound:
        pin_attempts.fail(ip)
        raise


@router.get("/today", response_model=list[TodayPunch])
def today(db: DbSession):
    return PunchService(db).today()
