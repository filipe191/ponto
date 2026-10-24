from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import Pin


def _check_minutes(value: int) -> int:
    if not 0 <= value <= 1440:
        raise ValueError("Jornada diária deve ficar entre 0h e 24h")
    return value


def _check_workdays(value: str) -> str:
    if not set(value) <= set("1234567"):
        raise ValueError("Dias de trabalho inválidos")
    return "".join(sorted(set(value)))


DailyMinutes = Annotated[int, AfterValidator(_check_minutes)]
# Dias da semana ISO: "1" = segunda … "7" = domingo
Workdays = Annotated[str, AfterValidator(_check_workdays)]


class EmployeeCreate(BaseModel):
    name: str = Field(default="", validate_default=True)
    pin: Pin = Field(default="", validate_default=True)
    daily_minutes: DailyMinutes = 480
    workdays: Workdays = "12345"

    @field_validator("name")
    @classmethod
    def _name_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Nome obrigatório")
        return value


class EmployeeUpdate(BaseModel):
    name: str | None = None
    pin: Pin | None = None
    active: bool | None = None
    daily_minutes: DailyMinutes | None = None
    workdays: Workdays | None = None

    @field_validator("name", "pin", mode="before")
    @classmethod
    def _blank_is_none(cls, value):
        return value.strip() or None if isinstance(value, str) else value


class EmployeeRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class EmployeeOut(EmployeeRef):
    active: bool
    created_at: datetime
    daily_minutes: int
    workdays: str


class EmployeeCreated(BaseModel):
    id: int
