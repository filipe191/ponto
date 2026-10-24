"""PIN dos funcionários, hash de senha do login e sessão em cookie assinado."""

import base64
import hashlib
import hmac
import secrets
import time

from app.core.config import settings

SESSION_COOKIE = "ponto_session"  # login do administrador
KIOSK_COOKIE = "ponto_kiosk"  # aparelho liberado como relógio de ponto

ROLE_ADMIN = "admin"
ROLE_KIOSK = "kiosk"


def _legacy_pin_hash(pin: str) -> str:
    """Hash antigo (sem chave). Ainda é a base do atual, para os PINs antigos poderem ser convertidos."""
    return hashlib.sha256(f"ponto:{pin}".encode()).hexdigest()


def rehash_legacy_pin(legacy_hash: str) -> str:
    """HMAC com PIN_KEY: sem a chave, uma cópia do banco não permite descobrir os PINs."""
    return hmac.new(settings.pin_key.encode(), legacy_hash.encode(), hashlib.sha256).hexdigest()


def hash_pin(pin: str) -> str:
    # Determinístico (sem salt) porque o funcionário é encontrado pelo hash do PIN
    return rehash_legacy_pin(_legacy_pin_hash(pin))


def _scrypt(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)


def hash_password(password: str) -> str:
    """Formato "scrypt$salt_hex$hash_hex"."""
    salt = secrets.token_bytes(16)
    return f"scrypt${salt.hex()}${_scrypt(password, salt).hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, salt, expected = stored.split("$")
        return hmac.compare_digest(_scrypt(password, bytes.fromhex(salt)).hex(), expected)
    except ValueError:
        return False


def _sign(payload: str, password_hash: str) -> str:
    # Inclui o hash da senha na chave: trocar a senha derruba as outras sessões abertas
    key = f"{settings.secret_key}:{password_hash}".encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def create_session(role: str, user: str, password_hash: str, seconds: int) -> str:
    """Token no formato base64("papel|usuario|expira_em|assinatura")."""
    expires = int(time.time()) + seconds
    payload = f"{role}|{user}|{expires}"
    return base64.urlsafe_b64encode(f"{payload}|{_sign(payload, password_hash)}".encode()).decode()


def read_session(token: str | None, role: str, user: str, password_hash: str) -> bool:
    """Diz se o token é válido, não expirou, tem o papel pedido e pertence ao login atual."""
    if not token:
        return False
    try:
        head, expires, signature = base64.urlsafe_b64decode(token.encode()).decode().rsplit("|", 2)
    except (ValueError, UnicodeDecodeError):
        return False
    if not hmac.compare_digest(signature, _sign(f"{head}|{expires}", password_hash)):
        return False
    if not expires.isdigit() or int(expires) < time.time():
        return False
    token_role, _, token_user = head.partition("|")
    return token_role == role and token_user == user
