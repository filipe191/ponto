from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BadRequest, Conflict, NotFound
from app.core.security import hash_pin
from app.models import Punch, PunchAction, PunchChange, PunchSource, PunchType
from app.repositories.calendar_repository import ClosureRepository
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.punch_repository import PunchRepository
from app.schemas.punch import ManualPunchCreate, PunchChangeOut, PunchResult, PunchUpdate, TodayPunch
from app.services.shifts import pair_shifts
from app.utils.dates import day_bounds, month_of, now_local, to_local

# Evita entrada e saída seguidas por toque duplo ou PIN digitado duas vezes
MIN_PUNCH_INTERVAL = timedelta(minutes=1)

NOTE_REQUIRED = "Informe o motivo do lançamento ou da correção"


def _with_tz(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=settings.timezone)


class PunchService:
    def __init__(self, db: Session, autocommit: bool = True):
        self.db = db
        # False: quem chama faz o commit (ex.: aprovar uma solicitação e marcá-la na mesma transação)
        self.autocommit = autocommit
        self.employees = EmployeeRepository(db)
        self.punches = PunchRepository(db)
        self.closures = ClosureRepository(db)

    def register(self, pin: str, offline_ts: datetime | None = None) -> PunchResult:
        """Bate o ponto pelo PIN: é saída se houver uma entrada aberta há menos de MAX_SHIFT_HOURS.

        `offline_ts`: batida feita com o relógio sem conexão e enviada depois (horário do aparelho).
        """
        employee = self.employees.get_by_pin_hash(hash_pin(pin), lock=True)
        if not employee or not employee.active:
            raise NotFound("PIN não reconhecido")

        now = datetime.now(timezone.utc)
        ts = now
        if offline_ts is not None:
            ts = _with_tz(offline_ts)
            if ts < now - timedelta(hours=settings.offline_max_hours) or ts > now + MIN_PUNCH_INTERVAL:
                raise BadRequest("Batida feita sem conexão fora do prazo aceito; peça um lançamento manual")
            ts = min(ts, now)

        near = self.punches.near(employee.id, ts, MIN_PUNCH_INTERVAL)
        if near:
            raise Conflict(
                f"{employee.name}, seu ponto já foi registrado às {to_local(near.ts):%H:%M}. "
                "Aguarde um minuto para bater de novo."
            )
        last = self.punches.last_before(employee.id, since=ts - settings.max_shift, before=ts)
        kind = PunchType.SAIDA if last and last.type == PunchType.ENTRADA else PunchType.ENTRADA

        punch = self.punches.add(Punch(employee_id=employee.id, ts=ts, type=kind, offline=offline_ts is not None))
        self.db.commit()
        return PunchResult(
            id=punch.id,
            receipt=punch.receipt,
            name=employee.name,
            type=kind,
            ts=ts,
            offline=punch.offline,
            today=self.today(employee.id),
            pin_short=employee.pin_short,
        )

    def today(self, employee_id: int) -> list[TodayPunch]:
        """Jornadas de hoje do funcionário, incluindo a que começou ontem e ainda está aberta ou fechou hoje."""
        now = datetime.now(timezone.utc)
        today = now_local().date()
        start, end = day_bounds(today)
        result = []
        for shift in pair_shifts(self.punches.list_between(start - settings.max_shift, end, employee_id), settings.max_shift):
            touches_today = any(to_local(p.ts).date() == today for p in shift.punches)
            if touches_today or shift.is_open(now, settings.max_shift):
                result.extend(shift.punches)
        return [TodayPunch(ts=p.ts, type=p.type) for p in sorted(result, key=lambda p: p.ts)]

    # ---------- Correções do admin (sempre com histórico) ----------

    def add_manual(self, data: ManualPunchCreate, user: str, client_id: str | None = None) -> Punch:
        if not self.employees.get(data.employee_id):
            raise BadRequest("Funcionário inválido")
        note = (data.note or "").strip()
        if not note:
            raise BadRequest(NOTE_REQUIRED)
        self._check_open(data.employee_id, _with_tz(data.ts))
        punch = self.punches.add(
            Punch(
                employee_id=data.employee_id,
                ts=_with_tz(data.ts),
                type=data.type,
                manual=True,
                note=note,
                source=PunchSource.ADMIN,
                client_id=client_id,
            )
        )
        self._log(punch, user, PunchAction.CRIADA, note=note)
        self._done()
        return punch

    def update(self, punch_id: int, data: PunchUpdate, user: str) -> None:
        """Corrige horário/tipo; o original do relógio fica guardado e a batida passa a contar como manual (*)."""
        punch = self._get(punch_id)
        if punch.deleted_at:
            raise BadRequest("Restaure a batida antes de alterá-la")
        old_ts, old_type = punch.ts, punch.type
        if not punch.manual and punch.original_ts is None:
            punch.original_ts, punch.original_type = punch.ts, punch.type
        if data.ts is not None:
            punch.ts = _with_tz(data.ts)
        if data.type is not None:
            punch.type = data.type
        if data.note is not None:
            punch.note = data.note.strip() or None
        if not punch.note:
            raise BadRequest(NOTE_REQUIRED)
        self._check_open(punch.employee_id, old_ts, punch.ts)
        punch.manual = True
        self._log(punch, user, PunchAction.ALTERADA, old_ts=old_ts, old_type=old_type, note=punch.note)
        self._done()

    def delete(self, punch_id: int, user: str, note: str = "") -> None:
        """Exclusão lógica: a batida sai do espelho e das horas, mas continua registrada."""
        punch = self._get(punch_id)
        if punch.deleted_at:
            return
        self._check_open(punch.employee_id, punch.ts)
        punch.deleted_at = datetime.now(timezone.utc)
        self._log(punch, user, PunchAction.EXCLUIDA, old_ts=punch.ts, old_type=punch.type, new=False, note=note)
        self._done()

    def restore(self, punch_id: int, user: str) -> None:
        punch = self._get(punch_id)
        if not punch.deleted_at:
            return
        self._check_open(punch.employee_id, punch.ts)
        punch.deleted_at = None
        self._log(punch, user, PunchAction.RESTAURADA)
        self._done()

    def history(self, punch_id: int) -> list[PunchChangeOut]:
        self._get(punch_id)
        return [PunchChangeOut.model_validate(c) for c in self.punches.changes_for(punch_id)]

    def _log(self, punch, user, action, old_ts=None, old_type=None, new=True, note=None) -> None:
        self.punches.add_change(
            PunchChange(
                punch_id=punch.id,
                user=user,
                action=action,
                old_ts=old_ts,
                old_type=old_type,
                new_ts=punch.ts if new else None,
                new_type=punch.type if new else None,
                note=(note or "").strip() or None,
            )
        )

    def _done(self) -> None:
        if self.autocommit:
            self.db.commit()
        else:
            self.db.flush()

    def _check_open(self, employee_id: int, *timestamps: datetime) -> None:
        """Mês fechado não aceita lançamentos nem correções (é preciso reabri-lo antes)."""
        for ts in timestamps:
            day = to_local(ts).date()
            if self.closures.get(employee_id, month_of(day)):
                raise BadRequest(f"O mês {day:%m/%Y} já foi fechado para este funcionário. Reabra o mês para alterar.")

    def _get(self, punch_id: int) -> Punch:
        punch = self.punches.get(punch_id)
        if not punch:
            raise NotFound("Batida não encontrada")
        return punch
