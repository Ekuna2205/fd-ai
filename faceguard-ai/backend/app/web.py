"""Single-process mode: serve the built React app from the API process (no Nginx needed).

Used by `python run.py` (local, SQLite) and by the root Dockerfile (Render / Railway / any VPS). The Docker Compose setup
does not use it: there the gateway serves the frontend and the backend image contains no frontend build.
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

# Same policy as infrastructure/nginx/snippets/security-headers.conf, so both deployment modes behave alike.
SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
        "media-src 'self' blob:; font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; "
        "form-action 'self'; frame-ancestors 'none'"
    ),
}


def add_security_headers(app: FastAPI) -> None:
    @app.middleware("http")
    async def _headers(request: Request, call_next):
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        if request.headers.get("x-forwarded-proto") == "https" or request.url.scheme == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response


def mount_frontend(app: FastAPI, root: Path) -> None:
    root = root.resolve()
    index = root / "index.html"

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa(path: str):
        # Unknown API paths stay JSON 404s; they must never turn into the HTML page.
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        if path:
            candidate = (root / path).resolve()
            if candidate.is_relative_to(root) and candidate.is_file():
                # Vite fingerprints everything under assets/, so it can be cached forever.
                cache = "public, max-age=31536000, immutable" if path.startswith("assets/") else "public, max-age=3600"
                return FileResponse(candidate, headers={"Cache-Control": cache})
            if path.startswith("assets/"):
                raise HTTPException(status_code=404, detail="Not found")
        # Client-side routes (/login, /history/123, ...) all load the app shell. Never cache it.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
