"""Auditoria geral: cada ação de admin (e alguns eventos do relógio) vira uma linha que não muda mais.

O registro entra na mesma transação da ação: se a ação falhar, nada é registrado, e vice-versa.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent

CLOCK_USER = "relógio"
EMPLOYEE_USER = "funcionário"

# Ações que aparecem como alerta no topo do painel
PIN_BLOCKED = "relogio.bloqueado"


def _plain(value):
    """Valores que cabem no JSON (datas viram texto)."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


class AuditLog:
    """Auditoria de uma empresa: grava nela e só lista o que é dela.

    Sem empresa (`company_id=None`) é a auditoria do sistema: o que o superadmin faz fora das empresas
    (login, senha, duas etapas, cadastro de empresas e de superadmins).
    """

    def __init__(self, db: Session, company_id: int | None):
        self.db = db
        self.company_id = company_id

    def _scope(self):
        if self.company_id is None:
            return AuditEvent.company_id.is_(None)
        return AuditEvent.company_id == self.company_id

    def record(
        self,
        user: str,
        action: str,
        summary: str,
        *,
        employee_id: int | None = None,
        details: dict | None = None,
        ip: str | None = None,
    ) -> None:
        self.db.add(
            AuditEvent(
                company_id=self.company_id,
                user=user,
                action=action,
                summary=summary,
                employee_id=employee_id,
                details=_plain(details) if details else None,
                ip=ip,
            )
        )

    def list(
        self, employee_id: int | None = None, action: str = "", before: int | None = None, limit: int = 50
    ) -> list[AuditEvent]:
        """Mais recentes primeiro; `action` filtra pelo prefixo (ex.: "mes." pega fechar e reabrir)."""
        query = select(AuditEvent).where(self._scope())
        if employee_id:
            query = query.where(AuditEvent.employee_id == employee_id)
        if action:
            query = query.where(AuditEvent.action.startswith(action, autoescape=True))
        if before:
            query = query.where(AuditEvent.id < before)
        return list(self.db.scalars(query.order_by(AuditEvent.id.desc()).limit(min(max(limit, 1), 200))))

    def reopenings(self, employee_id: int, month: str) -> list[AuditEvent]:
        """Fechamentos anteriores do mês (com a ciência dada na época), preservados na reabertura."""
        return list(
            self.db.scalars(
                select(AuditEvent)
                .where(
                    self._scope(),
                    AuditEvent.action == "mes.reaberto",
                    AuditEvent.employee_id == employee_id,
                    AuditEvent.details["month"].astext == month,
                )
                .order_by(AuditEvent.id)
            )
        )

    def recent(self, action: str, hours: int = 24) -> list[AuditEvent]:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        return list(
            self.db.scalars(
                select(AuditEvent)
                .where(self._scope(), AuditEvent.action == action, AuditEvent.at >= since)
                .order_by(AuditEvent.id.desc())
            )
        )
