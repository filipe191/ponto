"""E-mail de aviso das solicitações do app (batida esquecida, correção, exclusão).

O e-mail diz só a empresa e quantas solicitações estão pendentes: nomes e horários ficam no painel,
para nenhum dado de funcionário sair do sistema por e-mail. Várias solicitações seguidas viram um
aviso só (no máximo um por empresa a cada `aviso_intervalo_minutos`). Sem SMTP_HOST no .env, nada
é enviado.
"""

import logging
import smtplib
import ssl
import threading
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Company, Employee, PunchRequest, RequestStatus

log = logging.getLogger("ponto")


def email_enabled() -> bool:
    return bool(settings.smtp_host)


def recipients(addresses: str) -> list[str]:
    return [a.strip() for a in addresses.split(",") if a.strip()]


def send_email(to: list[str], subject: str, body: str) -> None:
    """Envia em segundo plano: um servidor de e-mail lento ou fora do ar não atrasa o app."""
    threading.Thread(target=_deliver, args=(to, subject, body), daemon=True).start()


def _deliver(to: list[str], subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = settings.smtp_from or settings.smtp_user
    message["To"] = ", ".join(to)
    message["Subject"] = subject
    message.set_content(body)
    context = ssl.create_default_context()
    try:
        if settings.smtp_port == 465:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20, context=context)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
            server.starttls(context=context)
        with server:
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as e:
        log.warning("E-mail de aviso não enviado para %s: %s", message["To"], e)


class RequestNotifier:
    def __init__(self, db: Session):
        self.db = db

    def new_request(self, company_id: int) -> None:
        """Chamado depois de gravar uma solicitação; avisa a empresa se ela tem e-mail e o intervalo passou."""
        company = self.db.get(Company, company_id)
        to = recipients(company.notify_email) if company else []
        if not email_enabled() or not to:
            return
        now = datetime.now(timezone.utc)
        interval = timedelta(minutes=settings.aviso_intervalo_minutos)
        if company.requests_notified_at and now - company.requests_notified_at < interval:
            return
        pending = self.db.scalar(
            select(func.count())
            .select_from(PunchRequest)
            .join(Employee, Employee.id == PunchRequest.employee_id)
            .where(Employee.company_id == company_id, PunchRequest.status == RequestStatus.PENDENTE)
        )
        if not pending:
            return
        company.requests_notified_at = now
        self.db.commit()
        count = f"{pending} solicitações pendentes" if pending > 1 else "1 solicitação pendente"
        body = (
            f"Há {count} do app de ponto na empresa {company.name}.\n\n"
            "Abra o painel de administração (aba Início) para aprovar ou recusar."
        )
        if settings.painel_url:
            body += f"\n\n{settings.painel_url}"
        body += (
            "\n\nEste aviso não traz nomes nem horários, que ficam só no painel. Novas solicitações nos próximos "
            f"{settings.aviso_intervalo_minutos} minutos não geram outro e-mail."
        )
        send_email(to, f"Ponto: {count}", body)
