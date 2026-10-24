import hmac

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BadRequest, Unauthorized
from app.core.security import (
    ROLE_ADMIN,
    ROLE_KIOSK,
    create_session,
    hash_password,
    read_session,
    verify_password,
)
from app.models import AdminAccount
from app.repositories.admin_repository import AdminRepository

MIN_PASSWORD_LENGTH = 6


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AdminRepository(db)

    def ensure_account(self) -> None:
        """Na primeira subida, cria o login com ADMIN_USER/ADMIN_PASSWORD do .env."""
        if self.repo.get():
            return
        self.repo.add(
            AdminAccount(username=settings.admin_user, password_hash=hash_password(settings.admin_password))
        )
        self.db.commit()

    def account(self) -> AdminAccount:
        account = self.repo.get()
        if not account:
            raise Unauthorized()
        return account

    def check_credentials(self, user: str | None, password: str | None) -> AdminAccount | None:
        account = self.account()
        user_ok = hmac.compare_digest((user or "").encode(), account.username.encode())
        pass_ok = verify_password(password or "", account.password_hash)
        return account if user_ok and pass_ok else None

    def session_user(self, token: str | None) -> str | None:
        """Usuário do admin logado, ou None."""
        account = self.account()
        valid = read_session(token, ROLE_ADMIN, account.username, account.password_hash)
        return account.username if valid else None

    def is_kiosk(self, token: str | None) -> bool:
        """Diz se o aparelho está liberado como relógio de ponto."""
        account = self.account()
        return read_session(token, ROLE_KIOSK, account.username, account.password_hash)

    def new_session(self, account: AdminAccount, seconds: int) -> str:
        return create_session(ROLE_ADMIN, account.username, account.password_hash, seconds)

    def new_kiosk(self, account: AdminAccount) -> str:
        return create_session(ROLE_KIOSK, account.username, account.password_hash, settings.kiosk_days * 86400)

    def change_password(self, current: str, new: str) -> AdminAccount:
        account = self.account()
        if not verify_password(current, account.password_hash):
            raise BadRequest("Senha atual incorreta")
        if len(new) < MIN_PASSWORD_LENGTH:
            raise BadRequest(f"A nova senha deve ter pelo menos {MIN_PASSWORD_LENGTH} caracteres")
        if new == current:
            raise BadRequest("A nova senha deve ser diferente da atual")
        account.password_hash = hash_password(new)
        self.db.commit()
        return account
