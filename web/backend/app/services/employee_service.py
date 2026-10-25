import secrets
from datetime import datetime, timezone

from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BadRequest, Conflict, NotFound
from app.core.security import hash_pin
from app.models import (
    Absence,
    AuditEvent,
    Company,
    Employee,
    EmployeeDevice,
    EmployeeSchedule,
    MonthClosure,
    Punch,
    PunchChange,
    PunchRequest,
)
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.punch_repository import PunchRepository
from app.models.employee import SCHEDULE_CYCLE
from app.schemas.employee import EmployeeCreate, EmployeeUpdate, ScheduleIn
from app.services.audit import AuditLog
from app.services.rules import ensure_months_open, load_rules
from app.utils.dates import now_local

PIN_IN_USE = "Este PIN já está em uso"

_FIELDS = {
    "name": "nome",
    "hired_on": "admissão",
    "terminated_on": "desligamento",
    "control_start": "início do controle",
}
# Saldo inicial do banco: até 2000 horas para mais ou para menos
MAX_INITIAL_MINUTES = 2000 * 60


def balance_label(minutes: int) -> str:
    sign = "+" if minutes > 0 else "−" if minutes < 0 else ""
    return f"{sign}{abs(minutes) // 60}h{abs(minutes) % 60:02d}"


def _check_initial(minutes: int, note: str) -> str:
    if abs(minutes) > MAX_INITIAL_MINUTES:
        raise BadRequest("O saldo inicial deve ficar entre −2000h e +2000h")
    note = note.strip()
    if minutes and not note:
        raise BadRequest("Informe de onde vem o saldo inicial (ex.: planilha de 2026)")
    return note


def _new_schedule(valid_from, spec: ScheduleIn) -> EmployeeSchedule:
    return EmployeeSchedule(
        valid_from=valid_from,
        kind=spec.kind,
        day_minutes=",".join(map(str, spec.minutes)),
        cycle_start=spec.cycle_start if spec.kind == SCHEDULE_CYCLE else None,
    )


def _schedule_details(s: EmployeeSchedule) -> dict:
    return {"kind": s.kind, "minutes": s.minutes, "cycle_start": s.cycle_start}


class EmployeeService:
    def __init__(self, db: Session, company_id: int):
        self.db = db
        self.repo = EmployeeRepository(db, company_id)
        self.punches = PunchRepository(db)
        self.audit = AuditLog(db, company_id)
        self.company_id = company_id

    def list(self) -> list[Employee]:
        return self.repo.list()

    def create(self, data: EmployeeCreate, user: str) -> Employee:
        hired_on = data.hired_on or self._today()
        note = _check_initial(data.initial_balance_minutes, data.initial_balance_note)
        employee = Employee(
            name=data.name,
            pin_hash=hash_pin(data.pin),
            hired_on=hired_on,
            control_start=data.control_start,
            initial_balance_minutes=data.initial_balance_minutes,
            initial_balance_note=note,
        )
        schedule = _new_schedule(hired_on, data.schedule_spec)
        employee.schedules.append(schedule)

        def add():
            self.repo.add(employee)
            self.db.flush()
            self.audit.record(
                user,
                "funcionario.criado",
                f"Cadastrou {employee.name} (admissão {hired_on:%d/%m/%Y}, "
                f"jornada {schedule.label})",
                employee_id=employee.id,
                details={"hired_on": hired_on, "schedule": _schedule_details(schedule)},
            )
            if data.initial_balance_minutes:
                self._log_initial(employee, 0, user)

        self._commit(add)
        return employee

    def update(self, employee_id: int, data: EmployeeUpdate, user: str) -> None:
        employee = self._get(employee_id)
        if employee.anonymized_at:
            raise BadRequest("Cadastro anonimizado (LGPD) não pode ser alterado")
        before = {field: getattr(employee, field) for field in _FIELDS}
        name_before = employee.name

        if data.name is not None:
            employee.name = data.name
        if data.hired_on is not None:
            employee.hired_on = data.hired_on
        if "terminated_on" in data.model_fields_set:
            employee.terminated_on = data.terminated_on
        if employee.terminated_on and employee.terminated_on < employee.hired_on:
            raise BadRequest("O desligamento não pode ser antes da admissão")
        if "control_start" in data.model_fields_set and data.control_start != employee.control_start:
            # Muda os dias que contam: desde a mais antiga das datas, nenhum mês dele pode estar fechado
            dates = [d for d in (data.control_start, employee.control_start) if d]
            first = min(dates) if len(dates) == 2 else employee.hired_on
            ensure_months_open(self.db, self.company_id, first, "o início do controle", employee.id)
            employee.control_start = data.control_start
        if data.initial_balance_minutes is not None or data.initial_balance_note is not None:
            minutes = (
                data.initial_balance_minutes
                if data.initial_balance_minutes is not None
                else employee.initial_balance_minutes
            )
            note = data.initial_balance_note if data.initial_balance_note is not None else employee.initial_balance_note
            note = _check_initial(minutes, note)
            if minutes != employee.initial_balance_minutes:
                # O saldo inicial entra no banco de todos os meses: nenhum deles pode estar fechado
                start = employee.counting_from(self._company_start())
                ensure_months_open(self.db, self.company_id, start, "o saldo inicial", employee.id)
                old = employee.initial_balance_minutes
                employee.initial_balance_minutes, employee.initial_balance_note = minutes, note
                self._log_initial(employee, old, user)
            employee.initial_balance_note = note

        changes = {f: [before[f], getattr(employee, f)] for f in _FIELDS if before[f] != getattr(employee, f)}
        if changes:
            self.audit.record(
                user,
                "funcionario.alterado",
                f"Alterou o cadastro de {name_before}: "
                + "; ".join(f"{_FIELDS[f]} {_show(old)} → {_show(new)}" for f, (old, new) in changes.items()),
                employee_id=employee.id,
                details={"changes": changes},
            )
        if data.active is not None and data.active != employee.active:
            employee.active = data.active
            self.audit.record(
                user,
                "funcionario.ativado" if data.active else "funcionario.desativado",
                f"{'Ativou' if data.active else 'Desativou'} {employee.name}",
                employee_id=employee.id,
            )
        if data.pin is not None:
            employee.pin_hash = hash_pin(data.pin)
            employee.pin_short = False
            # O PIN em si nunca vai para a auditoria
            self.audit.record(user, "funcionario.pin_trocado", f"Trocou o PIN de {employee.name}", employee_id=employee.id)
        if data.schedule is not None or data.daily_minutes is not None or data.workdays is not None:
            self._set_schedule(employee, data, user)
        self._commit()

    def _set_schedule(self, employee: Employee, data: EmployeeUpdate, user: str) -> None:
        """Nova jornada a partir de `schedule_from`; a anterior continua valendo antes dessa data."""
        start = data.schedule_from or self._today()
        current = employee.schedule_on(start)
        if data.schedule is not None:
            spec = data.schedule
        else:  # formato antigo: o que não veio continua como está
            minutes = data.daily_minutes if data.daily_minutes is not None else (current.daily_minutes if current else 480)
            workdays = data.workdays if data.workdays is not None else (current.workdays if current else "12345")
            spec = ScheduleIn.legacy(minutes, workdays)
        new = _new_schedule(start, spec)
        if current and _schedule_details(current) == _schedule_details(new):
            return
        # A jornada muda o previsto dos dias a partir de `start`: nenhum mês dele pode estar fechado
        ensure_months_open(self.db, self.company_id, start, "a nova jornada", employee.id)
        same_day = next((s for s in employee.schedules if s.valid_from == start), None)
        if same_day:
            same_day.kind, same_day.day_minutes, same_day.cycle_start = new.kind, new.day_minutes, new.cycle_start
        else:
            employee.schedules.append(new)
            employee.schedules.sort(key=lambda s: s.valid_from)
        self.audit.record(
            user,
            "jornada.alterada",
            f"Mudou a jornada de {employee.name} a partir de {start:%d/%m/%Y}: "
            f"{current.label if current else '—'} → {new.label}",
            employee_id=employee.id,
            details={
                "valid_from": start,
                "old": _schedule_details(current) if current else None,
                "new": _schedule_details(new),
            },
        )

    def delete(self, employee_id: int, user: str) -> None:
        """Só para cadastros feitos por engano: quem já tem registros de ponto é desativado, não excluído."""
        employee = self._get(employee_id)
        has_absences = self.db.scalar(select(Absence.id).where(Absence.employee_id == employee.id).limit(1))
        if self.punches.has_any(employee.id) or has_absences:
            raise Conflict("Este funcionário tem registros de ponto e não pode ser excluído. Desative-o.")
        self.audit.record(
            user, "funcionario.excluido", f"Excluiu o cadastro de {employee.name}", employee_id=employee.id
        )
        self.repo.delete(employee)
        self.db.commit()

    # ---------- LGPD ----------

    def export(self, employee_id: int, user: str) -> dict:
        """Tudo o que o sistema guarda sobre o funcionário (pedido de acesso aos próprios dados)."""
        employee = self._get(employee_id)
        db = self.db
        punches = list(db.scalars(select(Punch).where(Punch.employee_id == employee_id).order_by(Punch.ts)))
        ids = [p.id for p in punches]
        changes = list(db.scalars(select(PunchChange).where(PunchChange.punch_id.in_(ids)).order_by(PunchChange.id)))
        data = {
            "gerado_em": datetime.now(timezone.utc),
            "gerado_por": user,
            "funcionario": {
                "id": employee.id,
                "nome": employee.name,
                "ativo": employee.active,
                "cadastrado_em": employee.created_at,
                "admissao": employee.hired_on,
                "desligamento": employee.terminated_on,
                "inicio_do_controle": employee.control_start,
                "saldo_inicial_minutos": employee.initial_balance_minutes,
                "saldo_inicial_motivo": employee.initial_balance_note,
                "observacao_pin": "O PIN não é guardado, só um código derivado dele (hash), que não permite descobri-lo.",
            },
            "jornadas": [
                {
                    "desde": s.valid_from,
                    "tipo": s.kind,
                    "minutos": s.minutes,
                    "inicio_da_escala": s.cycle_start,
                    "descricao": s.label,
                }
                for s in employee.schedules
            ],
            "batidas": [
                {
                    "id": p.id,
                    "horario": p.ts,
                    "tipo": p.type,
                    "origem": p.source,
                    "manual": p.manual,
                    "sem_conexao": p.offline,
                    "motivo": p.note,
                    "horario_original": p.original_ts,
                    "tipo_original": p.original_type,
                    "excluida_em": p.deleted_at,
                    "aparelho": p.device,
                    "comprovante": p.receipt,
                }
                for p in punches
            ],
            "ausencias": [
                {
                    "tipo": a.label,
                    "de": a.first_day,
                    "ate": a.last_day,
                    "minutos_abonados_por_dia": a.minutes,
                    "observacao": a.note,
                    "lancada_por": a.created_by,
                    "lancada_em": a.created_at,
                }
                for a in db.scalars(select(Absence).where(Absence.employee_id == employee_id).order_by(Absence.first_day))
            ],
            "correcoes_de_batidas": [
                {
                    "batida": c.punch_id,
                    "em": c.at,
                    "por": c.user,
                    "acao": c.action,
                    "antes": {"horario": c.old_ts, "tipo": c.old_type},
                    "depois": {"horario": c.new_ts, "tipo": c.new_type},
                    "motivo": c.note,
                }
                for c in changes
            ],
            "solicitacoes_do_app": [
                {
                    "acao": r.action,
                    "horario": r.ts,
                    "tipo": r.type,
                    "observacao": r.note,
                    "situacao": r.status,
                    "pedida_em": r.requested_at,
                    "decidida_em": r.decided_at,
                    "decidida_por": r.decided_by,
                    "motivo_da_decisao": r.decision_note,
                }
                for r in db.scalars(select(PunchRequest).where(PunchRequest.employee_id == employee_id))
            ],
            "celulares": [
                {
                    "nome": d.name,
                    "criada_em": d.created_at,
                    "criada_por": d.created_by,
                    "ultimo_uso": d.last_used_at,
                    "vence_em": d.expires_at,
                    "revogada_em": d.revoked_at,
                }
                for d in db.scalars(select(EmployeeDevice).where(EmployeeDevice.employee_id == employee_id))
            ],
            "meses_fechados": [
                {"mes": c.month, "fechado_em": c.closed_at, "fechado_por": c.closed_by, "ciencia_em": c.acknowledged_at}
                for c in db.scalars(select(MonthClosure).where(MonthClosure.employee_id == employee_id))
            ],
            "auditoria": [
                {"em": a.at, "por": a.user, "acao": a.action, "descricao": a.summary}
                for a in db.scalars(
                    select(AuditEvent).where(AuditEvent.employee_id == employee_id).order_by(AuditEvent.id)
                )
            ],
        }
        self.audit.record(
            user, "funcionario.dados_exportados", f"Exportou os dados de {employee.name} (LGPD)", employee_id=employee.id
        )
        self.db.commit()
        return data

    def anonymize(self, employee_id: int, user: str) -> None:
        """Passado o prazo de guarda, apaga os dados pessoais. As batidas e as horas continuam (sem nome)."""
        employee = self._get(employee_id)
        if employee.anonymized_at:
            raise BadRequest("Este cadastro já foi anonimizado")
        if not employee.retention_due:
            raise BadRequest(
                f"Só é possível anonimizar {settings.retention_years} anos depois do desligamento "
                "(os registros de ponto precisam ser guardados até lá)"
            )
        db = self.db
        alias = f"Ex-funcionário nº {employee.id}"
        employee.name = alias
        employee.pin_hash = hash_pin(secrets.token_hex(16))  # nenhum PIN digitado bate com ele
        employee.pin_short = False
        employee.active = False
        employee.anonymized_at = datetime.now(timezone.utc)
        now = datetime.now(timezone.utc)
        db.execute(
            update(EmployeeDevice)
            .where(EmployeeDevice.employee_id == employee_id)
            .values(name="Celular", revoked_at=text("COALESCE(revoked_at, now())"))
        )
        db.execute(update(Punch).where(Punch.employee_id == employee_id).values(device=None))
        db.execute(update(PunchRequest).where(PunchRequest.employee_id == employee_id).values(note=None))
        # As observações das ausências podem trazer dados de saúde: saem; tipo e datas ficam (contam horas)
        db.execute(update(Absence).where(Absence.employee_id == employee_id).values(note=""))
        # Os registros de auditoria dessa pessoa trazem o nome: saem também (exceção prevista no banco)
        db.execute(text("SET LOCAL ponto.retencao = 'on'"))
        db.execute(delete(AuditEvent).where(AuditEvent.employee_id == employee_id))
        db.execute(text("SET LOCAL ponto.retencao = 'off'"))
        self.audit.record(
            user,
            "funcionario.anonimizado",
            f"Anonimizou o cadastro nº {employee.id} ({settings.retention_years} anos após o desligamento)",
            employee_id=employee.id,
            details={"terminated_on": employee.terminated_on, "at": now},
        )
        self.db.commit()

    def _log_initial(self, employee: Employee, old: int, user: str) -> None:
        self.audit.record(
            user,
            "funcionario.saldo_inicial",
            f"Saldo inicial do banco de horas de {employee.name}: {balance_label(old) or '0h00'} → "
            f"{balance_label(employee.initial_balance_minutes) or '0h00'} ({employee.initial_balance_note})",
            employee_id=employee.id,
            details={"old": old, "new": employee.initial_balance_minutes, "note": employee.initial_balance_note},
        )

    def _company_start(self):
        company = self.db.get(Company, self.company_id)
        return company.control_start if company else None

    def _today(self):
        return now_local(load_rules(self.db, self.company_id).tz).date()

    def _get(self, employee_id: int) -> Employee:
        employee = self.repo.get(employee_id)
        if not employee:
            raise NotFound("Funcionário não encontrado")
        return employee

    def _commit(self, action=None) -> None:
        try:
            if action:
                action()
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise Conflict(PIN_IN_USE)


def _show(value) -> str:
    if value is None:
        return "—"
    return f"{value:%d/%m/%Y}" if hasattr(value, "strftime") else str(value)
