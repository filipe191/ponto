"""Ausências justificadas no espelho: não viram falta, abonam (ou saem do banco) e respeitam a jornada."""

from datetime import date, timedelta

from app.core.config import settings
from app.models import Absence
from app.services.report_service import build_days
from app.services.shifts import pair_shifts
from tests.helpers import at, employee, punches
from tests.test_report import HOUR, normal_day


def absent(kind: str, first: date, last: date, minutes: int | None = None) -> dict[date, Absence]:
    a = Absence(id=1, employee_id=1, kind=kind, first_day=first, last_day=last, minutes=minutes, note="")
    out, day = {}, first
    while day <= last:
        out[day] = a
        day += timedelta(days=1)
    return out


def run(items, first, last, absences):
    shifts = pair_shifts(punches(*items), settings.max_shift)
    return build_days(shifts, [], employee(), first, last, at("2026-03-20 12:00"), {}, None, None, absences)


def test_atestado_abona_o_dia_inteiro():
    days = run([], date(2026, 3, 2), date(2026, 3, 3), absent("atestado", date(2026, 3, 2), date(2026, 3, 2)))
    assert days[0].status == "ausencia" and days[0].balance_ms == 0 and days[0].credited_ms == 8 * HOUR
    assert days[0].absence.label == "Atestado médico"
    assert days[1].status == "falta" and days[1].balance_ms == -8 * HOUR  # o dia seguinte continua falta


def test_ferias_no_fim_de_semana_nao_contam_dias():
    # Férias de sexta 06/03 a segunda 09/03: sábado e domingo continuam folga, sem abono
    days = run([], date(2026, 3, 6), date(2026, 3, 9), absent("ferias", date(2026, 3, 6), date(2026, 3, 9)))
    assert [d.status for d in days] == ["ausencia", "folga", "folga", "ausencia"]
    assert [d.credited_ms // HOUR for d in days] == [8, 0, 0, 8]
    assert all(d.balance_ms == 0 for d in days)


def test_folga_do_banco_nao_e_falta_mas_desconta():
    days = run([], date(2026, 3, 2), date(2026, 3, 2), absent("folga", date(2026, 3, 2), date(2026, 3, 2)))
    assert days[0].status == "ausencia" and days[0].credited_ms == 0 and days[0].balance_ms == -8 * HOUR


def test_abono_parcial_com_trabalho_no_dia():
    # Consulta de 2h abonada; trabalhou 6h (08–12 e 13–15): dia fechado sem saldo
    items = normal_day("2026-03-02", end="15:00")
    days = run(items, date(2026, 3, 2), date(2026, 3, 2), absent("atestado", date(2026, 3, 2), date(2026, 3, 2), 120))
    assert days[0].status == "ok" and days[0].credited_ms == 2 * HOUR and days[0].balance_ms == 0


def test_abono_parcial_nao_passa_da_jornada():
    days = run([], date(2026, 3, 2), date(2026, 3, 2), absent("abonada", date(2026, 3, 2), date(2026, 3, 2), 600))
    assert days[0].credited_ms == 8 * HOUR and days[0].balance_ms == 0
