"""FaceGuard AI: one command, no Docker, no PostgreSQL.

    python run.py                 # Windows: py run.py
    python run.py --port 9000     # other port
    python run.py --lan           # reachable from other devices on your network (camera then needs HTTPS)

First run: creates .venv, installs the backend packages, downloads the landmark model (54 MB, checksum-verified),
creates a SQLite database in backend/data/ and a random JWT secret. Later runs start in a few seconds.
Data lives in backend/data/ (database + datasets). Delete that folder to start over.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist"
DATA = BACKEND / "data"
VENV = ROOT / ".venv"
REQS = BACKEND / "requirements.txt"


def say(msg: str) -> None:
    print(f"[faceguard] {msg}", flush=True)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def in_venv() -> bool:
    try:
        return Path(sys.prefix).resolve() == VENV.resolve()
    except OSError:
        return False


def ensure_venv_and_reexec() -> None:
    """Create .venv, install requirements when they changed, then restart this script inside it."""
    if sys.version_info < (3, 11):
        sys.exit("Python 3.11 or newer is required. Download it from https://www.python.org/downloads/")
    if not venv_python().exists():
        say("Creating virtual environment in .venv ...")
        venv.EnvBuilder(with_pip=True).create(VENV)
    stamp = VENV / ".requirements.sha256"
    digest = hashlib.sha256(REQS.read_bytes()).hexdigest()
    if not stamp.exists() or stamp.read_text().strip() != digest:
        say("Installing backend packages (first run takes a few minutes) ...")
        py = str(venv_python())
        subprocess.run([py, "-m", "pip", "install", "--disable-pip-version-check", "-q", "--upgrade", "pip"], check=True)
        subprocess.run([py, "-m", "pip", "install", "--disable-pip-version-check", "-r", str(REQS)], check=True)
        stamp.write_text(digest)
    if not in_venv():
        raise SystemExit(subprocess.call([str(venv_python()), str(Path(__file__).resolve()), *sys.argv[1:]]))


def ensure_frontend(rebuild: bool) -> None:
    if (DIST / "index.html").is_file() and not rebuild:
        return
    npm = shutil.which("npm")
    if not npm:
        sys.exit("frontend/dist is missing and Node.js is not installed. Install Node.js 20+ from https://nodejs.org "
                 "and run this again (it builds the web app once).")
    say("Building the web app (npm ci + npm run build) ...")
    subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=FRONTEND, check=True)
    subprocess.run([npm, "run", "build"], cwd=FRONTEND, check=True)


def jwt_secret() -> str:
    path = DATA / ".jwt_secret"
    if not path.exists():
        path.write_text(secrets.token_hex(32))
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return path.read_text().strip()


def wait_and_open(url: str, open_browser: bool) -> None:
    for _ in range(120):
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=2) as r:
                if r.status == 200:
                    break
        except OSError:
            time.sleep(0.5)
    else:
        return
    say(f"Ready: {url}   (Ctrl+C stops the server)")
    if open_browser:
        webbrowser.open(url)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run FaceGuard AI as a single local web app.")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    ap.add_argument("--lan", action="store_true", help="listen on all network interfaces, not just this computer")
    ap.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    ap.add_argument("--build-frontend", action="store_true", help="rebuild frontend/dist (needs Node.js)")
    args = ap.parse_args()

    ensure_venv_and_reexec()
    ensure_frontend(args.build_frontend)
    DATA.mkdir(parents=True, exist_ok=True)

    url = f"http://localhost:{args.port}"
    env = os.environ.copy()
    env.update({
        "DATABASE_URL": env.get("DATABASE_URL") or f"sqlite:///{(DATA / 'faceguard.db').as_posix()}",
        "JWT_SECRET": env.get("JWT_SECRET") or jwt_secret(),
        "DATA_DIR": str(DATA),
        "FRONTEND_DIR": str(DIST),
        "ENVIRONMENT": "development",
        "DOCS_ENABLED": "false",
        "APP_BASE_URL": env.get("APP_BASE_URL") or url,
        "CORS_ORIGINS": url,
    })

    say("Checking the landmark model ...")
    if subprocess.call([sys.executable, "scripts/fetch_models.py"], cwd=BACKEND, env=env) != 0:
        return 1
    say("Applying database migrations ...")
    if subprocess.call([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env) != 0:
        return 1

    threading.Thread(target=wait_and_open, args=(url, not args.no_browser), daemon=True).start()
    host = "0.0.0.0" if args.lan else "127.0.0.1"
    try:
        return subprocess.call(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", host, "--port", str(args.port), "--log-level", "warning"],
            cwd=BACKEND, env=env,
        )
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
