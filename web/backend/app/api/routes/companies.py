"""Cadastro das empresas e auditoria do sistema (só o superadministrador)."""

from fastapi import APIRouter, Depends

from app.api.deps import DbSession, SuperAdmin, require_superadmin
from app.schemas.admin import AuditOut, CompanyCreate, CompanyOut, CompanyUpdate
from app.services.audit import AuditLog
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


# ---------- Auditoria do sistema ----------


@router.get("/audit", response_model=list[AuditOut])
def system_audit(db: DbSession, action: str = "", before: int = 0, limit: int = 50):
    """O que os superadmins fizeram fora das empresas: logins, conta, empresas e superadmins."""
    return AuditLog(db, None).list(None, action, before or None, limit)
