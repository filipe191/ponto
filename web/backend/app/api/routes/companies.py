"""Cadastro das empresas atendidas pelo sistema (só o superadministrador)."""

from fastapi import APIRouter, Depends

from app.api.deps import DbSession, SuperAdmin, require_superadmin
from app.schemas.admin import CompanyCreate, CompanyOut, CompanyUpdate
from app.services.auth_service import AuthService

router = APIRouter(prefix="/companies", tags=["empresas"], dependencies=[Depends(require_superadmin)])


@router.get("", response_model=list[CompanyOut])
def list_companies(db: DbSession):
    return AuthService(db).list_companies()


@router.post("", response_model=CompanyOut, status_code=201)
def create_company(body: CompanyCreate, db: DbSession, user: SuperAdmin):
    return AuthService(db).create_company(
        body.name, body.privacy_contact, body.admin_username, body.admin_password, user
    )


@router.patch("/{company_id}", response_model=CompanyOut)
def update_company(company_id: int, body: CompanyUpdate, db: DbSession, user: SuperAdmin):
    return AuthService(db).update_company(company_id, user, body.name, body.privacy_contact, body.active)
