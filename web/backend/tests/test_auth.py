from app.core import twofactor
from app.core.passwords import password_problem
from app.core.security import hash_session_token, new_session_token

RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # "12345678901234567890" em base32 (RFC 6238)


def test_totp_vetor_oficial_da_rfc():
    # RFC 6238, apêndice B: T=59s -> 94287082 (8 dígitos); com 6 dígitos, 287082
    assert twofactor.code_at(RFC_SECRET, 59 // 30) == "287082"
    assert twofactor.code_at(RFC_SECRET, 1111111109 // 30) == "081804"


def test_totp_aceita_30s_de_diferenca_e_nao_reaproveita():
    now = 1_700_000_000
    step = int(now // 30)
    code = twofactor.code_at(RFC_SECRET, step)
    assert twofactor.verify(RFC_SECRET, code, None, now) == step
    assert twofactor.verify(RFC_SECRET, code, None, now + 30) == step  # relógio 30 s adiantado
    assert twofactor.verify(RFC_SECRET, code, None, now + 90) is None  # longe demais
    assert twofactor.verify(RFC_SECRET, code, step, now) is None  # já usado
    assert twofactor.verify(RFC_SECRET, "12 34 5", None, now) is None
    assert twofactor.verify(RFC_SECRET, code[:3] + " " + code[3:], None, now) == step  # espaço no meio


def test_segredo_cifrado_no_banco():
    secret = twofactor.new_secret()
    token = twofactor.encrypt_secret(secret)
    assert secret not in token
    assert twofactor.decrypt_secret(token) == secret
    assert twofactor.decrypt_secret("lixo") is None


def test_qr_e_uri_do_autenticador():
    uri = twofactor.provisioning_uri("ABC", "ana souza")
    assert uri.startswith("otpauth://totp/Ponto%3Aana%20souza?secret=ABC&issuer=Ponto")
    assert twofactor.qr_data_uri(uri).startswith("data:image/svg+xml")


def test_codigos_de_recuperacao():
    codes = twofactor.new_recovery_codes()
    assert len(codes) == 10 and len(set(codes)) == 10
    assert all(len(c) == 9 and c[4] == "-" for c in codes)
    # digitar sem hífen, com espaço ou em maiúsculas vale o mesmo código
    c = codes[0]
    assert twofactor.hash_recovery_code(c) == twofactor.hash_recovery_code(c.upper().replace("-", " "))


def test_politica_de_senha():
    assert password_problem("curta1!") == "A senha deve ter pelo menos 12 caracteres"
    assert "comum" in password_problem("123456789012")
    assert "comum" in password_problem("Senha1234567")
    assert "só números" in password_problem("9081726354098")
    assert "variedade" in password_problem("aaaaaaaabbbb")
    assert "usuário" in password_problem("filipe-cavalo-azul", "filipe")
    assert password_problem("cavalo azul correndo 7") is None


def test_token_de_sessao_opaco():
    a, b = new_session_token(), new_session_token()
    assert a != b and len(a) >= 40
    assert hash_session_token(a) != a and len(hash_session_token(a)) == 64
