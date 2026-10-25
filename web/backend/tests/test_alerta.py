"""Alerta por e-mail dos scripts (backup com falha, sistema fora do ar)."""

import io
from unittest.mock import patch

from app import alerta
from app.core.config import settings


def run(subject: str, body: str = "") -> int:
    with patch("sys.stdin", io.StringIO(body)):
        return alerta.main(["alerta", subject])


def test_sem_smtp_nao_envia_e_nao_falha(capsys):
    with patch.object(settings, "smtp_host", ""), patch.object(settings, "alerta_email", "ti@empresa.com"):
        assert run("Ponto: o backup falhou") == 0
    assert "não enviado" in capsys.readouterr().out


def test_envia_para_cada_endereco():
    with (
        patch.object(settings, "smtp_host", "smtp.teste"),
        patch.object(settings, "alerta_email", "ti@empresa.com, dono@empresa.com"),
        patch("app.alerta.deliver", return_value=True) as deliver,
    ):
        assert run("Ponto: fora do ar", "detalhes") == 0
    deliver.assert_called_once_with(["ti@empresa.com", "dono@empresa.com"], "Ponto: fora do ar", "detalhes")


def test_falha_do_smtp_devolve_erro():
    with (
        patch.object(settings, "smtp_host", "smtp.teste"),
        patch.object(settings, "alerta_email", "ti@empresa.com"),
        patch("app.alerta.deliver", return_value=False),
    ):
        assert run("Ponto: fora do ar") == 1
