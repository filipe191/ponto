"""PIN dos funcionários, hash de senha do login e sessão em cookie assinado."""

import base64
import hashlib
import hmac
import secrets
import time
from collections.abc import Callable

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


def new_device_key() -> str:
    """Chave de acesso do app de celular (aleatória, 256 bits)."""
    return "ponto_" + secrets.token_urlsafe(32)


def hash_device_key(key: str) -> str:
    # A chave é aleatória e longa: SHA-256 basta (não precisa de hash lento como as senhas)
    return hashlib.sha256(key.encode()).hexdigest()


def receipt_code(punch_id: int, employee_id: int, ts) -> str:
    """Código de 10 caracteres do comprovante da batida (usa PIN_KEY, que é fixa)."""
    payload = f"comprovante|{punch_id}|{employee_id}|{int(ts.timestamp())}"
    digest = hmac.new(settings.pin_key.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.b32encode(digest).decode()[:10]


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


def _sign(payload: str, key_material: str) -> str:
    # A chave inclui o hash da senha do admin (ou o segredo dos relógios):
    # trocar a senha derruba as outras sessões desse admin
    key = f"{settings.secret_key}:{key_material}".encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def create_session(role: str, subject: str, key_material: str, seconds: int) -> str:
    """Token no formato base64("papel|sujeito|expira_em|assinatura")."""
    expires = int(time.time()) + seconds
    payload = f"{role}|{subject}|{expires}"
    return base64.urlsafe_b64encode(f"{payload}|{_sign(payload, key_material)}".encode()).decode()


def read_session(token: str | None, role: str, key_for: Callable[[str], str | None]) -> str | None:
    """Devolve o sujeito (ex.: usuário do admin) se o token for válido, do papel pedido e não expirou.

    `key_for(sujeito)` dá a chave usada na assinatura, ou None se o sujeito não existe mais.
    """
    if not token:
        return None
    try:
        head, expires, signature = base64.urlsafe_b64decode(token.encode()).decode().rsplit("|", 2)
    except (ValueError, UnicodeDecodeError):
        return None
    token_role, _, subject = head.partition("|")
    if token_role != role:
        return None
    key_material = key_for(subject)
    if key_material is None or not hmac.compare_digest(signature, _sign(f"{head}|{expires}", key_material)):
        return None
    if not expires.isdigit() or int(expires) < time.time():
        return None
    return subject
