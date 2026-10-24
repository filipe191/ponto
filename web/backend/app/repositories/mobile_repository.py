from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import EmployeeDevice, Punch, PunchRequest, RequestStatus


class DeviceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, device_id: int) -> EmployeeDevice | None:
        return self.db.get(EmployeeDevice, device_id)

    def by_key_hash(self, key_hash: str) -> EmployeeDevice | None:
        return self.db.scalar(select(EmployeeDevice).where(EmployeeDevice.key_hash == key_hash))

    def list_for_employee(self, employee_id: int) -> list[EmployeeDevice]:
        return list(
            self.db.scalars(
                select(EmployeeDevice).where(EmployeeDevice.employee_id == employee_id).order_by(EmployeeDevice.id)
            )
        )

    def add(self, device: EmployeeDevice) -> EmployeeDevice:
        self.db.add(device)
        self.db.flush()
        return device


class RequestRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, request_id: int) -> PunchRequest | None:
        return self.db.get(PunchRequest, request_id)

    def by_client_id(self, client_id: str) -> PunchRequest | None:
        return self.db.scalar(select(PunchRequest).where(PunchRequest.client_id == client_id))

    def pending_for_punch(self, punch_id: int) -> PunchRequest | None:
        return self.db.scalar(
            select(PunchRequest).where(
                PunchRequest.punch_id == punch_id, PunchRequest.status == RequestStatus.PENDENTE
            )
        )

    def list(self, status: str | None) -> list[PunchRequest]:
        query = select(PunchRequest).options(joinedload(PunchRequest.employee), joinedload(PunchRequest.punch))
        if status:
            query = query.where(PunchRequest.status == status)
        return list(self.db.scalars(query.order_by(PunchRequest.requested_at.desc()).limit(200)))

    def add(self, request: PunchRequest) -> PunchRequest:
        self.db.add(request)
        self.db.flush()
        return request


def punch_by_public_id(db: Session, employee_id: int, public_id: str) -> Punch | None:
    """Acha a batida pelo id que o app conhece (UUID do celular ou "web-N"), só do próprio funcionário."""
    if public_id.startswith("web-"):
        number = public_id.removeprefix("web-")
        if not number.isdigit():
            return None
        punch = db.get(Punch, int(number))
    else:
        punch = db.scalar(select(Punch).where(Punch.client_id == public_id))
    if not punch or punch.employee_id != employee_id or punch.deleted_at:
        return None
    return punch


def punches_between(db: Session, employee_id: int, start: datetime, end: datetime) -> list[Punch]:
    return list(
        db.scalars(
            select(Punch)
            .where(Punch.employee_id == employee_id, Punch.ts >= start, Punch.ts < end, Punch.deleted_at.is_(None))
            .order_by(Punch.ts)
        )
    )


def last_punch(db: Session, employee_id: int) -> Punch | None:
    return db.scalar(
        select(Punch)
        .where(Punch.employee_id == employee_id, Punch.deleted_at.is_(None))
        .order_by(Punch.ts.desc())
        .limit(1)
    )
