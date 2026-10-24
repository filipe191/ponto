from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.employee import EmployeeRef
from app.schemas.punch import PunchOut


class DayStatus(StrEnum):
    OK = "ok"
    INCOMPLETO = "incompleto"  # batida sem par
    FALTA = "falta"  # dia de trabalho sem nenhuma batida
    FOLGA = "folga"  # dia sem jornada prevista e sem batidas
    ANDAMENTO = "andamento"  # hoje, ou jornada ainda aberta


class DayReport(BaseModel):
    date: str
    punches: list[PunchOut]  # inclui as excluídas (deleted_at preenchido), que não contam horas
    worked_ms: int = Field(serialization_alias="workedMs")
    expected_ms: int = Field(serialization_alias="expectedMs")
    balance_ms: int = Field(serialization_alias="balanceMs")  # só nos dias fechados
    status: DayStatus
    closed: bool  # dia que já terminou e entra no saldo


class MonthReport(BaseModel):
    employee: EmployeeRef
    month: str
    days: list[DayReport]
    total_ms: int = Field(serialization_alias="totalMs")
    expected_ms: int = Field(serialization_alias="expectedMs")
    balance_ms: int = Field(serialization_alias="balanceMs")  # saldo do mês (dias fechados)
    previous_balance_ms: int = Field(serialization_alias="previousBalanceMs")  # banco antes do mês
    bank_ms: int = Field(serialization_alias="bankMs")  # banco de horas ao fim do mês
