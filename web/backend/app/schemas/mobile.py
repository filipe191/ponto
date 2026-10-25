"""Contrato do app de celular (app/), o mesmo do antigo backend Spring: JSON em camelCase."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

TipoBatida = Literal["ENTRADA", "SAIDA"]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class BatidaRequest(CamelModel):
    id: str
    tipo: TipoBatida
    ocorrido_em: datetime
    uptime_ms: int | None = None
    origem: str | None = Field(default=None, max_length=100)
    observacao: str | None = Field(default=None, max_length=500)
    manual: bool = False


class LoteRequest(BaseModel):
    # Cada batida é validada separadamente: uma inválida vai para "rejeitadas" sem derrubar o lote
    batidas: list[dict] = Field(default_factory=list, max_length=500)


class Rejeitada(BaseModel):
    id: str
    motivo: str


class LoteResponse(BaseModel):
    aceitas: list[str] = []
    duplicadas: list[str] = []
    rejeitadas: list[Rejeitada] = []


class AjusteRequest(CamelModel):
    ocorrido_em: datetime | None = None
    tipo: TipoBatida | None = None
    observacao: str | None = Field(default=None, max_length=500)


class BatidaServidor(CamelModel):
    id: str
    tipo: TipoBatida
    ocorrido_em: datetime
    origem: str | None
    observacao: str | None
    manual: bool
    ajustado_em: datetime | None
    relogio_suspeito: bool


class SolicitacaoApp(CamelModel):
    """Pedido feito pelo app e o que o admin decidiu (para o funcionário acompanhar)."""

    id: int
    acao: str  # incluir, alterar, excluir
    tipo: TipoBatida | None  # pedido (incluir/alterar) ou o da batida atual
    ocorrido_em: datetime | None  # horário pedido (incluir/alterar) ou o da batida (excluir)
    horario_atual: datetime | None  # alterar/excluir: como a batida estava quando o pedido foi feito
    status: str  # pendente, aprovada, recusada
    pedido_em: datetime
    decidido_em: datetime | None
    motivo_decisao: str | None  # observação do admin (ex.: motivo da recusa)


class DiaResumo(CamelModel):
    data: date
    trabalhado_minutos: int
    trabalhado_formatado: str
    saldo_minutos: int
    dia_aberto: bool
    batidas: list[BatidaServidor]


class ResumoMes(CamelModel):
    inicio: date
    fim: date
    trabalhado_minutos: int
    esperado_minutos: int
    saldo_minutos: int
    trabalhado_formatado: str
    saldo_formatado: str
    dias: list[DiaResumo]
