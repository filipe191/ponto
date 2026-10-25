import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import twofactor
from app.core.config import settings
from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.passwords import password_problem
from app.core.security import (
    ROLE_KIOSK,
    create_session,
    hash_password,
    hash_session_token,
    new_session_token,
    read_session,
    verify_password,
)
from app.models import AdminAccount, AdminSession, Company
from app.repositories.admin_repository import AdminRepository
from app.services.audit import AuditLog
from app.services.rules import default_rule

KIOSK_SUBJECT = "relogio"  # sujeito do token do relógio: "relogio:<empresa>"
# Relógios liberados antes das várias empresas: o token diz só "relogio" e vale para a empresa nº 1,
# que herdou o segredo deles (migração 0008)
LEGACY_KIOSK_COMPANY = 1
# Hash de uma senha qualquer: usuário inexistente gasta o mesmo tempo que senha errada
_DUMMY_HASH = hash_password(secrets.token_hex(8))
# A última atividade da sessão é gravada de tempos em tempos, não a cada requisição
_TOUCH_EVERY = timedelta(minutes=5)

PENDING_PASSWORD = "senha"  # precisa trocar a senha
PENDING_2FA = "2fa"  # precisa ativar a verificação em duas etapas


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AdminRepository(db)

    def audit(self, company_id: int | None) -> AuditLog:
        return AuditLog(self.db, company_id)

    def own_audit(self, account: AdminAccount) -> AuditLog:
        """Onde fica o que o admin faz na própria conta: na empresa dele, ou na auditoria do sistema
        para o superadmin (os admins da empresa nº 1 não veem os logins do superadmin)."""
        return self.audit(None if account.superadmin else account.company_id)

    def ensure_setup(self) -> None:
        """Na primeira subida, cria o superadmin com ADMIN_USER/ADMIN_PASSWORD do .env (ele cadastra as empresas)."""
        if not self.repo.count():
            self.repo.add(
                AdminAccount(
                    username=settings.admin_user,
                    password_hash=hash_password(settings.admin_password),
                    must_change_password=True,  # a senha do .env é provisória
                    superadmin=True,
                )
            )
        self.db.commit()

    # ---------- Login do admin ----------

    def authenticate(self, username: str, password: str, ip: str = "?") -> AdminAccount | None:
        account = self.repo.get_by_username(username)
        valid = verify_password(password, account.password_hash if account else _DUMMY_HASH)
        if account and not valid:
            self.log_login(account, False, ip, "senha errada")
        if not (account and valid):
            return None
        company = self.repo.company(account.company_id)
        if not account.superadmin and not (company and company.active):
            self.log_login(account, False, ip, "empresa desativada")
            raise Forbidden("Esta empresa está desativada. Fale com o administrador do sistema")
        # Senha que não segue mais a política (ex.: criada antes dela): trocar antes de usar o painel
        if password_problem(password, account.username):
            account.must_change_password = True
        return account

    def log_login(self, account: AdminAccount, ok: bool, ip: str, reason: str = "") -> None:
        """Entradas e tentativas erradas numa conta que existe (usuário inexistente não é registrado)."""
        audit = self.own_audit(account)
        if ok:
            audit.record(account.username, "admin.login", "Entrou no painel", ip=ip)
        else:
            audit.record(account.username, "admin.login_falhou", f"Tentativa de login recusada: {reason}", ip=ip)
        self.db.commit()

    def check_second_factor(self, account: AdminAccount, code: str) -> bool:
        """Código do app autenticador ou um código de recuperação (que deixa de valer depois de usado)."""
        secret = twofactor.decrypt_secret(account.totp_secret) if account.totp_secret else None
        if not secret:
            return False
        step = twofactor.verify(secret, code, account.totp_last_step)
        if step is not None:
            account.totp_last_step = step
            return True
        recovery = self.repo.unused_recovery_code(account.id, twofactor.hash_recovery_code(code))
        if recovery:
            recovery.used_at = _now()
            return True
        return False

    def pending(self, account: AdminAccount) -> str | None:
        """O que o admin precisa resolver antes de usar o painel."""
        if account.must_change_password:
            return PENDING_PASSWORD
        if settings.admin_2fa_required and not account.totp_secret:
            return PENDING_2FA
        return None

    # ---------- Sessões no servidor ----------

    def start_session(self, account: AdminAccount, seconds: int, ip: str | None, user_agent: str | None) -> str:
        token = new_session_token()
        company_id = account.company_id
        if account.superadmin and not self.repo.company(company_id):
            # Superadmin sem empresa própria: abre a primeira; no painel ele escolhe outra
            first = self.repo.first_active_company()
            company_id = first.id if first else None
        self.repo.add_session(
            AdminSession(
                admin_id=account.id,
                company_id=company_id,
                token_hash=hash_session_token(token),
                expires_at=_now() + timedelta(seconds=seconds),
                ip=ip,
                user_agent=(user_agent or "")[:300] or None,
            )
        )
        self.db.commit()
        return token

    def session_account(self, token: str | None) -> tuple[AdminAccount, AdminSession] | None:
        """Admin e sessão do token, se ela não tiver sido encerrada, vencida ou ficado parada demais."""
        if not token:
            return None
        session = self.repo.session_by_hash(hash_session_token(token))
        now = _now()
        if (
            not session
            or session.revoked_at
            or session.expires_at <= now
            or now - session.last_seen_at > timedelta(hours=settings.session_idle_hours)
        ):
            return None
        account = self.repo.get(session.admin_id)
        if not account:
            return None
        if not account.superadmin:
            company = self.repo.company(account.company_id)
            if not (company and company.active):
                return None  # empresa desativada: os admins dela saem na hora
        if now - session.last_seen_at > _TOUCH_EVERY:
            session.last_seen_at = now
            self.db.commit()
        return account, session

    @staticmethod
    def session_company(account: AdminAccount, session: AdminSession) -> int | None:
        """Empresa aberta no painel: a do admin, ou a escolhida pelo superadmin nesta sessão."""
        return session.company_id if account.superadmin else account.company_id

    def switch_company(self, account: AdminAccount, session: AdminSession, company_id: int, ip: str) -> Company:
        """O superadmin abre outra empresa no painel. A entrada fica na auditoria da empresa."""
        if not account.superadmin:
            raise Forbidden("Só o superadministrador troca de empresa")
        company = self.repo.company(company_id)
        if not company:
            raise NotFound("Empresa não encontrada")
        if session.company_id != company.id:
            session.company_id = company.id
            self.audit(company.id).record(
                account.username, "admin.empresa_aberta", "Superadministrador abriu o painel desta empresa", ip=ip
            )
            self.db.commit()
        return company

    def company(self, company_id: int | None) -> Company | None:
        return self.repo.company(company_id)

    def company_by_code(self, code: str) -> Company | None:
        """Empresa do link público do aviso de privacidade (só as ativas)."""
        company = self.repo.company_by_code(code) if code else None
        return company if company and company.active else None

    def end_session(self, token: str | None) -> None:
        session = self.repo.session_by_hash(hash_session_token(token)) if token else None
        if session and not session.revoked_at:
            session.revoked_at = _now()
            self.db.commit()

    def list_sessions(self, account: AdminAccount) -> list[AdminSession]:
        """Sessões que ainda valem (não encerradas, não vencidas e não paradas além do limite)."""
        now = _now()
        idle = timedelta(hours=settings.session_idle_hours)
        return [s for s in self.repo.active_sessions(account.id, now) if now - s.last_seen_at <= idle]

    def end_session_by_id(self, account: AdminAccount, session_id: int) -> None:
        for session in self.repo.active_sessions(account.id, _now()):
            if session.id == session_id:
                session.revoked_at = _now()
                self.db.commit()
                return
        raise NotFound("Sessão não encontrada")

    def end_other_sessions(self, account: AdminAccount, keep: AdminSession) -> None:
        self.repo.revoke_sessions(account.id, _now(), keep_id=keep.id)
        self.db.commit()

    # ---------- Senha ----------

    def change_password(self, account: AdminAccount, current: str, new: str, keep: AdminSession) -> None:
        """Troca a senha; as outras sessões do admin caem, a atual continua."""
        if not verify_password(current, account.password_hash):
            raise BadRequest("Senha atual incorreta")
        if new == current:
            raise BadRequest("A nova senha deve ser diferente da atual")
        problem = password_problem(new, account.username)
        if problem:
            raise BadRequest(problem)
        account.password_hash = hash_password(new)
        account.must_change_password = False
        self.repo.revoke_sessions(account.id, _now(), keep_id=keep.id)
        self.own_audit(account).record(account.username, "admin.senha_trocada", "Trocou a própria senha")
        self.db.commit()

    # ---------- Verificação em duas etapas ----------

    def totp_setup(self, account: AdminAccount) -> dict:
        """Gera um segredo novo, ainda pendente: só vale depois de confirmado com um código."""
        secret = twofactor.new_secret()
        account.totp_pending = twofactor.encrypt_secret(secret)
        self.db.commit()
        uri = twofactor.provisioning_uri(secret, account.username)
        return {"secret": secret, "uri": uri, "qr": twofactor.qr_data_uri(uri)}

    def totp_enable(self, account: AdminAccount, code: str) -> list[str]:
        secret = twofactor.decrypt_secret(account.totp_pending) if account.totp_pending else None
        if not secret:
            raise BadRequest("Comece a ativação de novo")
        step = twofactor.verify(secret, code, None)
        if step is None:
            raise BadRequest("Código inválido. Confira o horário do celular e tente de novo")
        account.totp_secret = account.totp_pending
        account.totp_pending = None
        account.totp_last_step = step
        codes = twofactor.new_recovery_codes()
        self.repo.replace_recovery_codes(account.id, [twofactor.hash_recovery_code(c) for c in codes])
        self.own_audit(account).record(account.username, "admin.2fa_ativada", "Ativou a verificação em duas etapas")
        self.db.commit()
        return codes

    def totp_disable(self, account: AdminAccount, password: str, code: str) -> None:
        if not verify_password(password, account.password_hash):
            raise BadRequest("Senha incorreta")
        if not self.check_second_factor(account, code):
            raise BadRequest("Código inválido")
        account.totp_secret = None
        account.totp_pending = None
        account.totp_last_step = None
        self.repo.replace_recovery_codes(account.id, [])
        self.own_audit(account).record(
            account.username, "admin.2fa_desativada", "Desativou a verificação em duas etapas"
        )
        self.db.commit()

    def new_recovery_codes(self, account: AdminAccount, code: str) -> list[str]:
        if not self.check_second_factor(account, code):
            raise BadRequest("Código inválido")
        codes = twofactor.new_recovery_codes()
        self.repo.replace_recovery_codes(account.id, [twofactor.hash_recovery_code(c) for c in codes])
        self.own_audit(account).record(
            account.username, "admin.codigos_recuperacao", "Gerou novos códigos de recuperação"
        )
        self.db.commit()
        return codes

    def recovery_codes_left(self, account: AdminAccount) -> int:
        return self.repo.recovery_codes_left(account.id)

    # ---------- Relógios ----------

    def kiosk_company(self, token: str | None) -> int | None:
        """Empresa do aparelho liberado como relógio (None se não for um relógio válido)."""
        found: list[int] = []

        def key_for(subject: str) -> str | None:
            if subject == KIOSK_SUBJECT:
                company_id = LEGACY_KIOSK_COMPANY
            else:
                prefix, _, number = subject.partition(":")
                if prefix != KIOSK_SUBJECT or not number.isdigit():
                    return None
                company_id = int(number)
            company = self.repo.company(company_id)
            if not (company and company.active):
                return None
            found.append(company.id)
            return company.kiosk_secret

        return found[0] if read_session(token, ROLE_KIOSK, key_for) else None

    def new_kiosk(self, company_id: int, user: str, ip: str) -> str:
        company = self._company(company_id)
        self.audit(company.id).record(user, "relogio.ativado", "Liberou um aparelho como relógio de ponto", ip=ip)
        self.db.commit()
        return create_session(
            ROLE_KIOSK, f"{KIOSK_SUBJECT}:{company.id}", company.kiosk_secret, settings.kiosk_days * 86400
        )

    def kiosk_disabled(self, company_id: int, user: str, ip: str) -> None:
        self.audit(company_id).record(user, "relogio.desativado", "Desligou o modo relógio de um aparelho", ip=ip)
        self.db.commit()

    def reset_kiosks(self, company_id: int, user: str) -> None:
        """Troca o segredo da empresa: todos os relógios dela precisam ser ativados de novo."""
        self._company(company_id).kiosk_secret = secrets.token_hex(32)
        self.audit(company_id).record(user, "relogio.todos_desligados", "Desligou todos os relógios")
        self.db.commit()

    # ---------- Administradores ----------

    def list_admins(self, company_id: int) -> list[AdminAccount]:
        return self.repo.list(company_id)

    def create_admin(self, company_id: int, username: str, password: str, user: str) -> AdminAccount:
        """A senha inicial é provisória: o novo admin troca no primeiro acesso e ativa as duas etapas."""
        username = username.strip()
        if not username or "|" in username:
            raise BadRequest("Usuário inválido")
        problem = password_problem(password, username)
        if problem:
            raise BadRequest(problem)
        try:
            account = self.repo.add(
                AdminAccount(
                    company_id=company_id,
                    username=username,
                    password_hash=hash_password(password),
                    must_change_password=True,
                )
            )
            self.audit(company_id).record(user, "admin.criado", f"Criou o administrador {username}")
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise Conflict("Já existe um administrador com esse usuário")
        return account

    def delete_admin(self, company_id: int, admin_id: int, current_user: str) -> None:
        account = self.repo.get(admin_id)
        if not account or account.company_id != company_id:
            raise NotFound("Administrador não encontrado")
        if account.username == current_user:
            raise BadRequest("Você não pode excluir a própria conta")
        if account.superadmin:
            raise BadRequest("O superadministrador não pode ser excluído pelo painel da empresa")
        if self.repo.count(company_id) <= 1:
            raise BadRequest("É preciso manter pelo menos um administrador")
        self.audit(company_id).record(current_user, "admin.excluido", f"Excluiu o administrador {account.username}")
        self.repo.delete(account)  # as sessões e os códigos de recuperação caem junto (ON DELETE CASCADE)
        self.db.commit()

    # ---------- Empresas (só o superadmin) ----------

    def list_companies(self) -> list[Company]:
        return self.repo.companies()

    def create_company(self, name: str, contact: str, admin_username: str, admin_password: str, user: str) -> Company:
        """Cadastra a empresa já com o primeiro admin dela (senha provisória, como os demais)."""
        name = name.strip()
        if not name:
            raise BadRequest("Informe o nome da empresa")
        company = self.repo.add_company(
            Company(
                name=name,
                privacy_contact=contact.strip(),
                kiosk_secret=secrets.token_hex(32),
                timezone=settings.tz,
                offline_max_hours=settings.offline_max_hours,
            )
        )
        self.db.add(default_rule(company.id, user))
        self.audit(company.id).record(user, "empresa.criada", f"Cadastrou a empresa {name}")
        self.audit(None).record(
            user, "empresa.criada", f"Cadastrou a empresa {name}", details={"company_id": company.id}
        )
        self.create_admin(company.id, admin_username, admin_password, user)  # faz o commit (ou desfaz tudo)
        return company

    def update_company(
        self, company_id: int, user: str, name: str | None, contact: str | None, active: bool | None
    ) -> Company:
        company = self._company(company_id)
        changes = []
        if name is not None and name.strip() and name.strip() != company.name:
            changes.append(f"nome {company.name} → {name.strip()}")
            company.name = name.strip()
        if contact is not None and contact.strip() != company.privacy_contact:
            changes.append("contato de privacidade alterado")
            company.privacy_contact = contact.strip()
        events = []
        if changes:
            events.append(("empresa.alterada", "Alterou a empresa: " + "; ".join(changes)))
        if active is not None and active != company.active:
            company.active = active
            events.append(
                ("empresa.ativada", "Ativou a empresa")
                if active
                else ("empresa.desativada", "Desativou a empresa (admins, relógios e celulares param)")
            )
        # Fica na auditoria da empresa (os admins dela veem) e na do sistema (com o nome da empresa)
        for action, summary in events:
            self.audit(company.id).record(user, action, summary)
            self.audit(None).record(user, action, f"{company.name}: {summary}", details={"company_id": company.id})
        self.db.commit()
        return company

    # ---------- Superadministradores ----------

    def list_superadmins(self) -> list[AdminAccount]:
        return self.repo.superadmins()

    def create_superadmin(self, username: str, password: str, user: str) -> AdminAccount:
        """Outro superadmin, para o sistema não depender de uma conta só. Senha provisória, como os demais."""
        username = username.strip()
        if not username or "|" in username:
            raise BadRequest("Usuário inválido")
        problem = password_problem(password, username)
        if problem:
            raise BadRequest(problem)
        try:
            account = self.repo.add(
                AdminAccount(
                    username=username,
                    password_hash=hash_password(password),
                    must_change_password=True,
                    superadmin=True,
                )
            )
            self.audit(None).record(user, "superadmin.criado", f"Criou o superadministrador {username}")
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise Conflict("Já existe um administrador com esse usuário")
        return account

    def delete_superadmin(self, admin_id: int, current_user: str) -> None:
        account = self.repo.get(admin_id)
        if not account or not account.superadmin:
            raise NotFound("Superadministrador não encontrado")
        if account.username == current_user:
            raise BadRequest("Você não pode excluir a própria conta")
        if len(self.repo.superadmins()) <= 1:
            raise BadRequest("É preciso manter pelo menos um superadministrador")
        self.audit(None).record(current_user, "superadmin.excluido", f"Excluiu o superadministrador {account.username}")
        self.repo.delete(account)
        self.db.commit()

    def _company(self, company_id: int) -> Company:
        company = self.repo.company(company_id)
        if not company:
            raise NotFound("Empresa não encontrada")
        return company
