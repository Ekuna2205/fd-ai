import pytest
from pydantic import ValidationError

from app.core.config import Settings

SECRET = "s" * 40


def test_database_url_is_assembled_and_escaped():
    s = Settings(_env_file=None, database_url="", jwt_secret=SECRET, postgres_password="p@ss/word:1", postgres_host="db")
    assert s.database_url == "postgresql+psycopg://faceguard:p%40ss%2Fword%3A1@db:5432/faceguard"


def test_explicit_database_url_wins():
    s = Settings(_env_file=None, database_url="sqlite://", jwt_secret=SECRET)
    assert s.database_url == "sqlite://"


@pytest.mark.parametrize("kwargs", [
    {"jwt_secret": "short", "database_url": "sqlite://"},
    {"jwt_secret": "CHANGE_ME" * 5, "database_url": "sqlite://"},
    {"jwt_secret": SECRET, "database_url": "", "postgres_password": ""},
    {"jwt_secret": SECRET, "database_url": "", "postgres_password": "CHANGE_ME"},
])
def test_unsafe_or_missing_secrets_are_rejected(kwargs):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **kwargs)


def test_production_rejects_wildcard_cors_but_development_allows_it():
    base = dict(_env_file=None, database_url="sqlite://", jwt_secret=SECRET, cors_origins="*")
    with pytest.raises(ValidationError):
        Settings(environment="production", **base)
    assert Settings(environment="development", **base).is_production is False
    assert Settings(environment="Production", **{**base, "cors_origins": "https://app.example.com"}).is_production is True


def test_production_warns_when_docs_are_enabled(caplog):
    import logging
    from app.core.config import get_settings
    from app.main import create_app
    s = get_settings()
    old = (s.environment, s.docs_enabled)
    try:
        s.environment, s.docs_enabled = "production", True
        with caplog.at_level(logging.WARNING, logger="faceguard"):
            create_app()
    finally:
        s.environment, s.docs_enabled = old
    assert any("DOCS_ENABLED=true in production" in r.message for r in caplog.records)
