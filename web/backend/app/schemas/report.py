from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.absence import DayAbsence
from app.schemas.employee import EmployeeRef
from app.schemas.punch import PunchOut


class DayStatus(StrEnum):
    OK = "ok"
    INCOMPLETO = "incompleto"  # batida sem par
    FALTA = "falta"  # dia de trabalho sem nenhuma batida
    FOLGA = "folga"  # dia sem jornada prevista e sem batidas
    FERIADO = "feriado"  # feriado sem batidas
    FORA = "fora"  # antes da admissão ou depois do desligamento
    ANTES = "antes"  # antes do início do controle no sistema: não conta (nem como falta)
    AUSENCIA = "ausencia"  # dia de trabalho sem batidas, com ausência lançada (atestado, férias...)
    ANDAMENTO = "andamento"  # hoje, ou jornada ainda aberta


class DayReport(BaseModel):
    date: str
    punches: list[PunchOut]  # inclui as excluídas (deleted_at preenchido), que não contam horas
    # Horas trabalhadas já com a hora noturna reduzida (52min30s valem 1h)
    worked_ms: int = Field(serialization_alias="workedMs")
    night_ms: int = Field(serialization_alias="nightMs")  # horas noturnas (reduzidas), base do adicional
    expected_ms: int = Field(serialization_alias="expectedMs")
    balance_ms: int = Field(serialization_alias="balanceMs")  # só nos dias fechados, já com a tolerância
    status: DayStatus
    closed: bool  # dia que já terminou e entra no saldo
    holiday: str | None = None
    alerts: list[str] = []
    absence: DayAbsence | None = None  # ausência lançada que vale no dia
    credited_ms: int = Field(default=0, serialization_alias="creditedMs")  # abonado (conta como trabalhado)


class ClosureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    closed_at: datetime
    closed_by: str
    acknowledged_at: datetime | None


class ReopeningOut(BaseModel):
    """Fechamento anterior do mês, desfeito por uma reabertura (fica guardado na auditoria)."""

    reopened_at: datetime
    reopened_by: str
    note: str | None
    closed_at: datetime | None
    closed_by: str | None
    acknowledged_at: datetime | None


class MonthReport(BaseModel):
    employee: EmployeeRef
    month: str
    days: list[DayReport]
    total_ms: int = Field(serialization_alias="totalMs")
    night_ms: int = Field(serialization_alias="nightMs")
    expected_ms: int = Field(serialization_alias="expectedMs")
    balance_ms: int = Field(serialization_alias="balanceMs")  # saldo do mês (dias fechados)
    previous_balance_ms: int = Field(serialization_alias="previousBalanceMs")  # banco antes do mês
    bank_ms: int = Field(serialization_alias="bankMs")  # banco de horas ao fim do mês
    # Saldo trazido do controle anterior (já somado ao banco anterior a partir do mês do início)
    initial_balance_ms: int = Field(default=0, serialization_alias="initialBalanceMs")
    credited_ms: int = Field(default=0, serialization_alias="creditedMs")  # abonado no mês (dias fechados)
    # Dias de trabalho com ausência no mês, por tipo (ex.: {"atestado": 2})
    absence_days: dict[str, int] = Field(default_factory=dict, serialization_alias="absenceDays")
    control_from: date | None = Field(default=None, serialization_alias="controlFrom")  # primeiro dia que conta
    closure: ClosureOut | None = None
    reopenings: list[ReopeningOut] = []  # só no espelho do painel


class SummaryRow(BaseModel):
    """Uma linha do resumo do mês de todos os funcionários."""

    employee: EmployeeRef
    total_ms: int = Field(serialization_alias="totalMs")
    night_ms: int = Field(serialization_alias="nightMs")
    expected_ms: int = Field(serialization_alias="expectedMs")
    balance_ms: int = Field(serialization_alias="balanceMs")
    bank_ms: int = Field(serialization_alias="bankMs")
    absences: int
    incomplete: int
    alerts: int
    credited_ms: int = Field(default=0, serialization_alias="creditedMs")
    absence_days: dict[str, int] = Field(default_factory=dict, serialization_alias="absenceDays")
    closure: ClosureOut | None = None
