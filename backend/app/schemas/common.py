import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel


class OkResponse(BaseModel):
    ok: bool = True


def _check_pin(value: str) -> str:
    if not re.fullmatch(r"\d{4,8}", value or ""):
        raise ValueError("PIN deve ter de 4 a 8 dígitos")
    return value


Pin = Annotated[str, AfterValidator(_check_pin)]
