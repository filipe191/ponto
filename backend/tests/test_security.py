from unittest.mock import patch

from app.core.ratelimit import AttemptLimiter
from app.core.security import (
    ROLE_ADMIN,
    ROLE_KIOSK,
    _legacy_pin_hash,
    create_session,
    hash_pin,
    read_session,
    rehash_legacy_pin,
)


def test_pin_usa_chave_e_converte_hash_antigo():
    assert hash_pin("1234") != _legacy_pin_hash("1234")
    assert hash_pin("1234") == rehash_legacy_pin(_legacy_pin_hash("1234"))


def test_token_do_relogio_nao_vale_como_admin():
    token = create_session(ROLE_KIOSK, "admin", "hash", 60)
    assert read_session(token, ROLE_KIOSK, "admin", "hash")
    assert not read_session(token, ROLE_ADMIN, "admin", "hash")


def test_token_cai_quando_a_senha_muda():
    token = create_session(ROLE_ADMIN, "admin", "hash-antigo", 60)
    assert not read_session(token, ROLE_ADMIN, "admin", "hash-novo")


def test_token_expirado():
    token = create_session(ROLE_ADMIN, "admin", "hash", -1)
    assert not read_session(token, ROLE_ADMIN, "admin", "hash")


def test_token_adulterado():
    assert not read_session("bGl4bw==", ROLE_ADMIN, "admin", "hash")
    assert not read_session("não é base64", ROLE_ADMIN, "admin", "hash")


def test_limite_de_tentativas():
    limiter = AttemptLimiter(max_attempts=3, window_seconds=60)
    with patch("app.core.ratelimit.time.monotonic", return_value=1000.0):
        for _ in range(3):
            limiter.fail("1.2.3.4")
        assert limiter.blocked("1.2.3.4")
        assert not limiter.blocked("5.6.7.8")
    with patch("app.core.ratelimit.time.monotonic", return_value=1061.0):
        assert not limiter.blocked("1.2.3.4")  # a janela passou


def test_limite_zera_apos_acerto():
    limiter = AttemptLimiter(max_attempts=2, window_seconds=60)
    limiter.fail("ip")
    limiter.reset("ip")
    limiter.fail("ip")
    assert not limiter.blocked("ip")
