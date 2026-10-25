"""Rotas do app de celular (app/), no mesmo contrato do antigo backend Spring.

Autenticação pelo cabeçalho X-API-Key: a chave de celular gerada pelo admin para cada funcionário.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response

from app.api.deps import DbSession, client_ip
from app.core.errors import TooManyRequests, Unauthorized
from app.core.ratelimit import AttemptLimiter
from app.schemas.mobile import AjusteRequest, BatidaServidor, LoteRequest, LoteResponse, ResumoMes
from app.services.mobile_service import DeviceService, MobileService

router = APIRouter(prefix="/pontos", tags=["app de celular"])

# Chave errada repetida: 10 em 5 minutos bloqueiam o IP
key_attempts = AttemptLimiter("celular", max_attempts=10, window_seconds=300)


def mobile(request: Request, db: DbSession, x_api_key: Annotated[str | None, Header()] = None) -> MobileService:
    ip = client_ip(request)
    if key_attempts.blocked(ip):
        raise TooManyRequests("Muitas tentativas com chave errada. Aguarde alguns minutos.")
    try:
        employee, device = DeviceService(db).authenticate(x_api_key)
    except Unauthorized:
        key_attempts.fail(ip)
        raise
    return MobileService(db, employee, device)


App = Annotated[MobileService, Depends(mobile)]


@router.post("/lote", response_model=LoteResponse)
def sync(body: LoteRequest, app: App):
    return app.sync(body.batidas)


@router.get("/ultima", response_model=BatidaServidor | None)
def last(app: App):
    return app.last()


@router.get("/resumo", response_model=ResumoMes)
def summary(app: App, mes: str = ""):
    return app.summary(mes)


@router.get("", response_model=list[BatidaServidor])
def between(app: App, inicio: date, fim: date):
    return app.between(inicio, fim)


@router.patch("/{public_id}", response_model=BatidaServidor)
def request_change(public_id: str, body: AjusteRequest, app: App):
    """Vira uma solicitação para o admin: a batida devolvida ainda é a atual."""
    return app.request_change(public_id, body)


@router.delete("/{public_id}", status_code=204)
def request_delete(public_id: str, app: App):
    """Vira uma solicitação de exclusão para o admin."""
    app.request_delete(public_id)
    return Response(status_code=204)
