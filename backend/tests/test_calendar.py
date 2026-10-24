from datetime import date, timedelta

from app.utils.dates import night_time
from app.utils.holidays import easter, national_holidays
from tests.helpers import at


def test_pascoa():
    assert easter(2024) == date(2024, 3, 31)
    assert easter(2025) == date(2025, 4, 20)
    assert easter(2026) == date(2026, 4, 5)


def test_feriados_nacionais():
    h = national_holidays(2026)
    assert h[date(2026, 4, 3)] == "Sexta-feira Santa"
    assert h[date(2026, 11, 20)] == "Dia da Consciência Negra"
    assert len(h) == 10
    assert date(2023, 11, 20) not in national_holidays(2023)  # nacional só a partir de 2024


def test_horario_noturno():
    assert night_time(at("2026-03-02 08:00"), at("2026-03-02 17:00")) == timedelta(0)
    assert night_time(at("2026-03-02 21:00"), at("2026-03-03 06:00")) == timedelta(hours=7)
    assert night_time(at("2026-03-03 03:00"), at("2026-03-03 08:00")) == timedelta(hours=2)
    # duas noites seguidas
    assert night_time(at("2026-03-02 23:00"), at("2026-03-03 23:00")) == timedelta(hours=7)
