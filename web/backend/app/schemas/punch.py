from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import PunchAction, PunchType
from app.schemas.common import Pin


class PunchRequest(BaseModel):
    pin: Pin = Field(default="", validate_default=True)
    # Batida guardada no relógio enquanto estava sem conexão: horário (do aparelho) em que foi feita
    offline_ts: datetime | None = None


class PunchResult(BaseModel):
    id: int
    receipt: str  # código do comprovante
    name: str
    type: PunchType
    ts: datetime
    offline: bool = False


class TodayPunch(BaseModel):
    employee_id: int
    name: str
    ts: datetime
    type: PunchType


class ManualPunchCreate(BaseModel):
    employee_id: int
    ts: datetime
    type: PunchType
    note: str | None = None


class PunchUpdate(BaseModel):
    ts: datetime | None = None
    type: PunchType | None = None
    note: str | None = None


class PunchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: datetime
    type: PunchType
    manual: bool
    offline: bool
    note: str | None
    original_ts: datetime | None
    original_type: PunchType | None
    deleted_at: datetime | None
    receipt: str


class PunchChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    at: datetime
    user: str
    action: PunchAction
    old_ts: datetime | None
    old_type: PunchType | None
    new_ts: datetime | None
    new_type: PunchType | None
    note: str | None


class MyReportRequest(BaseModel):
    """Consulta do próprio espelho no relógio, com o PIN."""

    pin: Pin = Field(default="", validate_default=True)
    month: str = ""
