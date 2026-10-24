from datetime import datetime, timedelta

from sqlalchemy import exists, select
from sqlalchemy.orm import Session, joinedload

from app.models import Punch, PunchChange

_not_deleted = Punch.deleted_at.is_(None)


class PunchRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, punch_id: int) -> Punch | None:
        return self.db.get(Punch, punch_id)

    def last_before(self, employee_id: int, since: datetime, before: datetime) -> Punch | None:
        """Última batida do funcionário em [since, before)."""
        return self.db.scalar(
            select(Punch)
            .where(Punch.employee_id == employee_id, Punch.ts >= since, Punch.ts < before, _not_deleted)
            .order_by(Punch.ts.desc())
            .limit(1)
        )

    def near(self, employee_id: int, ts: datetime, delta: timedelta) -> Punch | None:
        """Alguma batida do funcionário a menos de `delta` de `ts` (antes ou depois)."""
        return self.db.scalar(
            select(Punch)
            .where(Punch.employee_id == employee_id, Punch.ts > ts - delta, Punch.ts < ts + delta, _not_deleted)
            .order_by(Punch.ts)
            .limit(1)
        )

    def list_between(self, start: datetime, end: datetime) -> list[Punch]:
        """Batidas de todos os funcionários no intervalo, já com o funcionário carregado."""
        return list(
            self.db.scalars(
                select(Punch)
                .options(joinedload(Punch.employee))
                .where(Punch.ts >= start, Punch.ts < end, _not_deleted)
                .order_by(Punch.employee_id, Punch.ts)
            )
        )

    def list_for_employee(self, employee_id: int, end: datetime, include_deleted: bool = False) -> list[Punch]:
        """Todas as batidas do funcionário até `end` (o banco de horas precisa do histórico inteiro)."""
        query = select(Punch).where(Punch.employee_id == employee_id, Punch.ts < end)
        if not include_deleted:
            query = query.where(_not_deleted)
        return list(self.db.scalars(query.order_by(Punch.ts)))

    def has_any(self, employee_id: int) -> bool:
        """Inclui as excluídas: elas continuam sendo registro de ponto."""
        return bool(self.db.scalar(select(exists().where(Punch.employee_id == employee_id))))

    def add(self, punch: Punch) -> Punch:
        self.db.add(punch)
        self.db.flush()
        return punch

    def add_change(self, change: PunchChange) -> None:
        self.db.add(change)

    def changes_for(self, punch_id: int) -> list[PunchChange]:
        return list(
            self.db.scalars(
                select(PunchChange).where(PunchChange.punch_id == punch_id).order_by(PunchChange.at, PunchChange.id)
            )
        )
