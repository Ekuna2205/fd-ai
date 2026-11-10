import logging
import time

from fastapi import FastAPI, Request


def configure_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def add_request_logging(app: FastAPI) -> None:
    log = logging.getLogger("faceguard.access")

    @app.middleware("http")
    async def _log(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - start) * 1000
        # Method, path and status only: never bodies, query strings or tokens.
        log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, ms)
        return response
