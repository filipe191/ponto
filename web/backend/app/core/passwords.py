"""Política de senha dos administradores."""

import re

MIN_LENGTH = 12

# Senhas longas que aparecem em listas de vazamentos (as curtas já caem pelo tamanho mínimo)
COMMON = {
    "123456789012", "1234567890123", "12345678910", "123456789123", "1234567891011",
    "qwertyuiopas", "qwertyuiop123", "qwerty123456", "asdfghjklçç", "abcdefghijkl",
    "abc123456789", "password1234", "password123!", "passwordpassword", "senha1234567",
    "senhasenhasenha", "minhasenha123", "senha12345678", "mudar123456", "trocar123456",
    "administrador", "administrador1", "admin1234567", "adminadmin123", "iloveyou1234",
    "brasil123456", "flamengo1234", "corinthians1", "corinthians123", "palmeiras123",
    "saopaulo1234", "gremio123456", "vasco1234567", "botafogo1234", "cruzeiro1234",
    "jesuscristo1", "deusefiel123", "princesa1234", "batatinha123", "chocolate123",
    "bemvindo1234", "welcome12345", "letmein12345", "football1234", "monkey123456",
    "dragon123456", "sunshine1234", "superman1234", "ponto1234567", "pontoponto12",
}


def password_problem(password: str, username: str = "") -> str | None:
    """Explica por que a senha não serve, ou None se ela for aceitável."""
    if len(password) < MIN_LENGTH:
        return f"A senha deve ter pelo menos {MIN_LENGTH} caracteres"
    lowered = password.lower()
    if lowered in COMMON or re.sub(r"[^a-zç0-9]", "", lowered) in COMMON:
        return "Essa senha é muito comum. Escolha outra"
    if len(set(lowered)) < 5:
        return "Use uma senha com mais variedade de caracteres"
    if lowered.isdigit():
        return "A senha não pode ter só números"
    if username and len(username) >= 3 and username.lower() in lowered:
        return "A senha não pode conter o nome de usuário"
    if lowered in "01234567890123456789" or lowered in "abcdefghijklmnopqrstuvwxyz":
        return "A senha não pode ser uma sequência"
    return None
