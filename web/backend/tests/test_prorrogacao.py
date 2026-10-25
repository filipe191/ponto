"""Prorrogação do horário noturno (Súmula 60 do TST): o que passa das 5h numa jornada que cobriu a noite toda."""

from datetime import date

from app.core.config import settings
from app.services.report_service import build_days
from app.services.rules import RuleBook, RulePeriod
from app.services.shifts import pair_shifts
from tests.helpers import at, employee, punches

HOUR = 3_600_000
REDUCED = 60 / 52.5  # hora noturna urbana


def book(extension: bool = True) -> RuleBook:
    return RuleBook(periods=[RulePeriod(**{**RulePeriod.from_settings().__dict__, "night_extension": extension})])


def run(items, rules):
    shifts = pair_shifts(punches(*items), settings.max_shift)
    return build_days(shifts, [], employee(), date(2026, 3, 2), date(2026, 3, 3), at("2026-03-10 12:00"), {}, rules)


def ms(hours: float) -> int:
    return round(hours * HOUR)


def test_noite_inteira_e_mais_duas_horas():
    days = run([("entrada", "2026-03-02 22:00"), ("saida", "2026-03-03 07:00")], book())
    # 22h–5h (7h) + 5h–7h prorrogadas (2h): 9h reais noturnas, com hora reduzida
    assert days[0].night_ms == ms(9 * REDUCED)
    assert days[0].worked_ms == ms(9 * REDUCED)


def test_sem_a_regra_so_ate_as_5h():
    days = run([("entrada", "2026-03-02 22:00"), ("saida", "2026-03-03 07:00")], book(extension=False))
    assert days[0].night_ms == ms(7 * REDUCED)
    assert days[0].worked_ms == ms(2 + 7 * REDUCED)


def test_jornada_com_intervalo_conta_como_uma_so():
    # 22h–1h, intervalo, 2h–7h: a segunda parte começa no dia 3, mas é a mesma jornada
    items = [("entrada", "2026-03-02 22:00"), ("saida", "2026-03-03 01:00"),
             ("entrada", "2026-03-03 02:00"), ("saida", "2026-03-03 07:00")]
    days = run(items, book())
    total_night = sum(d.night_ms for d in days)
    assert abs(total_night - ms(8 * REDUCED)) <= 2  # 6h reais dentro do horário + 2h prorrogadas (arredondamento por dia)


def test_quem_entra_depois_das_22h_nao_prorroga():
    days = run([("entrada", "2026-03-02 23:00"), ("saida", "2026-03-03 07:00")], book())
    assert days[0].night_ms == ms(6 * REDUCED)
