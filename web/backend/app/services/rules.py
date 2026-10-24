"""Regras de jornada de uma empresa: qual vale em cada dia, e o fuso que define os dias."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, available_timezones

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BadRequest, NotFound
from app.models import Company, CompanyRule, Employee, MonthClosure, Punch
from app.services.audit import AuditLog
from app.utils.dates import month_of

SINCE_ALWAYS = date(2000, 1, 1)  # vigência da primeira regra de cada empresa


@dataclass(frozen=True)
class RulePeriod:
    """Regras que valem a partir de `valid_from` (até a próxima vigência)."""

    valid_from: date
    tolerance_minutes: int
    night_start_hour: int
    night_end_hour: int
    night_hour_minutes: float
    max_shift_hours: int

    @property
    def tolerance(self) -> timedelta:
        return timedelta(minutes=self.tolerance_minutes)

    @property
    def max_shift(self) -> timedelta:
        return timedelta(hours=self.max_shift_hours)

    @classmethod
    def from_settings(cls, valid_from: date = SINCE_ALWAYS) -> RulePeriod:
        """Os valores do .env: padrão das empresas novas."""
        return cls(
            valid_from=valid_from,
            tolerance_minutes=settings.tolerance_minutes,
            night_start_hour=settings.night_start_hour,
            night_end_hour=settings.night_end_hour,
            night_hour_minutes=settings.night_hour_minutes,
            max_shift_hours=settings.max_shift_hours,
        )


@dataclass
class RuleBook:
    """Fuso, prazo das batidas sem conexão e as vigências das regras de jornada de uma empresa."""

    tz: ZoneInfo = field(default_factory=lambda: settings.timezone)
    offline_max_hours: int = field(default_factory=lambda: settings.offline_max_hours)
    periods: list[RulePeriod] = field(default_factory=lambda: [RulePeriod.from_settings()])

    def on(self, day: date) -> RulePeriod:
        """Regra em vigor no dia (antes da primeira vigência, vale a primeira)."""
        current = self.periods[0]
        for period in self.periods:
            if period.valid_from <= day:
                current = period
        return current

    def max_shift_at(self, ts: datetime) -> timedelta:
        """Jornada máxima de uma jornada que começa em `ts` (regra do dia local da entrada)."""
        return self.on(ts.astimezone(self.tz).date()).max_shift

    @property
    def longest_shift(self) -> timedelta:
        """Maior jornada máxima de todas as vigências: margem segura para buscar batidas no banco."""
        return max(p.max_shift for p in self.periods)

    @property
    def current(self) -> RulePeriod:
        return self.on(datetime.now(self.tz).date())


def load_rules(db: Session, company_id: int | None) -> RuleBook:
    company = db.get(Company, company_id) if company_id else None
    if not company:
        return RuleBook()
    rows = db.scalars(
        select(CompanyRule).where(CompanyRule.company_id == company.id).order_by(CompanyRule.valid_from)
    ).all()
    periods = [
        RulePeriod(
            valid_from=r.valid_from,
            tolerance_minutes=r.tolerance_minutes,
            night_start_hour=r.night_start_hour,
            night_end_hour=r.night_end_hour,
            night_hour_minutes=r.night_hour_minutes,
            max_shift_hours=r.max_shift_hours,
        )
        for r in rows
    ]
    return RuleBook(
        tz=ZoneInfo(company.timezone),
        offline_max_hours=company.offline_max_hours,
        periods=periods or [RulePeriod.from_settings()],
    )


# ---------- Alteração das regras (superadmin, no painel da empresa) ----------

_RULE_FIELDS = {
    "tolerance_minutes": "tolerância",
    "night_start_hour": "início do noturno",
    "night_end_hour": "fim do noturno",
    "night_hour_minutes": "hora noturna",
    "max_shift_hours": "jornada máxima",
}


def _check_period(p: RulePeriod) -> None:
    if not 0 <= p.tolerance_minutes <= 60:
        raise BadRequest("A tolerância deve ficar entre 0 e 60 minutos")
    if not (0 <= p.night_start_hour <= 23 and 0 <= p.night_end_hour <= 23) or p.night_start_hour == p.night_end_hour:
        raise BadRequest("Informe o início e o fim do horário noturno (horas de 0 a 23, diferentes)")
    if not 30 <= p.night_hour_minutes <= 60:
        raise BadRequest("A hora noturna deve ter entre 30 e 60 minutos (urbano: 52,5; rural: 60)")
    if not 4 <= p.max_shift_hours <= 24:
        raise BadRequest("A jornada máxima deve ficar entre 4 e 24 horas")
    if p.valid_from < SINCE_ALWAYS:
        raise BadRequest("Data de vigência inválida")


def _label(p: RulePeriod) -> str:
    minutes = f"{p.night_hour_minutes:g}".replace(".", ",")
    return (
        f"tolerância {p.tolerance_minutes} min, noturno {p.night_start_hour}h–{p.night_end_hour}h "
        f"(hora de {minutes} min), jornada máxima {p.max_shift_hours} h"
    )


class RulesService:
    def __init__(self, db: Session, company_id: int):
        self.db = db
        self.company_id = company_id
        self.audit = AuditLog(db, company_id)

    def company(self) -> Company:
        company = self.db.get(Company, self.company_id)
        if not company:
            raise NotFound("Empresa não encontrada")
        return company

    def periods(self) -> list[CompanyRule]:
        return list(
            self.db.scalars(
                select(CompanyRule).where(CompanyRule.company_id == self.company_id).order_by(CompanyRule.valid_from)
            )
        )

    def add_period(self, period: RulePeriod, user: str) -> None:
        """Novas regras a partir de `valid_from`. O passado (e o banco de horas acumulado) não muda.

        Não pode começar num mês já fechado: o espelho fechado e a ciência do funcionário mudariam.
        """
        _check_period(period)
        closed = self.db.scalar(
            select(MonthClosure.month)
            .join(Employee, Employee.id == MonthClosure.employee_id)
            .where(Employee.company_id == self.company_id, MonthClosure.month >= month_of(period.valid_from))
            .order_by(MonthClosure.month.desc())
            .limit(1)
        )
        if closed:
            year, month = closed.split("-")
            raise BadRequest(
                f"O mês {month}/{year} já foi fechado: as novas regras precisam começar depois dele "
                "(ou reabra o mês)"
            )
        before = load_rules(self.db, self.company_id).on(period.valid_from)
        row = self.db.scalar(
            select(CompanyRule).where(
                CompanyRule.company_id == self.company_id, CompanyRule.valid_from == period.valid_from
            )
        )
        if not row:
            row = CompanyRule(company_id=self.company_id, valid_from=period.valid_from, created_by=user)
            self.db.add(row)
        for name in _RULE_FIELDS:
            setattr(row, name, getattr(period, name))
        self.audit.record(
            user,
            "regras.alteradas",
            f"Mudou as regras de jornada a partir de {period.valid_from:%d/%m/%Y}: "
            f"{_label(before)} → {_label(period)}",
            details={
                "valid_from": period.valid_from,
                "old": {k: getattr(before, k) for k in _RULE_FIELDS},
                "new": {k: getattr(period, k) for k in _RULE_FIELDS},
            },
        )
        self.db.commit()

    def update_settings(self, user: str, tz: str | None, offline_max_hours: int | None) -> Company:
        company = self.company()
        changes = []
        if tz is not None and tz != company.timezone:
            if tz not in available_timezones():
                raise BadRequest("Fuso horário inválido (ex.: America/Sao_Paulo)")
            # O fuso define onde cada dia começa: mudar com batidas já registradas mudaria o passado
            has_punches = self.db.scalar(
                select(exists().where(Punch.employee_id == Employee.id, Employee.company_id == company.id))
            )
            if has_punches:
                raise BadRequest("O fuso só pode ser mudado antes da primeira batida da empresa")
            changes.append(f"fuso {company.timezone} → {tz}")
            company.timezone = tz
        if offline_max_hours is not None and offline_max_hours != company.offline_max_hours:
            if not 0 <= offline_max_hours <= 72:
                raise BadRequest("O prazo das batidas sem conexão deve ficar entre 0 e 72 horas")
            changes.append(f"batidas sem conexão aceitas até {company.offline_max_hours} h → {offline_max_hours} h")
            company.offline_max_hours = offline_max_hours
        if changes:
            self.audit.record(user, "regras.alteradas", "Alterou os ajustes da empresa: " + "; ".join(changes))
            self.db.commit()
        return company


def default_rule(company_id: int, user: str) -> CompanyRule:
    """Primeira regra de uma empresa nova: os valores do .env, desde sempre."""
    p = RulePeriod.from_settings()
    return CompanyRule(
        company_id=company_id,
        valid_from=p.valid_from,
        created_by=user,
        **{name: getattr(p, name) for name in _RULE_FIELDS},
    )
