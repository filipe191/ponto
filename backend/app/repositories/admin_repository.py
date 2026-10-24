from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AdminAccount


class AdminRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self) -> AdminAccount | None:
        return self.db.scalar(select(AdminAccount).order_by(AdminAccount.id).limit(1))

    def add(self, account: AdminAccount) -> AdminAccount:
        self.db.add(account)
        self.db.flush()
        return account
