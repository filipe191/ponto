from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import PunchAction, PunchType
from app.schemas.common import Pin


class PunchRequest(BaseModel):
    pin: Pin = Field(default="", validate_default=True)
    # Batida guardada no relógio enquanto estava sem conexão: horário (do aparelho) em que foi feita
    offline_ts: datetime | None = None


class TodayPunch(BaseModel):
    ts: datetime
    type: PunchType


class PunchResult(BaseModel):
    id: int
    receipt: str  # código do comprovante
    name: str
    type: PunchType
    ts: datetime
    offline: bool = False
    # Só as batidas de hoje de quem bateu: o relógio não mostra mais as dos colegas
    today: list[TodayPunch] = []
    pin_short: bool = False  # PIN antigo de 4 ou 5 dígitos: pedir um novo ao admin


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
    source: str  # relogio, app ou admin
    clock_suspect: bool  # batida do celular com horário à frente do servidor


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
