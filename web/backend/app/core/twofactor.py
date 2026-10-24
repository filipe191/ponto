"""Verificação em duas etapas dos administradores: código de 6 dígitos de um app autenticador
(TOTP, RFC 6238: Google Authenticator, Microsoft Authenticator, Bitwarden...) e códigos de recuperação."""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

import segno
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

STEP_SECONDS = 30
DIGITS = 6
ISSUER = "Ponto"
RECOVERY_CODES = 10


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def code_at(secret: str, step: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 10**DIGITS:0{DIGITS}d}"


def verify(secret: str, code: str, last_step: int | None, now: float | None = None) -> int | None:
    """Devolve o passo de tempo do código se ele for válido (aceita 30 s de diferença de relógio).

    Um código já usado (passo <= last_step) é recusado: quem viu o código não consegue reaproveitá-lo.
    """
    code = "".join(c for c in code if c.isdigit())
    if len(code) != DIGITS:
        return None
    current = int((time.time() if now is None else now) // STEP_SECONDS)
    for step in (current - 1, current, current + 1):
        if (last_step is None or step > last_step) and hmac.compare_digest(code_at(secret, step), code):
            return step
    return None


def provisioning_uri(secret: str, username: str) -> str:
    label = quote(f"{ISSUER}:{username}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={ISSUER}&digits={DIGITS}&period={STEP_SECONDS}"


def qr_data_uri(uri: str) -> str:
    return segno.make(uri, error="m").svg_data_uri(scale=5, border=2)


# ---------- Segredo cifrado no banco ----------
# Com o banco vazado sozinho (ex.: um backup), os segredos não servem para gerar códigos.


def _fernet() -> Fernet:
    key = hashlib.sha256(f"totp|{settings.pin_key}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None


# ---------- Códigos de recuperação (uso único, para quando o celular for perdido) ----------


def new_recovery_codes() -> list[str]:
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"  # sem 0/o/1/l/i, que se confundem
    return ["-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(2)) for _ in range(RECOVERY_CODES)]


def hash_recovery_code(code: str) -> str:
    normalized = code.strip().lower().replace(" ", "").replace("-", "")
    return hashlib.sha256(f"recuperacao|{normalized}".encode()).hexdigest()
