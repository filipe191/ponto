from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    updated_at: datetime
    superadmin: bool
    read_only: bool  # só consulta


class AdminCreate(BaseModel):
    username: str = ""
    password: str = ""
    read_only: bool = False  # só consulta (ex.: contabilidade)


class HolidayOut(BaseModel):
    date: date
    name: str
    national: bool  # calculado pelo sistema (não pode ser removido)
    yearly: bool = False  # repete todo ano (cadastrado em `since`)
    since: date | None = None


class HolidayCreate(BaseModel):
    date: date
    name: str = ""
    yearly: bool = False  # repete no mesmo dia e mês todo ano

    @field_validator("name")
    @classmethod
    def _name_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Informe o nome do feriado")
        return value


class MovableHolidays(BaseModel):
    year: int
    items: list[Literal["carnaval", "corpus_christi"]]


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    created_by: str
    last_used_at: datetime | None
    revoked_at: datetime | None
    expires_at: datetime


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


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    at: datetime
    user: str
    action: str
    summary: str
    employee_id: int | None
    details: dict | None
    ip: str | None


class Alerts(BaseModel):
    pin_blocks: list[AuditOut]  # bloqueios do relógio por PINs errados nas últimas 24h
    short_pins: int  # funcionários ativos com PIN antigo de 4 ou 5 dígitos
    devices_expiring: int  # chaves de celular que vencem nos próximos dias
    retention_due: int  # ex-funcionários que passaram do prazo de guarda (anonimizar)
    holidays_missing_year: int | None = None  # em dezembro: o ano seguinte ainda sem feriado da empresa


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    privacy_contact: str
    active: bool
    created_at: datetime
    public_code: str  # link do aviso de privacidade: /privacidade?e=<código>
    notify_email: str  # quem recebe o aviso das solicitações do app


class CompanyCreate(BaseModel):
    name: str = ""
    privacy_contact: str = ""
    notify_email: str = ""
    # Primeiro administrador da empresa (senha provisória: troca no primeiro acesso)
    admin_username: str = ""
    admin_password: str = ""


class CompanyUpdate(BaseModel):
    name: str | None = None
    privacy_contact: str | None = None
    notify_email: str | None = None
    active: bool | None = None


class CompanySwitch(BaseModel):
    company_id: int


class RulePeriodIn(BaseModel):
    valid_from: date
    tolerance_minutes: int
    night_start_hour: int
    night_end_hour: int
    night_hour_minutes: float
    max_shift_hours: int
    overtime_mode: str = "banco"  # "banco" ou "pagar"
    overtime_pct: int = 50
    rest_overtime_pct: int = 100


class RulePeriodOut(RulePeriodIn):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    created_by: str


class RulesOut(BaseModel):
    timezone: str
    offline_max_hours: int
    control_start: date | None  # início do controle (vazio = desde a admissão de cada funcionário)
    periods: list[RulePeriodOut]  # da mais antiga para a mais nova
    can_edit: bool  # só o superadmin altera


class RulesSettingsIn(BaseModel):
    timezone: str | None = None
    offline_max_hours: int | None = None
    control_start: date | None = None  # só muda quando enviado; null = desde a admissão
