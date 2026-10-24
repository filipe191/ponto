from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import PunchAction, PunchType
from app.schemas.common import Pin


class PunchRequest(BaseModel):
    pin: Pin = Field(default="", validate_default=True)


class PunchResult(BaseModel):
    name: str
    type: PunchType
    ts: datetime


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
    note: str | None
    original_ts: datetime | None
    original_type: PunchType | None
    deleted_at: datetime | None


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
