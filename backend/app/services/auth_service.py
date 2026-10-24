import secrets

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BadRequest, Conflict, NotFound
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
KIOSK_SECRET = "kiosk_secret"
KIOSK_SUBJECT = "relogio"
# Hash de uma senha qualquer: usuário inexistente gasta o mesmo tempo que senha errada
_DUMMY_HASH = hash_password(secrets.token_hex(8))


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AdminRepository(db)

    def ensure_setup(self) -> None:
        """Na primeira subida, cria o login com ADMIN_USER/ADMIN_PASSWORD do .env e o segredo dos relógios."""
        if not self.repo.count():
            self.repo.add(
                AdminAccount(username=settings.admin_user, password_hash=hash_password(settings.admin_password))
            )
        if not self.repo.setting(KIOSK_SECRET):
            self.repo.set_setting(KIOSK_SECRET, secrets.token_hex(32))
        self.db.commit()

    # ---------- Login do admin ----------

    def authenticate(self, username: str, password: str) -> AdminAccount | None:
        account = self.repo.get_by_username(username)
        valid = verify_password(password, account.password_hash if account else _DUMMY_HASH)
        return account if account and valid else None

    def session_user(self, token: str | None) -> str | None:
        """Usuário do admin logado, ou None."""

        def key_for(username: str) -> str | None:
            account = self.repo.get_by_username(username)
            return account.password_hash if account else None

        return read_session(token, ROLE_ADMIN, key_for)

    def new_session(self, account: AdminAccount, seconds: int) -> str:
        return create_session(ROLE_ADMIN, account.username, account.password_hash, seconds)

    def change_password(self, username: str, current: str, new: str) -> AdminAccount:
        account = self._get_by_username(username)
        if not verify_password(current, account.password_hash):
            raise BadRequest("Senha atual incorreta")
        self._check_password(new)
        if new == current:
            raise BadRequest("A nova senha deve ser diferente da atual")
        account.password_hash = hash_password(new)
        self.db.commit()
        return account

    # ---------- Relógios ----------

    def is_kiosk(self, token: str | None) -> bool:
        """Diz se o aparelho está liberado como relógio de ponto."""
        secret = self.repo.setting(KIOSK_SECRET)
        return read_session(token, ROLE_KIOSK, lambda _subject: secret) == KIOSK_SUBJECT

    def new_kiosk(self) -> str:
        return create_session(ROLE_KIOSK, KIOSK_SUBJECT, self.repo.setting(KIOSK_SECRET), settings.kiosk_days * 86400)

    def reset_kiosks(self) -> None:
        """Troca o segredo: todos os aparelhos liberados como relógio precisam ser ativados de novo."""
        self.repo.set_setting(KIOSK_SECRET, secrets.token_hex(32))
        self.db.commit()

    # ---------- Administradores ----------

    def list_admins(self) -> list[AdminAccount]:
        return self.repo.list()

    def create_admin(self, username: str, password: str) -> AdminAccount:
        username = username.strip()
        if not username or "|" in username:
            raise BadRequest("Usuário inválido")
        self._check_password(password)
        try:
            account = self.repo.add(AdminAccount(username=username, password_hash=hash_password(password)))
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise Conflict("Já existe um administrador com esse usuário")
        return account

    def delete_admin(self, admin_id: int, current_user: str) -> None:
        account = self.repo.get(admin_id)
        if not account:
            raise NotFound("Administrador não encontrado")
        if account.username == current_user:
            raise BadRequest("Você não pode excluir a própria conta")
        if self.repo.count() <= 1:
            raise BadRequest("É preciso manter pelo menos um administrador")
        self.repo.delete(account)
        self.db.commit()

    def _get_by_username(self, username: str) -> AdminAccount:
        account = self.repo.get_by_username(username)
        if not account:
            raise NotFound("Administrador não encontrado")
        return account

    @staticmethod
    def _check_password(password: str) -> None:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise BadRequest(f"A senha deve ter pelo menos {MIN_PASSWORD_LENGTH} caracteres")
