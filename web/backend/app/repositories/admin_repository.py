from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import AdminAccount, AdminRecoveryCode, AdminSession, AppSetting, Company


class AdminRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, admin_id: int) -> AdminAccount | None:
        return self.db.get(AdminAccount, admin_id)

    def get_by_username(self, username: str) -> AdminAccount | None:
        return self.db.scalar(select(AdminAccount).where(AdminAccount.username == username))

    def list(self, company_id: int) -> list[AdminAccount]:
        return list(
            self.db.scalars(
                select(AdminAccount).where(AdminAccount.company_id == company_id).order_by(AdminAccount.username)
            )
        )

    def superadmins(self) -> list[AdminAccount]:
        query = select(AdminAccount).where(AdminAccount.superadmin).order_by(AdminAccount.username)
        return list(self.db.scalars(query))

    def count(self, company_id: int | None = None) -> int:
        """Admins da empresa (ou de todo o sistema, sem empresa)."""
        query = select(func.count()).select_from(AdminAccount)
        if company_id is not None:
            query = query.where(AdminAccount.company_id == company_id)
        return self.db.scalar(query) or 0

    def add(self, account: AdminAccount) -> AdminAccount:
        self.db.add(account)
        self.db.flush()
        return account

    def delete(self, account: AdminAccount) -> None:
        self.db.delete(account)

    # ---------- Sessões ----------

    def session_by_hash(self, token_hash: str) -> AdminSession | None:
        return self.db.scalar(select(AdminSession).where(AdminSession.token_hash == token_hash))

    def add_session(self, session: AdminSession) -> AdminSession:
        self.db.add(session)
        self.db.flush()
        return session

    def active_sessions(self, admin_id: int, now: datetime) -> list[AdminSession]:
        return list(
            self.db.scalars(
                select(AdminSession)
                .where(AdminSession.admin_id == admin_id, AdminSession.revoked_at.is_(None), AdminSession.expires_at > now)
                .order_by(AdminSession.last_seen_at.desc())
            )
        )

    def revoke_sessions(self, admin_id: int, now: datetime, keep_id: int | None = None) -> None:
        query = update(AdminSession).where(AdminSession.admin_id == admin_id, AdminSession.revoked_at.is_(None))
        if keep_id is not None:
            query = query.where(AdminSession.id != keep_id)
        self.db.execute(query.values(revoked_at=now))

    # ---------- Códigos de recuperação ----------

    def unused_recovery_code(self, admin_id: int, code_hash: str) -> AdminRecoveryCode | None:
        return self.db.scalar(
            select(AdminRecoveryCode).where(
                AdminRecoveryCode.admin_id == admin_id,
                AdminRecoveryCode.code_hash == code_hash,
                AdminRecoveryCode.used_at.is_(None),
            )
        )

    def recovery_codes_left(self, admin_id: int) -> int:
        return self.db.scalar(
            select(func.count())
            .select_from(AdminRecoveryCode)
            .where(AdminRecoveryCode.admin_id == admin_id, AdminRecoveryCode.used_at.is_(None))
        ) or 0

    def replace_recovery_codes(self, admin_id: int, hashes: list[str]) -> None:
        self.db.query(AdminRecoveryCode).filter(AdminRecoveryCode.admin_id == admin_id).delete()
        self.db.add_all(AdminRecoveryCode(admin_id=admin_id, code_hash=h) for h in hashes)

    # ---------- Empresas ----------

    def company(self, company_id: int | None) -> Company | None:
        return self.db.get(Company, company_id) if company_id else None

    def companies(self) -> list[Company]:
        return list(self.db.scalars(select(Company).order_by(Company.name, Company.id)))

    def first_active_company(self) -> Company | None:
        return self.db.scalar(select(Company).where(Company.active).order_by(Company.id).limit(1))

    def add_company(self, company: Company) -> Company:
        self.db.add(company)
        self.db.flush()
        return company

    # ---------- Valores do sistema ----------

    def setting(self, key: str) -> str | None:
        row = self.db.get(AppSetting, key)
        return row.value if row else None

    def set_setting(self, key: str, value: str) -> None:
        row = self.db.get(AppSetting, key)
        if row:
            row.value = value
        else:
            self.db.add(AppSetting(key=key, value=value))
