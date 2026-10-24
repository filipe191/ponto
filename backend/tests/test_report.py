from datetime import date, timedelta

from app.core.config import settings
from app.schemas.report import DayStatus
from app.services.report_service import build_days
from app.services.shifts import pair_shifts
from tests.helpers import at, employee, punches

HOUR = 3600_000


def days_for(items, first, last, now, deleted=(), emp=None):
    shifts = pair_shifts(items, settings.max_shift)
    return build_days(shifts, list(deleted), emp or employee(), first, last, at(now))


def test_saldo_positivo_e_negativo():
    # 2026-03-02 é segunda, 03 é terça
    days = days_for(
        punches(
            ("entrada", "2026-03-02 08:00"),
            ("saida", "2026-03-02 18:00"),
            ("entrada", "2026-03-03 08:00"),
            ("saida", "2026-03-03 15:00"),
        ),
        date(2026, 3, 2),
        date(2026, 3, 3),
        now="2026-03-10 12:00",
    )
    assert [d.balance_ms for d in days] == [2 * HOUR, -1 * HOUR]
    assert all(d.status == DayStatus.OK for d in days)


def test_falta_e_folga():
    # sábado 07 e domingo 08 são folga; segunda 09 sem batida é falta
    days = days_for([], date(2026, 3, 7), date(2026, 3, 9), now="2026-03-10 12:00")
    assert [d.status for d in days] == [DayStatus.FOLGA, DayStatus.FOLGA, DayStatus.FALTA]
    assert [d.balance_ms for d in days] == [0, 0, -8 * HOUR]


def test_hoje_nao_entra_no_saldo():
    (day,) = days_for(
        punches(("entrada", "2026-03-10 08:00"), ("saida", "2026-03-10 12:00")),
        date(2026, 3, 10),
        date(2026, 3, 10),
        now="2026-03-10 12:30",
    )
    assert day.status == DayStatus.ANDAMENTO
    assert not day.closed and day.balance_ms == 0
    assert day.worked_ms == 4 * HOUR


def test_turno_noturno_aparece_no_dia_da_entrada():
    days = days_for(
        punches(("entrada", "2026-03-02 22:00"), ("saida", "2026-03-03 06:00")),
        date(2026, 3, 2),
        date(2026, 3, 3),
        now="2026-03-10 12:00",
    )
    assert days[0].worked_ms == 8 * HOUR and len(days[0].punches) == 2
    assert days[1].worked_ms == 0 and days[1].status == DayStatus.FALTA


def test_jornada_noturna_aberta_ontem_fica_em_andamento():
    (day,) = days_for(
        punches(("entrada", "2026-03-09 22:00")), date(2026, 3, 9), date(2026, 3, 9), now="2026-03-10 03:00"
    )
    assert day.status == DayStatus.ANDAMENTO and not day.closed


def test_batida_sem_par_e_incompleta():
    (day,) = days_for(
        punches(("entrada", "2026-03-02 08:00")), date(2026, 3, 2), date(2026, 3, 2), now="2026-03-10 12:00"
    )
    assert day.status == DayStatus.INCOMPLETO


def test_excluidas_aparecem_mas_nao_contam():
    (removed,) = punches(("saida", "2026-03-02 23:00"))
    removed.deleted_at = at("2026-03-03 09:00")
    (day,) = days_for(
        punches(("entrada", "2026-03-02 08:00"), ("saida", "2026-03-02 16:00")),
        date(2026, 3, 2),
        date(2026, 3, 2),
        now="2026-03-10 12:00",
        deleted=[removed],
    )
    assert day.worked_ms == 8 * HOUR
    assert len(day.punches) == 3 and day.punches[-1].deleted_at


def test_dias_antes_do_cadastro_nao_sao_falta():
    shifts = pair_shifts([], settings.max_shift)
    days = build_days(
        shifts, [], employee(), date(2026, 3, 2), date(2026, 3, 4), at("2026-03-10 12:00"), active_from=date(2026, 3, 4)
    )
    assert [d.status for d in days] == [DayStatus.FOLGA, DayStatus.FOLGA, DayStatus.FALTA]
    assert [d.expected_ms for d in days] == [0, 0, 8 * HOUR]


def test_jornada_personalizada():
    emp = employee(daily_minutes=360, workdays="6")  # só sábado, 6h
    days = days_for([], date(2026, 3, 6), date(2026, 3, 7), now="2026-03-10 12:00", emp=emp)
    assert [d.expected_ms for d in days] == [0, 6 * HOUR]
    assert days[1].balance_ms == -6 * HOUR
    assert timedelta(milliseconds=days[1].expected_ms) == timedelta(hours=6)
