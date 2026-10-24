"""App de celular (app/) falando com este backend, no mesmo contrato do antigo backend Spring.

- A batida feita na hora entra direto no ponto (origem "app"; o horário vem do aparelho).
- Batida lançada depois no app, correção e exclusão viram solicitações que o admin aprova.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from pydantic import ValidationError
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BadRequest, NotFound, Unauthorized
from app.core.security import hash_device_key, new_device_key
from app.models import (
    Employee,
    EmployeeDevice,
    Punch,
    PunchRequest,
    PunchSource,
    PunchType,
    RequestAction,
    RequestStatus,
)
from app.repositories.calendar_repository import ClosureRepository
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.punch_repository import PunchRepository
from app.repositories.mobile_repository import (
    DeviceRepository,
    RequestRepository,
    last_punch,
    punch_by_public_id,
    punches_between,
)
from app.schemas.admin import DeviceCreated, RequestOut
from app.schemas.mobile import (
    AjusteRequest,
    BatidaRequest,
    BatidaServidor,
    DiaResumo,
    LoteResponse,
    Rejeitada,
    ResumoMes,
)
from app.schemas.punch import ManualPunchCreate, PunchUpdate
from app.schemas.report import DayStatus
from app.services.punch_service import MIN_PUNCH_INTERVAL, PunchService
from app.services.report_service import ReportService, check_month
from app.utils.dates import day_bounds, month_bounds, month_of, parse_month, to_local

REQUEST_NOTE = "Pedido pelo funcionário no app"


def _minutes(ms: int) -> int:
    return round(ms / 60000)


def _fmt(minutes: int, signed: bool = False) -> str:
    sign = ("-" if minutes < 0 else "+") if signed and minutes else ""
    return f"{sign}{abs(minutes) // 60}h{abs(minutes) % 60:02d}"


def to_batida(punch: Punch) -> BatidaServidor:
    return BatidaServidor(
        id=punch.public_id,
        tipo=punch.type.upper(),
        ocorrido_em=to_local(punch.ts),
        origem=punch.device or punch.source,
        observacao=punch.note,
        manual=punch.manual,
        ajustado_em=None,
        relogio_suspeito=punch.clock_suspect,
    )


class DeviceService:
    """Chaves de acesso do app, geradas pelo admin para cada funcionário."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = DeviceRepository(db)
        self.employees = EmployeeRepository(db)

    def authenticate(self, key: str | None) -> tuple[Employee, EmployeeDevice]:
        device = self.repo.by_key_hash(hash_device_key(key)) if key else None
        if not device or device.revoked_at:
            raise Unauthorized("Chave de acesso inválida")
        employee = self.employees.get(device.employee_id)
        if not employee or not employee.active:
            raise Unauthorized("Funcionário desativado")
        now = datetime.now(timezone.utc)
        # Grava o último uso de vez em quando, não a cada requisição
        if not device.last_used_at or now - device.last_used_at > timedelta(minutes=5):
            device.last_used_at = now
            self.db.commit()
        return employee, device

    def list(self, employee_id: int) -> list[EmployeeDevice]:
        return self.repo.list_for_employee(employee_id)

    def create(self, employee_id: int, name: str, user: str) -> DeviceCreated:
        if not self.employees.get(employee_id):
            raise NotFound("Funcionário não encontrado")
        key = new_device_key()
        device = self.repo.add(
            EmployeeDevice(employee_id=employee_id, name=name, key_hash=hash_device_key(key), created_by=user)
        )
        self.db.commit()
        return DeviceCreated(
            id=device.id,
            name=device.name,
            created_at=device.created_at,
            created_by=device.created_by,
            last_used_at=None,
            revoked_at=None,
            key=key,
        )

    def revoke(self, device_id: int) -> None:
        device = self.repo.get(device_id)
        if not device:
            raise NotFound("Celular não encontrado")
        if not device.revoked_at:
            device.revoked_at = datetime.now(timezone.utc)
            self.db.commit()


class MobileService:
    def __init__(self, db: Session, employee: Employee, device: EmployeeDevice):
        self.db = db
        self.employee = employee
        self.device = device
        self.requests = RequestRepository(db)
        self.closures = ClosureRepository(db)
        self.punches = PunchRepository(db)

    # ---------- Envio do lote ----------

    def sync(self, raw: list[dict]) -> LoteResponse:
        """Recebe as batidas pendentes do celular. Reenviar o mesmo lote não duplica nada."""
        result = LoteResponse()
        for item in raw:
            item_id = str(item.get("id", "")) if isinstance(item, dict) else ""
            try:
                batida = BatidaRequest.model_validate(item)
                uuid.UUID(batida.id)
            except (ValidationError, ValueError):
                result.rejeitadas.append(Rejeitada(id=item_id, motivo="Batida inválida"))
                continue
            try:
                with self.db.begin_nested():
                    status = self._receive(batida)
            except BadRequest as e:
                result.rejeitadas.append(Rejeitada(id=batida.id, motivo=e.message))
                continue
            (result.aceitas if status == "aceita" else result.duplicadas).append(batida.id)
        self.db.commit()
        return result

    def _receive(self, b: BatidaRequest) -> str:
        if self._client_id_known(b.id):
            return "duplicada"
        ts = b.ocorrido_em if b.ocorrido_em.tzinfo else b.ocorrido_em.replace(tzinfo=settings.timezone)
        kind = PunchType.ENTRADA if b.tipo == "ENTRADA" else PunchType.SAIDA

        if b.manual:
            # Lançada depois no app ("esqueci de bater"): vira pedido para o admin aprovar
            self.requests.add(
                PunchRequest(
                    employee_id=self.employee.id,
                    device_id=self.device.id,
                    action=RequestAction.INCLUIR,
                    ts=ts,
                    type=kind,
                    client_id=b.id,
                    note=b.observacao or "Batida esquecida, lançada no app",
                )
            )
            return "aceita"

        if self.closures.get(self.employee.id, month_of(to_local(ts).date())):
            raise BadRequest("Mês já fechado pelo administrador; peça um lançamento manual")
        # Mesma batida feita também no relógio da empresa (ou toque duplo): o ponto já tem esse horário
        if self.punches.near(self.employee.id, ts, MIN_PUNCH_INTERVAL):
            return "duplicada"
        self.db.add(
            Punch(
                employee_id=self.employee.id,
                ts=ts,
                type=kind,
                source=PunchSource.APP,
                client_id=b.id,
                note=b.observacao,
                device=b.origem or self.device.name,
                device_uptime_ms=b.uptime_ms,
            )
        )
        self.db.flush()
        return "aceita"

    def _client_id_known(self, client_id: str) -> bool:
        in_punches = self.db.scalar(select(exists().where(Punch.client_id == client_id)))
        return bool(in_punches or self.requests.by_client_id(client_id))

    # ---------- Consultas ----------

    def last(self) -> BatidaServidor | None:
        punch = last_punch(self.db, self.employee.id)
        return to_batida(punch) if punch else None

    def between(self, first: date, last: date) -> list[BatidaServidor]:
        if last < first or (last - first).days > 400:
            raise BadRequest("Período inválido")
        start, _ = day_bounds(first)
        _, end = day_bounds(last)
        return [to_batida(p) for p in punches_between(self.db, self.employee.id, start, end)]

    def summary(self, month: str) -> ResumoMes:
        """Resumo do mês calculado pelas mesmas regras do espelho (CLT, feriados, jornada)."""
        report = ReportService(self.db).build(self.employee, check_month(month), None)
        start, end = month_bounds(*parse_month(month))
        by_id = {p.id: p for p in punches_between(self.db, self.employee.id, start - settings.max_shift, end + settings.max_shift)}
        dias = []
        for d in report.days:
            batidas = [to_batida(by_id[p.id]) for p in d.punches if not p.deleted_at and p.id in by_id]
            if not batidas:
                continue
            worked = _minutes(d.worked_ms)
            dias.append(
                DiaResumo(
                    data=date.fromisoformat(d.date),
                    trabalhado_minutos=worked,
                    trabalhado_formatado=_fmt(worked),
                    saldo_minutos=_minutes(d.balance_ms),
                    dia_aberto=d.status in (DayStatus.INCOMPLETO, DayStatus.ANDAMENTO) and len(batidas) % 2 == 1,
                    batidas=batidas,
                )
            )
        worked, balance = _minutes(report.total_ms), _minutes(report.balance_ms)
        return ResumoMes(
            inicio=start.date(),
            fim=(end - timedelta(days=1)).date(),
            trabalhado_minutos=worked,
            esperado_minutos=_minutes(report.expected_ms),
            saldo_minutos=balance,
            trabalhado_formatado=_fmt(worked),
            saldo_formatado=_fmt(balance, signed=True),
            dias=dias,
        )

    # ---------- Correções pedidas pelo app ----------

    def request_change(self, public_id: str, data: AjusteRequest) -> BatidaServidor:
        punch = self._punch(public_id)
        if data.ocorrido_em is None and data.tipo is None:
            raise BadRequest("Nada para corrigir")
        ts = data.ocorrido_em
        if ts is not None and not ts.tzinfo:
            ts = ts.replace(tzinfo=settings.timezone)
        kind = (PunchType.ENTRADA if data.tipo == "ENTRADA" else PunchType.SAIDA) if data.tipo else None
        self._upsert_request(punch, RequestAction.ALTERAR, ts, kind, data.observacao)
        return to_batida(punch)  # nada muda até o admin aprovar

    def request_delete(self, public_id: str) -> None:
        self._upsert_request(self._punch(public_id), RequestAction.EXCLUIR, None, None, None)

    def _upsert_request(self, punch: Punch, action: str, ts, kind, note) -> None:
        # Um pedido pendente por batida: o mais recente substitui o anterior
        request = self.requests.pending_for_punch(punch.id)
        if not request:
            request = self.requests.add(
                PunchRequest(employee_id=self.employee.id, device_id=self.device.id, punch_id=punch.id, action=action)
            )
        request.action = action
        request.ts, request.type = ts, kind
        request.note = note or REQUEST_NOTE
        request.requested_at = datetime.now(timezone.utc)
        self.db.commit()

    def _punch(self, public_id: str) -> Punch:
        punch = punch_by_public_id(self.db, self.employee.id, public_id)
        if not punch:
            raise NotFound("Batida não encontrada")
        return punch


class RequestService:
    """Admin aprova ou recusa os pedidos feitos pelo app."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = RequestRepository(db)

    def list(self, status: str | None) -> list[RequestOut]:
        return [
            RequestOut(
                id=r.id,
                employee_id=r.employee_id,
                employee_name=r.employee.name,
                action=r.action,
                status=r.status,
                current_ts=r.punch.ts if r.punch else None,
                current_type=r.punch.type if r.punch else None,
                ts=r.ts,
                type=r.type,
                note=r.note,
                requested_at=r.requested_at,
                decided_at=r.decided_at,
                decided_by=r.decided_by,
                decision_note=r.decision_note,
            )
            for r in self.repo.list(status or None)
        ]

    def approve(self, request_id: int, user: str, note: str = "") -> None:
        request = self._pending(request_id)
        when = f"{to_local(request.requested_at):%d/%m/%Y %H:%M}"
        reason = f"{request.note or REQUEST_NOTE} (pedido no app em {when})"
        punches = PunchService(self.db, autocommit=False)
        if request.action == RequestAction.INCLUIR:
            punches.add_manual(
                ManualPunchCreate(employee_id=request.employee_id, ts=request.ts, type=request.type, note=reason),
                user,
                client_id=request.client_id,
            )
        elif request.action == RequestAction.ALTERAR:
            punches.update(request.punch_id, PunchUpdate(ts=request.ts, type=request.type, note=reason), user)
        else:
            punches.delete(request.punch_id, user, reason)
        self._decide(request, RequestStatus.APROVADA, user, note)

    def reject(self, request_id: int, user: str, note: str = "") -> None:
        self._decide(self._pending(request_id), RequestStatus.RECUSADA, user, note)

    def _decide(self, request: PunchRequest, status: str, user: str, note: str) -> None:
        request.status = status
        request.decided_at = datetime.now(timezone.utc)
        request.decided_by = user
        request.decision_note = note.strip() or None
        self.db.commit()

    def _pending(self, request_id: int) -> PunchRequest:
        request = self.repo.get(request_id)
        if not request:
            raise NotFound("Solicitação não encontrada")
        if request.status != RequestStatus.PENDENTE:
            raise BadRequest("Esta solicitação já foi decidida")
        return request
