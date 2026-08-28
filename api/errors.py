# api/errors.py — the frozen error envelope
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


class HelmError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, detail: dict | None = None):
        self.code, self.message, self.status, self.detail = code, message, status, detail or {}


def _envelope(code: str, message: str, detail: dict, status: int) -> JSONResponse:
    return JSONResponse(status_code=status,
                        content={"error": {"code": code, "message": message, "detail": detail}})


def register(app):
    @app.exception_handler(HelmError)
    async def _helm(_: Request, exc: HelmError):
        return _envelope(exc.code, exc.message, exc.detail, exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        return _envelope("VALIDATION", "Request body failed validation",
                         {"errors": exc.errors()}, 422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 409: "CONFLICT", 400: "BAD_REQUEST"}.get(exc.status_code, "HTTP_ERROR")
        return _envelope(code, str(exc.detail), {}, exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        return _envelope("INTERNAL", "Unexpected server error", {"type": type(exc).__name__}, 500)
