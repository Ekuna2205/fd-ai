"""Runs the real Alembic migration on a scratch PostgreSQL database. Skipped on SQLite."""
import os

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

import app.models  # noqa: F401
from app.database.base import Base

URL = os.environ["DATABASE_URL"]
pytestmark = pytest.mark.skipif(not URL.startswith("postgresql"), reason="migration test needs PostgreSQL")


def test_upgrade_matches_models_and_downgrades_cleanly():
    base = make_url(URL)
    scratch = base.set(database="faceguard_migration_test")
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text("DROP DATABASE IF EXISTS faceguard_migration_test"))
        c.execute(text("CREATE DATABASE faceguard_migration_test"))
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "migrations"))
    cfg.attributes["url"] = scratch.render_as_string(hide_password=False)
    engine = create_engine(scratch)
    try:
        command.upgrade(cfg, "head")
        assert "users" in inspect(engine).get_table_names()
        with engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        assert diff == [], f"models and migration disagree: {diff}"
        command.downgrade(cfg, "base")
        assert inspect(engine).get_table_names() == ["alembic_version"]
    finally:
        engine.dispose()
        with admin.connect() as c:
            c.execute(text("DROP DATABASE IF EXISTS faceguard_migration_test"))
        admin.dispose()
