"""Limite de tentativas erradas guardado no banco: sobrevive a um reinício do backend."""

from datetime import timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core import ratelimit
from app.core.ratelimit import AttemptLimiter, EscalatingLimiter
from app.main import app
from tests.integration.conftest import ORIGIN


def _clock(start):
    now = [start]
    return now, patch("app.core.ratelimit._now", side_effect=lambda: now[0])


def test_limite_de_tentativas(legacy):
    limiter = AttemptLimiter("teste-janela", max_attempts=3, window_seconds=60)
    now, clock = _clock(ratelimit._now())
    with clock:
        for _ in range(3):
            limiter.fail("1.2.3.4")
        assert limiter.blocked("1.2.3.4")
        assert not limiter.blocked("5.6.7.8")
        now[0] += timedelta(seconds=61)
        assert not limiter.blocked("1.2.3.4")  # a janela passou


def test_limite_zera_apos_acerto(legacy):
    limiter = AttemptLimiter("teste-acerto", max_attempts=2, window_seconds=60)
    limiter.fail("ip")
    limiter.reset("ip")
    limiter.fail("ip")
    assert not limiter.blocked("ip")


def test_bloqueio_dobra_a_cada_rodada_de_erros(legacy):
    limiter = EscalatingLimiter("teste-dobra", 3, 60, base_block=300, max_block=1000, forget_after=3600)
    now, clock = _clock(ratelimit._now())
    with clock:
        assert [limiter.fail("ip") for _ in range(3)] == [0, 0, 300]
        assert limiter.blocked_for("ip") == 300
        assert limiter.blocked_for("outro") == 0
        now[0] += timedelta(seconds=301)
        assert limiter.blocked_for("ip") == 0
        assert [limiter.fail("ip") for _ in range(3)] == [0, 0, 600]  # segunda rodada: o dobro
        now[0] += timedelta(seconds=601)
        assert [limiter.fail("ip") for _ in range(3)] == [0, 0, 1000]  # nunca passa do máximo
        now[0] += timedelta(seconds=1000 + 3601)  # um tempo sem bloqueios: volta ao início
        assert [limiter.fail("ip") for _ in range(3)] == [0, 0, 300]


def test_bloqueio_continua_depois_de_reiniciar(legacy):
    before = EscalatingLimiter("teste-reinicio", 2, 60, base_block=300, max_block=1000, forget_after=3600)
    assert [before.fail("ip") for _ in range(2)] == [0, 300]
    # Um limitador novo (como depois de reiniciar o backend) enxerga o bloqueio e a contagem
    after = EscalatingLimiter("teste-reinicio", 2, 60, base_block=300, max_block=1000, forget_after=3600)
    assert 295 < after.blocked_for("ip") <= 300
    with patch("app.core.ratelimit._now", return_value=ratelimit._now() + timedelta(seconds=301)):
        assert [after.fail("ip") for _ in range(2)] == [0, 600]


def test_login_bloqueia_depois_de_cinco_senhas_erradas(legacy):
    client = TestClient(app, client=("10.9.9.9", 50000))
    for _ in range(5):
        response = client.post("/api/auth/login", json={"username": "ninguem", "password": "errada"}, headers=ORIGIN)
        assert response.status_code == 401
    response = client.post("/api/auth/login", json={"username": "ninguem", "password": "errada"}, headers=ORIGIN)
    assert response.status_code == 429
    AttemptLimiter("login", 5, 300).reset("10.9.9.9")
