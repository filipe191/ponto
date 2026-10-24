"""Erros da API, sempre no formato {"error": "..."} esperado pelo frontend."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message


class NotFound(ApiError):
    def __init__(self, message: str):
        super().__init__(404, message)


class BadRequest(ApiError):
    def __init__(self, message: str):
        super().__init__(400, message)


class Conflict(ApiError):
    def __init__(self, message: str):
        super().__init__(409, message)


class Unauthorized(ApiError):
    def __init__(self, message: str = "Usuário ou senha inválidos"):
        super().__init__(401, message)


class TooManyRequests(ApiError):
    def __init__(self, message: str):
        super().__init__(429, message)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_req: Request, exc: ApiError):
        return JSONResponse({"error": exc.message}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_req: Request, exc: RequestValidationError):
        # Usa a mensagem do primeiro validador que falhou (ex.: "PIN deve ter de 4 a 8 dígitos")
        errors = exc.errors()
        message = errors[0].get("msg", "Dados inválidos") if errors else "Dados inválidos"
        return JSONResponse({"error": message.removeprefix("Value error, ")}, status_code=400)
