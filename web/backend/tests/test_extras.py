"""Horas extras pagas: 50% no dia comum, 100% em domingo e feriado de folga; fora do banco de horas."""

from datetime import date

from app.core.config import settings
from app.services.report_service import build_days
from app.services.rules import RuleBook, RulePeriod
from app.services.shifts import pair_shifts
from tests.helpers import at, employee, punches
from tests.test_report import HOUR, normal_day


def book(mode: str, since=date(2000, 1, 1)) -> RuleBook:
    base = RulePeriod.from_settings()
    pay = RulePeriod(**{**base.__dict__, "valid_from": since, "overtime_mode": mode})
    return RuleBook(periods=[base, pay] if since != date(2000, 1, 1) else [pay])


def run(items, first, last, rules, holidays=None):
    shifts = pair_shifts(punches(*items), settings.max_shift)
    return build_days(shifts, [], employee(), first, last, at("2026-06-01 12:00"), holidays or {}, rules)


def test_pagar_separa_extras_e_desconto():
    items = (
        normal_day("2026-03-02", end="19:00")  # segunda: 10h, 2h extras (50%)
        + normal_day("2026-03-03", end="15:00")  # terça: 6h, 2h a descontar
        + [("entrada", "2026-03-08 08:00"), ("saida", "2026-03-08 12:00")]  # domingo: 4h (100%)
    )
    days = run(items, date(2026, 3, 2), date(2026, 3, 8), book("pagar"))
    by = {d.date: d for d in days}
    assert by["2026-03-02"].extra_ms == 2 * HOUR and by["2026-03-02"].extra_rest_ms == 0
    assert by["2026-03-03"].deficit_ms == 2 * HOUR
    assert by["2026-03-08"].extra_rest_ms == 4 * HOUR
    assert all(d.paid for d in days)


def test_feriado_trabalhado_e_100():
    items = normal_day("2026-04-21")  # Tiradentes, terça
    days = run(items, date(2026, 4, 21), date(2026, 4, 21), book("pagar"), {date(2026, 4, 21): "Tiradentes"})
    assert days[0].extra_rest_ms == 8 * HOUR and days[0].extra_ms == 0


def test_banco_nao_gera_extras():
    days = run(normal_day("2026-03-02", end="19:00"), date(2026, 3, 2), date(2026, 3, 2), book("banco"))
    assert not days[0].paid and days[0].extra_ms == 0 and days[0].balance_ms == 2 * HOUR


def test_regra_muda_no_meio_do_mes():
    items = normal_day("2026-03-02", end="19:00") + normal_day("2026-03-10", end="19:00")
    days = run(items, date(2026, 3, 2), date(2026, 3, 10), book("pagar", since=date(2026, 3, 9)))
    by = {d.date: d for d in days}
    assert not by["2026-03-02"].paid and by["2026-03-02"].extra_ms == 0  # antes da vigência: banco
    assert by["2026-03-10"].paid and by["2026-03-10"].extra_ms == 2 * HOUR


def test_folga_no_sabado_trabalhado_e_50():
    items = [("entrada", "2026-03-07 08:00"), ("saida", "2026-03-07 12:00")]  # sábado sem jornada (5x2)
    days = run(items, date(2026, 3, 7), date(2026, 3, 7), book("pagar"))
    assert days[0].extra_ms == 4 * HOUR and days[0].extra_rest_ms == 0
