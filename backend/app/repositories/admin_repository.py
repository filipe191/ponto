from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AdminAccount, AppSetting


class AdminRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, admin_id: int) -> AdminAccount | None:
        return self.db.get(AdminAccount, admin_id)

    def get_by_username(self, username: str) -> AdminAccount | None:
        return self.db.scalar(select(AdminAccount).where(AdminAccount.username == username))

    def list(self) -> list[AdminAccount]:
        return list(self.db.scalars(select(AdminAccount).order_by(AdminAccount.username)))

    def count(self) -> int:
        return self.db.scalar(select(func.count()).select_from(AdminAccount)) or 0

    def add(self, account: AdminAccount) -> AdminAccount:
        self.db.add(account)
        self.db.flush()
        return account

    def delete(self, account: AdminAccount) -> None:
        self.db.delete(account)

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
