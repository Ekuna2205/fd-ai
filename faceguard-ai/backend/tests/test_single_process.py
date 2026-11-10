"""Single-process mode (run.py / root Dockerfile): the API serves the web app, SQLite is created by Alembic."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def spa(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>FaceGuard AI</title>")
    (tmp_path / "assets" / "app-123.js").write_text("console.log(1)")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    (tmp_path.parent / "secret.txt").write_text("nope")
    monkeypatch.setenv("FRONTEND_DIR", str(tmp_path))
    from app.core.config import get_settings
    from app.main import create_app
    get_settings.cache_clear()
    try:
        yield TestClient(create_app())
    finally:
        get_settings.cache_clear()


def test_client_routes_get_the_app_shell(spa):
    for path in ("/", "/login", "/history/abc", "/datasets"):
        r = spa.get(path)
        assert r.status_code == 200 and "FaceGuard AI" in r.text
        assert r.headers["cache-control"] == "no-cache"
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
        assert r.headers["permissions-policy"].startswith("camera=(self)")
    assert spa.head("/login").status_code == 200


def test_static_files_and_caching(spa):
    r = spa.get("/assets/app-123.js")
    assert r.status_code == 200 and "immutable" in r.headers["cache-control"]
    assert spa.get("/favicon.svg").status_code == 200
    assert spa.get("/assets/missing.js").status_code == 404  # never the HTML shell for a missing asset


def test_api_paths_are_never_swallowed_by_the_app_shell(spa):
    assert spa.get("/api/health").json()["status"] in {"ok", "degraded"}
    r = spa.get("/api/does-not-exist")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")


def test_path_traversal_is_refused(spa):
    r = spa.get("/..%2Fsecret.txt")
    assert "nope" not in r.text


def test_no_frontend_folder_means_api_only(tmp_path, monkeypatch):
    monkeypatch.setenv("FRONTEND_DIR", str(tmp_path / "missing"))
    from app.core.config import get_settings
    from app.main import create_app
    get_settings.cache_clear()
    try:
        assert TestClient(create_app()).get("/login").status_code == 404
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("given", ["postgres://u:p@h:5432/d", "postgresql://u:p@h:5432/d"])
def test_platform_postgres_urls_get_the_driver(given):
    s = Settings(database_url=given, jwt_secret="x" * 40)
    assert s.database_url == "postgresql+psycopg://u:p@h:5432/d"


def test_alembic_builds_a_working_sqlite_database(tmp_path):
    """Regression: migrations used PostgreSQL's now(), so inserting a user failed on SQLite."""
    from alembic import command
    from alembic.config import Config

    url = f"sqlite:///{tmp_path / 'm.db'}"
    cfg = Config(str(ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend" / "migrations"))
    cfg.attributes["url"] = url
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    with engine.begin() as c:
        c.execute(text("INSERT INTO roles (id, name, description) VALUES ('r1', 'viewer', 'v')"))
        c.execute(text("INSERT INTO users (id, email, full_name, password_hash, role_id, is_active) "
                       "VALUES ('u1', 'a@b.c', 'A', 'h', 'r1', 1)"))
        assert c.execute(text("SELECT created_at FROM users")).scalar() is not None
