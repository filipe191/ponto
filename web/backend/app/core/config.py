"""Configuração da aplicação, lida das variáveis de ambiente."""

import secrets
from datetime import timedelta
from functools import cached_property
from zoneinfo import ZoneInfo

from pydantic import PrivateAttr, model_validator
from pydantic_settings import BaseSettings
from sqlalchemy import URL


class Settings(BaseSettings):
    # Postgres (mesmos nomes das variáveis padrão do libpq)
    pghost: str = "localhost"
    pgport: int = 5432
    pgdatabase: str = "ponto"
    pguser: str = "ponto"
    pgpassword: str = ""

    # Login inicial (tela de ponto e painel de administração). Só é usado para
    # criar a conta na primeira subida; depois a senha fica no banco e é trocada em /senha.
    admin_user: str = "admin"
    admin_password: str = "ponto123"

    # Sessão em cookie assinado. Sem SECRET_KEY, gera uma chave a cada subida
    # (as sessões abertas caem quando o container reinicia).
    secret_key: str = ""
    session_days: int = 30
    # Sessão do admin cai depois de X horas sem uso (além do limite de session_days)
    session_idle_hours: int = 8
    # Verificação em duas etapas (código no celular) obrigatória para todos os administradores
    admin_2fa_required: bool = True
    # Aparelho liberado como relógio (só bate ponto). O admin pode desligar todos de uma vez.
    kiosk_days: int = 365
    # Login do admin feito no próprio aparelho do relógio expira rápido, para não ficar aberto
    admin_on_kiosk_minutes: int = 30
    cookie_secure: bool = False  # True quando estiver atrás de HTTPS

    # Chave do hash dos PINs (obrigatória). Nunca troque depois de definida: os PINs param de funcionar.
    pin_key: str = ""

    # Fuso usado para definir o "dia" de cada batida
    tz: str = "America/Sao_Paulo"

    # Duração máxima de uma jornada: uma saída só fecha a entrada se vier até X horas depois.
    # Permite turnos que passam da meia-noite (a jornada conta no dia da entrada).
    max_shift_hours: int = 16

    # Tolerância diária (CLT art. 58 §1º): diferenças de até X minutos no dia não geram saldo
    tolerance_minutes: int = 10

    # Trabalho noturno urbano (CLT art. 73): das 22h às 5h, hora noturna de 52min30s.
    # Rural: lavoura 21h–5h e pecuária 20h–4h, com hora de 60 min (Lei 5.889/73).
    night_start_hour: int = 22
    night_end_hour: int = 5
    night_hour_minutes: float = 52.5

    # Batidas guardadas no relógio sem conexão são aceitas até X horas depois
    offline_max_hours: int = 24

    # Chave do app de celular: vale X dias desde que foi gerada e é revogada sozinha depois
    # de Y dias sem uso. O painel avisa quando faltam menos de Z dias para vencer.
    device_key_days: int = 365
    device_idle_days: int = 90
    device_warn_days: int = 30

    # LGPD: registros de ponto ficam guardados X anos depois do desligamento (prazo de
    # prescrição trabalhista); depois disso o painel oferece anonimizar o ex-funcionário
    retention_years: int = 5
    # Aviso de privacidade (/privacidade): quem controla os dados e como pedir acesso ou correção
    empresa_nome: str = ""
    privacidade_contato: str = ""

    # Documentação interativa em /api/docs (deixe desligada em produção)
    api_docs: bool = False

    _secret_from_env: bool = PrivateAttr(False)

    @model_validator(mode="after")
    def _secret_or_random(self) -> "Settings":
        self._secret_from_env = bool(self.secret_key)
        self.secret_key = self.secret_key or secrets.token_hex(32)
        return self

    @property
    def secret_key_from_env(self) -> bool:
        return self._secret_from_env

    @cached_property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.pguser,
            password=self.pgpassword,
            host=self.pghost,
            port=self.pgport,
            database=self.pgdatabase,
        )

    @cached_property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.tz)

    @cached_property
    def max_shift(self) -> timedelta:
        return timedelta(hours=self.max_shift_hours)


settings = Settings()
