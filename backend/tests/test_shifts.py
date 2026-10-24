from datetime import date, timedelta

from app.core.config import settings
from app.services.shifts import pair_shifts
from tests.helpers import at, punches

MAX = settings.max_shift


def test_dia_normal_com_almoco():
    shifts = pair_shifts(
        punches(
            ("entrada", "2026-03-02 08:00"),
            ("saida", "2026-03-02 12:00"),
            ("entrada", "2026-03-02 13:00"),
            ("saida", "2026-03-02 17:00"),
        ),
        MAX,
    )
    assert [s.complete for s in shifts] == [True, True]
    assert sum((s.worked for s in shifts), timedelta()) == timedelta(hours=8)


def test_turno_que_passa_da_meia_noite_conta_no_dia_da_entrada():
    (shift,) = pair_shifts(punches(("entrada", "2026-03-02 22:00"), ("saida", "2026-03-03 06:00")), MAX)
    assert shift.complete
    assert shift.day == date(2026, 3, 2)
    assert shift.worked == timedelta(hours=8)


def test_saida_longe_demais_nao_fecha_a_entrada():
    shifts = pair_shifts(punches(("entrada", "2026-03-02 08:00"), ("saida", "2026-03-03 09:00")), MAX)
    assert [s.complete for s in shifts] == [False, False]


def test_duas_entradas_seguidas():
    shifts = pair_shifts(
        punches(("entrada", "2026-03-02 08:00"), ("entrada", "2026-03-02 09:00"), ("saida", "2026-03-02 17:00")),
        MAX,
    )
    assert [s.complete for s in shifts] == [False, True]
    assert shifts[1].worked == timedelta(hours=8)


def test_saida_sem_entrada():
    (shift,) = pair_shifts(punches(("saida", "2026-03-02 17:00")), MAX)
    assert not shift.complete and not shift.pending


def test_entrada_aberta_esta_em_andamento_ate_o_limite():
    (shift,) = pair_shifts(punches(("entrada", "2026-03-02 22:00")), MAX)
    assert shift.is_open(at("2026-03-03 05:00"), MAX)
    assert not shift.is_open(at("2026-03-03 15:00"), MAX)
