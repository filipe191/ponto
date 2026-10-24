import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel


class OkResponse(BaseModel):
    ok: bool = True


def _check_pin(value: str) -> str:
    if not re.fullmatch(r"\d{4,8}", value or ""):
        raise ValueError("PIN deve ter de 4 a 8 dígitos")
    return value


def _check_new_pin(value: str) -> str:
    if not re.fullmatch(r"\d{6,8}", value or ""):
        raise ValueError("PIN deve ter de 6 a 8 dígitos")
    return value


# Para bater o ponto: os PINs antigos de 4 e 5 dígitos ainda valem
Pin = Annotated[str, AfterValidator(_check_pin)]
# Para cadastrar ou trocar: no mínimo 6 dígitos
NewPin = Annotated[str, AfterValidator(_check_new_pin)]
