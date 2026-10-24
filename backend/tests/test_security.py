from unittest.mock import patch

from app.core.ratelimit import AttemptLimiter
from app.core.security import (
    ROLE_ADMIN,
    ROLE_KIOSK,
    _legacy_pin_hash,
    create_session,
    hash_pin,
    read_session,
    receipt_code,
    rehash_legacy_pin,
)
from tests.helpers import at

KEYS = {"ana": "hash-da-ana", "bia": "hash-da-bia"}


def key_for(user):
    return KEYS.get(user)


def test_pin_usa_chave_e_converte_hash_antigo():
    assert hash_pin("1234") != _legacy_pin_hash("1234")
    assert hash_pin("1234") == rehash_legacy_pin(_legacy_pin_hash("1234"))


def test_sessao_identifica_o_admin():
    token = create_session(ROLE_ADMIN, "ana", KEYS["ana"], 60)
    assert read_session(token, ROLE_ADMIN, key_for) == "ana"


def test_token_do_relogio_nao_vale_como_admin():
    token = create_session(ROLE_KIOSK, "ana", KEYS["ana"], 60)
    assert read_session(token, ROLE_ADMIN, key_for) is None


def test_token_cai_quando_a_senha_muda():
    token = create_session(ROLE_ADMIN, "ana", "hash-antigo", 60)
    assert read_session(token, ROLE_ADMIN, key_for) is None


def test_token_de_admin_excluido():
    token = create_session(ROLE_ADMIN, "carla", "hash", 60)
    assert read_session(token, ROLE_ADMIN, key_for) is None


def test_nao_da_para_trocar_o_usuario_do_token():
    import base64

    token = create_session(ROLE_ADMIN, "ana", KEYS["ana"], 60)
    forged = base64.urlsafe_b64decode(token).decode().replace("|ana|", "|bia|")
    assert read_session(base64.urlsafe_b64encode(forged.encode()).decode(), ROLE_ADMIN, key_for) is None


def test_token_expirado():
    token = create_session(ROLE_ADMIN, "ana", KEYS["ana"], -1)
    assert read_session(token, ROLE_ADMIN, key_for) is None


def test_token_adulterado():
    assert read_session("bGl4bw==", ROLE_ADMIN, key_for) is None
    assert read_session("não é base64", ROLE_ADMIN, key_for) is None


def test_comprovante_depende_da_batida():
    code = receipt_code(1, 1, at("2026-03-02 08:00"))
    assert len(code) == 10 and code == receipt_code(1, 1, at("2026-03-02 08:00"))
    assert code != receipt_code(1, 1, at("2026-03-02 08:01"))
    assert code != receipt_code(2, 1, at("2026-03-02 08:00"))


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
