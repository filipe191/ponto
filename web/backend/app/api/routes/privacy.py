"""Aviso de privacidade (LGPD): público, sem dados de ninguém, só quem controla os dados e os prazos."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(tags=["privacidade"])


class PrivacyInfo(BaseModel):
    empresa: str  # controladora dos dados (EMPRESA_NOME no .env)
    contato: str  # a quem pedir acesso, correção ou tirar dúvidas (PRIVACIDADE_CONTATO)
    retention_years: int  # anos de guarda depois do desligamento


@router.get("/privacidade", response_model=PrivacyInfo)
def privacy():
    return PrivacyInfo(
        empresa=settings.empresa_nome,
        contato=settings.privacidade_contato,
        retention_years=settings.retention_years,
    )
