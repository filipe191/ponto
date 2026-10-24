from datetime import date, timedelta

from app.core.config import settings
from app.schemas.report import DayStatus
from app.services.report_service import build_days
from app.services.shifts import pair_shifts
from app.utils.holidays import national_holidays
from tests.helpers import at, employee, punches

HOUR = 3600_000
MIN = 60_000


def days_for(items, first, last, now, deleted=(), emp=None, holidays=None):
    shifts = pair_shifts(items, settings.max_shift)
    return build_days(shifts, list(deleted), emp or employee(), first, last, at(now), holidays or {})


def normal_day(day: str, start="08:00", lunch=("12:00", "13:00"), end="17:00"):
    return [
        ("entrada", f"{day} {start}"),
        ("saida", f"{day} {lunch[0]}"),
        ("entrada", f"{day} {lunch[1]}"),
        ("saida", f"{day} {end}"),
    ]


def test_saldo_positivo_e_negativo():
    # 2026-03-02 é segunda, 03 é terça
    days = days_for(
        punches(*normal_day("2026-03-02", end="19:00"), *normal_day("2026-03-03", end="16:00")),
        date(2026, 3, 2),
        date(2026, 3, 3),
        now="2026-03-10 12:00",
    )
    assert [d.balance_ms for d in days] == [2 * HOUR, -1 * HOUR]
    assert all(d.status == DayStatus.OK for d in days)


def test_tolerancia_de_10_minutos_no_dia():
    days = days_for(
        punches(*normal_day("2026-03-02", end="17:08"), *normal_day("2026-03-03", end="17:11")),
        date(2026, 3, 2),
        date(2026, 3, 3),
        now="2026-03-10 12:00",
    )
    assert days[0].balance_ms == 0  # 8 min: dentro da tolerância
    assert days[1].balance_ms == 11 * MIN  # passou da tolerância: conta tudo


def test_falta_e_folga():
    # sábado 07 e domingo 08 são folga; segunda 09 sem batida é falta
    days = days_for([], date(2026, 3, 7), date(2026, 3, 9), now="2026-03-10 12:00")
    assert [d.status for d in days] == [DayStatus.FOLGA, DayStatus.FOLGA, DayStatus.FALTA]
    assert [d.balance_ms for d in days] == [0, 0, -8 * HOUR]


def test_feriado_nao_tem_jornada():
    holidays = national_holidays(2026)
    (day,) = days_for([], date(2026, 4, 21), date(2026, 4, 21), now="2026-05-10 12:00", holidays=holidays)
    assert day.status == DayStatus.FERIADO and day.holiday == "Tiradentes"
    assert day.expected_ms == 0 and day.balance_ms == 0


def test_trabalho_em_feriado_vira_saldo_e_alerta():
    holidays = national_holidays(2026)
    (day,) = days_for(
        punches(("entrada", "2026-04-21 08:00"), ("saida", "2026-04-21 12:00")),
        date(2026, 4, 21),
        date(2026, 4, 21),
        now="2026-05-10 12:00",
        holidays=holidays,
    )
    assert day.balance_ms == 4 * HOUR
    assert "Trabalho em dia sem jornada prevista" in day.alerts


def test_fora_do_contrato():
    emp = employee(hired_on=date(2026, 3, 4), terminated_on=date(2026, 3, 5))
    days = days_for([], date(2026, 3, 3), date(2026, 3, 6), now="2026-03-10 12:00", emp=emp)
    assert [d.status for d in days] == [DayStatus.FORA, DayStatus.FALTA, DayStatus.FALTA, DayStatus.FORA]


def test_jornada_com_vigencia_nao_muda_o_passado():
    emp = employee(schedules=[(date(2026, 1, 1), 480, "12345"), (date(2026, 3, 4), 360, "12345")])
    days = days_for([], date(2026, 3, 3), date(2026, 3, 4), now="2026-03-10 12:00", emp=emp)
    assert [d.expected_ms for d in days] == [8 * HOUR, 6 * HOUR]


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


def test_hora_noturna_reduzida():
    # 22:00 → 05:00 são 7h reais de noturno = 8h contadas (hora de 52min30s)
    (day, _) = days_for(
        punches(("entrada", "2026-03-02 22:00"), ("saida", "2026-03-03 05:00")),
        date(2026, 3, 2),
        date(2026, 3, 3),
        now="2026-03-10 12:00",
    )
    assert day.night_ms == 8 * HOUR
    assert day.worked_ms == 8 * HOUR
    assert day.balance_ms == 0


def test_noturno_parcial():
    # 18:00 → 23:30: 1h30 real de noturno = 1h42m51s contadas
    (day,) = days_for(
        punches(("entrada", "2026-03-02 18:00"), ("saida", "2026-03-02 23:30")),
        date(2026, 3, 2),
        date(2026, 3, 2),
        now="2026-03-10 12:00",
    )
    assert round(day.night_ms / 1000) == round(90 * 60 * 60 / 52.5)
    assert round(day.worked_ms / 1000) == 4 * 3600 + round(90 * 60 * 60 / 52.5)


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
        punches(*normal_day("2026-03-02")),
        date(2026, 3, 2),
        date(2026, 3, 2),
        now="2026-03-10 12:00",
        deleted=[removed],
    )
    assert day.worked_ms == 8 * HOUR
    assert len(day.punches) == 5 and day.punches[-1].deleted_at


def test_alerta_sem_intervalo_de_almoco():
    (day,) = days_for(
        punches(("entrada", "2026-03-02 08:00"), ("saida", "2026-03-02 16:00")),
        date(2026, 3, 2),
        date(2026, 3, 2),
        now="2026-03-10 12:00",
    )
    assert day.alerts == ["Intervalo de almoço menor que 1h"]


def test_alerta_descanso_entre_jornadas_e_horas_extras():
    days = days_for(
        punches(
            ("entrada", "2026-03-02 08:00"),
            ("saida", "2026-03-02 12:00"),
            ("entrada", "2026-03-02 13:00"),
            ("saida", "2026-03-02 23:00"),
            *normal_day("2026-03-03", start="07:00"),
        ),
        date(2026, 3, 2),
        date(2026, 3, 3),
        now="2026-03-10 12:00",
    )
    assert "Mais de 2h extras no dia" in days[0].alerts
    assert days[1].alerts == ["Menos de 11h de descanso desde a jornada anterior"]


def test_dia_normal_sem_alertas():
    (day,) = days_for(punches(*normal_day("2026-03-02")), date(2026, 3, 2), date(2026, 3, 2), now="2026-03-10 12:00")
    assert day.alerts == []


def test_jornada_personalizada():
    emp = employee(daily_minutes=360, workdays="6")  # só sábado, 6h
    days = days_for([], date(2026, 3, 6), date(2026, 3, 7), now="2026-03-10 12:00", emp=emp)
    assert [d.expected_ms for d in days] == [0, 6 * HOUR]
    assert days[1].balance_ms == -6 * HOUR
    assert timedelta(milliseconds=days[1].expected_ms) == timedelta(hours=6)


def test_csv_neutraliza_formulas_e_separadores():
    from app.services.report_service import _text

    assert _text("Ana") == "Ana"
    assert _text("=HYPERLINK(\"http://x\")") == "\"'=HYPERLINK(\"\"http://x\"\")\""
    assert _text("+5511999") == "'+5511999"
    assert _text("@SUM(A1)") == "'@SUM(A1)"
    assert _text("-1") == "'-1"
    assert _text("Ana; Souza") == '"Ana; Souza"'  # não cria coluna nova
    assert _text("linha\nnova") == '"linha\nnova"'


def test_prazo_de_guarda_conta_a_partir_do_desligamento():
    from datetime import datetime, timezone
    from unittest.mock import patch

    hoje = date(2031, 6, 10)
    with patch("app.models.employee.now_local", return_value=datetime(2031, 6, 10, 12, tzinfo=timezone.utc)):
        assert not employee().retention_due  # ainda trabalha
        assert not employee(terminated_on=date(2026, 6, 11)).retention_due  # falta um dia
        assert employee(terminated_on=date(2026, 6, 10)).retention_due
        anonimizado = employee(terminated_on=date(2020, 1, 1))
        anonimizado.anonymized_at = datetime(2030, 1, 1, tzinfo=timezone.utc)
        assert not anonimizado.retention_due
    assert hoje.year - 2026 == settings.retention_years
