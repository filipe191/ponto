from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Company(Base):
    """Empresa atendida pelo sistema. Funcionários, feriados, admins e auditoria pertencem a uma empresa."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    # Aviso de privacidade (LGPD): a quem o funcionário pede acesso ou correção dos dados
    privacy_contact: Mapped[str] = mapped_column(String, default="", server_default="")
    # Empresa desativada: os admins dela não entram, os relógios e os celulares param
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("TRUE"))
    # Assina os relógios da empresa; trocar desliga todos eles de uma vez
    kiosk_secret: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Fuso que define o "dia" de cada batida. Só muda antes da primeira batida (ver CompanyService)
    timezone: Mapped[str] = mapped_column(String)
    # Batidas guardadas no relógio sem conexão são aceitas até X horas depois
    offline_max_hours: Mapped[int] = mapped_column(Integer)


class CompanyRule(Base):
    """Regras de jornada da empresa a partir de uma data. Mudar cria uma nova vigência e não altera o passado
    (o banco de horas soma o histórico inteiro, cada dia com a regra que valia nele)."""

    __tablename__ = "company_rules"
    __table_args__ = (UniqueConstraint("company_id", "valid_from", name="company_rules_company_from_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="RESTRICT"))
    valid_from: Mapped[date] = mapped_column(Date)
    # Tolerância diária (CLT art. 58 §1º): diferenças de até X minutos no dia não geram saldo
    tolerance_minutes: Mapped[int] = mapped_column(Integer)
    # Horário noturno e duração da hora noturna (urbano 22h–5h e 52min30s; rural: Lei 5.889/73)
    night_start_hour: Mapped[int] = mapped_column(Integer)
    night_end_hour: Mapped[int] = mapped_column(Integer)
    night_hour_minutes: Mapped[float] = mapped_column(Float)
    # Uma saída só fecha a entrada se vier até X horas depois
    max_shift_hours: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str] = mapped_column(String)
