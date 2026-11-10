import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.i18n import parse_accept_language, set_lang
from app.core.logging import add_request_logging, configure_logging
from app.database.session import get_sessionmaker
from app.repositories import user_repository
from app.services import retention_service
from app.web import add_security_headers, mount_frontend

log = logging.getLogger("faceguard")


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        with get_sessionmaker()() as db:
            user_repository.seed_roles(db)
            retention_service.purge(db)  # no-op unless RETENTION_DAYS > 0
    except Exception:  # noqa: BLE001 - the API still starts so /api/health can report "degraded"
        log.exception("Could not seed roles at startup (is the database migrated and reachable?)")
    yield


def create_app() -> FastAPI:
    s = get_settings()
    configure_logging(s.log_level)
    if s.is_production and s.docs_enabled:
        log.warning("DOCS_ENABLED=true in production: the API documentation is publicly reachable. Set DOCS_ENABLED=false.")
    app = FastAPI(
        title="FaceGuard AI API",
        version="0.2.0",
        lifespan=lifespan,
        docs_url="/api/docs" if s.docs_enabled else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if s.docs_enabled else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept-Language"],
        allow_credentials=False,  # bearer tokens, not cookies
    )

    @app.middleware("http")
    async def _security_headers(request: Request, call_next):
        set_lang(parse_accept_language(request.headers.get("accept-language")))  # language of user-facing messages
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/docs"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    add_request_logging(app)
    register_error_handlers(app)
    app.include_router(api_router)

    frontend = s.frontend_path
    if frontend is not None:  # single-process mode (run.py / root Dockerfile); the route goes last
        add_security_headers(app)
        mount_frontend(app, frontend)
        log.info("Serving the web app from %s", frontend)
    return app


app = create_app()
