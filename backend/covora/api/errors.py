"""One error shape for every API failure: {"error": {"code", "message", "details"}}."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from covora.config import Settings
from covora.gateway.gateway import GatewayError
from covora.observability.redaction import redact

logger = logging.getLogger("covora.api")

MODEL_UNAVAILABLE = "The AI models are unavailable right now. Please try again."


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}


def error_response(status: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "details": details or {}}})


def install_error_handlers(app: FastAPI, settings: Settings) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(e.get("loc", [])), "msg": e.get("msg", "")} for e in exc.errors()]
        return error_response(422, "validation_error", "Some fields are invalid.", {"errors": errors})

    @app.exception_handler(GatewayError)
    async def _gateway(request: Request, exc: GatewayError) -> JSONResponse:
        logger.warning("model gateway failure: %s", redact(str(exc), settings.secret_values()))
        return error_response(502, "model_unavailable", MODEL_UNAVAILABLE)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "http_error"
        return error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled error: %s", redact(f"{type(exc).__name__}: {exc}", settings.secret_values()))
        return error_response(500, "internal_error", "Something went wrong.")
