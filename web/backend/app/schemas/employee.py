from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import NewPin


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


class ScheduleIn(BaseModel):
    """Jornada: minutos de cada dia da semana (seg … dom) ou uma escala que se repete a cada N dias."""

    kind: Literal["semana", "ciclo"] = "semana"
    minutes: list[DailyMinutes]
    cycle_start: date | None = None  # escala: o dia que corresponde ao primeiro valor

    @model_validator(mode="after")
    def _shape(self):
        if self.kind == "semana" and len(self.minutes) != 7:
            raise ValueError("Informe os minutos dos 7 dias da semana")
        if self.kind == "ciclo":
            if not 2 <= len(self.minutes) <= 28:
                raise ValueError("A escala deve ter de 2 a 28 dias")
            if not self.cycle_start:
                raise ValueError("Informe o dia em que a escala começa")
            if not any(self.minutes):
                raise ValueError("A escala precisa de pelo menos um dia de trabalho")
        return self

    @classmethod
    def legacy(cls, daily_minutes: int, workdays: str) -> "ScheduleIn":
        return cls(minutes=[daily_minutes if str(d) in workdays else 0 for d in range(1, 8)])


class EmployeeCreate(BaseModel):
    name: str = Field(default="", validate_default=True)
    pin: NewPin = Field(default="", validate_default=True)
    # Jornada: `schedule` (por dia ou escala) ou, no formato antigo, os mesmos minutos nos dias de trabalho
    schedule: ScheduleIn | None = None
    daily_minutes: DailyMinutes = 480
    workdays: Workdays = "12345"
    hired_on: date | None = None  # padrão: hoje
    control_start: date | None = None  # vazio = o início do controle da empresa
    initial_balance_minutes: int = 0  # banco de horas trazido do controle anterior
    initial_balance_note: str = ""

    @field_validator("name")
    @classmethod
    def _name_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Nome obrigatório")
        return value

    @property
    def schedule_spec(self) -> ScheduleIn:
        return self.schedule or ScheduleIn.legacy(self.daily_minutes, self.workdays)


class EmployeeUpdate(BaseModel):
    name: str | None = None
    pin: NewPin | None = None
    active: bool | None = None
    schedule: ScheduleIn | None = None
    daily_minutes: DailyMinutes | None = None  # formato antigo (no lugar de `schedule`)
    workdays: Workdays | None = None
    # A nova jornada vale a partir desta data (padrão: hoje); o passado não muda
    schedule_from: date | None = None
    hired_on: date | None = None
    terminated_on: date | None = None  # enviar null explicitamente apaga o desligamento
    control_start: date | None = None  # enviar null volta ao início do controle da empresa
    initial_balance_minutes: int | None = None
    initial_balance_note: str | None = None

    @field_validator("name", "pin", mode="before")
    @classmethod
    def _blank_is_none(cls, value):
        return value.strip() or None if isinstance(value, str) else value

    @model_validator(mode="after")
    def _dates_in_order(self):
        if self.hired_on and self.terminated_on and self.terminated_on < self.hired_on:
            raise ValueError("O desligamento não pode ser antes da admissão")
        return self


class EmployeeRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    valid_from: date
    kind: str
    minutes: list[int]
    cycle_start: date | None
    label: str
    weekly_minutes: int | None  # total da semana (jornada semanal)
    daily_minutes: int  # formato antigo: o maior dia
    workdays: str


class EmployeeOut(EmployeeRef):
    active: bool
    created_at: datetime
    hired_on: date
    terminated_on: date | None
    control_start: date | None
    initial_balance_minutes: int
    initial_balance_note: str
    pin_short: bool  # PIN antigo de 4 ou 5 dígitos: trocar
    anonymized_at: datetime | None
    retention_due: bool  # passou do prazo de guarda e ainda não foi anonimizado
    daily_minutes: int  # jornada em vigor hoje (formato antigo: o maior dia)
    workdays: str
    schedule_label: str  # jornada em vigor hoje, por extenso
    schedules: list[ScheduleOut]


class EmployeeCreated(BaseModel):
    id: int
