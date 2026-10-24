"""Feriados nacionais (Lei 662/49, Lei 6.802/80 e Lei 14.759/23). Carnaval e Corpus Christi são
ponto facultativo e, quando adotados, devem ser cadastrados pelo admin, como os municipais."""

from datetime import date, timedelta
from functools import cache

FIXED = {
    (1, 1): "Confraternização Universal",
    (4, 21): "Tiradentes",
    (5, 1): "Dia do Trabalho",
    (9, 7): "Independência do Brasil",
    (10, 12): "Nossa Senhora Aparecida",
    (11, 2): "Finados",
    (11, 15): "Proclamação da República",
    (11, 20): "Dia da Consciência Negra",
    (12, 25): "Natal",
}


def easter(year: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher, calendário gregoriano)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


@cache
def national_holidays(year: int) -> dict[date, str]:
    holidays = {date(year, m, d): name for (m, d), name in FIXED.items()}
    holidays[easter(year) - timedelta(days=2)] = "Sexta-feira Santa"
    if year < 2024:  # Consciência Negra virou feriado nacional em 2024
        holidays.pop(date(year, 11, 20))
    return holidays
