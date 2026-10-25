from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AbsenceKind = Literal["atestado", "ferias", "licenca", "abonada", "folga"]


class AbsenceIn(BaseModel):
    employee_id: int
    kind: AbsenceKind
    first_day: date
    last_day: date
    minutes: int | None = None  # vazio = dias inteiros; senão, as horas abonadas por dia
    note: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def _check(self):
        if self.last_day < self.first_day:
            raise ValueError("O último dia não pode ser antes do primeiro")
        if (self.last_day - self.first_day).days > 365:
            raise ValueError("Lance no máximo um ano por vez")
        if self.minutes is not None and not 1 <= self.minutes <= 1440:
            raise ValueError("As horas abonadas por dia devem ficar entre 0h01 e 24h")
        if self.minutes is not None and self.kind == "folga":
            raise ValueError("A folga do banco vale o dia inteiro")
        return self


class DayAbsence(BaseModel):
    """Ausência que vale num dia do espelho."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    label: str
    minutes: int | None
    note: str


class AbsenceOut(DayAbsence):
    employee_id: int
    first_day: date
    last_day: date
    created_at: datetime
    created_by: str
