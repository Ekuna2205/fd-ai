import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.i18n import tr

log = logging.getLogger("faceguard.errors")


class AppError(Exception):
    """Domain error mapped to an HTTP response. `detail` is safe to show to users."""

    status_code = 400

    def __init__(self, detail: str, status_code: int | None = None, headers: dict[str, str] | None = None):
        super().__init__(detail)
        self.detail = detail
        self.headers = headers
        if status_code:
            self.status_code = status_code


class AuthenticationError(AppError):
    status_code = 401

    def __init__(self, detail: str = "Not authenticated."):
        super().__init__(detail, headers={"WWW-Authenticate": "Bearer"})


class PermissionDenied(AppError):
    status_code = 403


class NotFound(AppError):
    status_code = 404


class Conflict(AppError):
    status_code = 409


def _field_name(loc: tuple) -> str:
    parts = [str(p) for p in loc if p not in ("body", "query", "path")]
    return ".".join(parts)


def register_error_handlers(app: FastAPI) -> None:
    """All errors share the shape {"detail": str, "errors"?: [{field, message}]}."""

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse({"detail": tr(exc.detail)}, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        errors = [
            {"field": _field_name(e["loc"]), "message": tr(str(e["msg"]).removeprefix("Value error, "))}
            for e in exc.errors()
        ]
        return JSONResponse({"detail": tr("Some fields are invalid."), "errors": errors}, status_code=422)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse({"detail": tr("Internal server error.")}, status_code=500)
