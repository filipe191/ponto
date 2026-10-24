from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    updated_at: datetime


class AdminCreate(BaseModel):
    username: str = ""
    password: str = ""


class HolidayOut(BaseModel):
    date: date
    name: str
    national: bool  # calculado pelo sistema (não pode ser removido)


class HolidayCreate(BaseModel):
    date: date
    name: str = ""

    @field_validator("name")
    @classmethod
    def _name_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Informe o nome do feriado")
        return value


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    created_by: str
    last_used_at: datetime | None
    revoked_at: datetime | None


class DeviceCreate(BaseModel):
    name: str = ""

    @field_validator("name")
    @classmethod
    def _name_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Dê um nome ao celular (ex.: iPhone da Ana)")
        return value


class DeviceCreated(DeviceOut):
    key: str  # mostrada uma única vez


class RequestOut(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    action: str
    status: str
    # Batida atual (alterar/excluir) e o que foi pedido (incluir/alterar)
    current_ts: datetime | None
    current_type: str | None
    ts: datetime | None
    type: str | None
    note: str | None
    requested_at: datetime
    decided_at: datetime | None
    decided_by: str | None
    decision_note: str | None


class RequestDecision(BaseModel):
    note: str = ""


class ClosureRequest(BaseModel):
    month: str
    employee_id: int | None = None  # None = todos os funcionários com contrato no mês
