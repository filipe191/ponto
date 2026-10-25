"""Aviso de privacidade (LGPD): público, sem dados de ninguém, só quem controla os dados e os prazos."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentAccess, DbSession
from app.core.config import settings
from app.services.auth_service import AuthService

router = APIRouter(tags=["privacidade"])


class PrivacyInfo(BaseModel):
    empresa: str  # controladora dos dados (cadastro da empresa)
    contato: str  # a quem pedir acesso, correção ou tirar dúvidas
    retention_years: int  # anos de guarda depois do desligamento


@router.get("/privacidade", response_model=PrivacyInfo)
def privacy(db: DbSession, access: CurrentAccess, e: str = ""):
    """A empresa vem do link público (`?e=<código>`, para o celular do funcionário), do relógio ou do admin
    logado neste aparelho; sem nenhum deles, a página usa o texto genérico."""
    auth = AuthService(db)
    company = auth.company_by_code(e.strip()[:64]) if e else auth.company(access.clock_company_id)
    return PrivacyInfo(
        empresa=company.name if company else "",
        contato=company.privacy_contact if company else "",
        retention_years=settings.retention_years,
    )
