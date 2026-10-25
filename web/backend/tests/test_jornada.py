"""Jornada por dia da semana e escalas em ciclo (12x36 etc.): previsto de cada dia e descrição."""

from datetime import date

from app.models import Employee, EmployeeSchedule
from app.models.employee import SCHEDULE_CYCLE
from tests.helpers import at
from tests.test_report import HOUR, days_for


def _emp(*schedules: EmployeeSchedule) -> Employee:
    emp = Employee(id=1, name="Ana", hired_on=date(2026, 1, 1), created_at=at("2026-01-01 00:00"))
    emp.schedules.extend(schedules)
    return emp


def week(*minutes: int, since=date(2026, 1, 1)) -> EmployeeSchedule:
    return EmployeeSchedule(valid_from=since, kind="semana", day_minutes=",".join(map(str, minutes)))


def cycle(*minutes: int, start: date, since=date(2026, 1, 1)) -> EmployeeSchedule:
    return EmployeeSchedule(valid_from=since, kind=SCHEDULE_CYCLE, day_minutes=",".join(map(str, minutes)), cycle_start=start)


def test_sabado_meio_periodo():
    emp = _emp(week(480, 480, 480, 480, 480, 240, 0))
    # 02/03/2026 é segunda; até domingo 08/03
    days = days_for([], date(2026, 3, 2), date(2026, 3, 8), now="2026-03-10 12:00", emp=emp)
    assert [d.expected_ms // HOUR for d in days] == [8, 8, 8, 8, 8, 4, 0]
    assert days[5].status == "falta" and days[6].status == "folga"


def test_escala_12x36_alterna_os_dias_a_partir_do_inicio():
    emp = _emp(cycle(720, 0, start=date(2026, 3, 3)))  # trabalha 03/03 (terça), folga 04, trabalha 05...
    days = days_for([], date(2026, 3, 2), date(2026, 3, 7), now="2026-03-10 12:00", emp=emp)
    assert [d.expected_ms // HOUR for d in days] == [0, 12, 0, 12, 0, 12]


def test_escala_vale_por_vigencia():
    emp = _emp(week(480, 480, 480, 480, 480, 0, 0), cycle(720, 0, start=date(2026, 3, 5), since=date(2026, 3, 5)))
    days = days_for([], date(2026, 3, 2), date(2026, 3, 8), now="2026-03-10 12:00", emp=emp)
    assert [d.expected_ms // HOUR for d in days] == [8, 8, 8, 12, 0, 12, 0]


def test_descricoes():
    assert week(480, 480, 480, 480, 480, 0, 0).label == "8h00 · seg a sex"
    assert week(480, 480, 480, 480, 480, 240, 0).label == "seg a sex 8h00 · sáb 4h00"
    assert week(0, 0, 0, 0, 0, 360, 0).label == "6h00 · sáb"
    assert week(480, 0, 480, 0, 480, 0, 0).label == "8h00 · seg, qua, sex"
    assert week(0, 0, 0, 0, 0, 0, 0).label == "sem dias de trabalho"
    assert cycle(720, 0, start=date(2026, 3, 3)).label == "escala 12x36 (12h00, folga)"
    assert cycle(480, 480, 0, start=date(2026, 3, 3)).label == "escala de 3 dias (8h00, 8h00, folga)"
    assert week(480, 480, 480, 480, 480, 240, 0).weekly_minutes == 44 * 60


def test_formato_antigo_continua():
    s = EmployeeSchedule.weekly(date(2026, 1, 1), 360, "6")
    assert s.minutes == [0, 0, 0, 0, 0, 360, 0] and s.workdays == "6" and s.daily_minutes == 360
