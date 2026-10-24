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


class ClosureRequest(BaseModel):
    month: str
    employee_id: int | None = None  # None = todos os funcionários com contrato no mês
