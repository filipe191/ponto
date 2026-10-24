from datetime import timedelta

from app.core.security import hash_device_key, new_device_key
from app.models import Punch, PunchSource
from app.schemas.mobile import BatidaRequest, LoteResponse, ResumoMes
from app.services.mobile_service import _fmt, to_batida
from tests.helpers import at


def punch(**extra) -> Punch:
    values = dict(id=7, employee_id=1, ts=at("2026-03-02 08:00"), type="entrada", manual=False, note=None)
    values.update(extra)
    return Punch(**values)


def test_id_publico_usa_o_uuid_do_celular_ou_web_n():
    assert punch(client_id="3f2b1c4a-8d5e-4f6a-9b7c-1d2e3f4a5b6c").public_id == "3f2b1c4a-8d5e-4f6a-9b7c-1d2e3f4a5b6c"
    assert punch().public_id == "web-7"


def test_relogio_suspeito_quando_o_celular_esta_adiantado():
    received = at("2026-03-02 08:00")
    assert not punch(received_at=received).clock_suspect
    assert punch(ts=received + timedelta(minutes=5), received_at=received).clock_suspect
    # batida antiga enviada depois (sem conexão) é normal
    assert not punch(ts=received - timedelta(hours=5), received_at=received).clock_suspect


def test_batida_no_formato_do_app():
    b = to_batida(punch(source=PunchSource.APP, client_id="abc", device="iphone-ana"))
    data = b.model_dump(by_alias=True, mode="json")
    assert data["id"] == "abc"
    assert data["tipo"] == "ENTRADA"
    assert data["ocorridoEm"] == "2026-03-02T08:00:00-03:00"
    assert data["origem"] == "iphone-ana"
    assert set(data) == {"id", "tipo", "ocorridoEm", "origem", "observacao", "manual", "ajustadoEm", "relogioSuspeito"}


def test_entrada_do_app_em_camel_case():
    b = BatidaRequest.model_validate(
        {"id": "x", "tipo": "SAIDA", "ocorridoEm": "2026-09-10T17:31:00-03:00", "uptimeMs": 5, "manual": True}
    )
    assert b.uptime_ms == 5 and b.manual and b.ocorrido_em.hour == 17


def test_campos_do_resumo_e_do_lote():
    assert set(ResumoMes.model_json_schema(by_alias=True)["properties"]) == {
        "inicio", "fim", "trabalhadoMinutos", "esperadoMinutos", "saldoMinutos",
        "trabalhadoFormatado", "saldoFormatado", "dias",
    }
    assert set(LoteResponse().model_dump()) == {"aceitas", "duplicadas", "rejeitadas"}


def test_formatacao_de_horas():
    assert _fmt(510) == "8h30"
    assert _fmt(-45, signed=True) == "-0h45"
    assert _fmt(65, signed=True) == "+1h05"
    assert _fmt(0, signed=True) == "0h00"


def test_chave_do_celular():
    key = new_device_key()
    assert key.startswith("ponto_") and len(key) > 40
    assert hash_device_key(key) == hash_device_key(key) != hash_device_key(new_device_key())
