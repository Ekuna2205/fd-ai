from unittest.mock import MagicMock

from app.database.session import get_db
from tests.conftest import add_model

KEYS = {"status", "database", "model_loaded", "model_trained"}


def test_health_is_public_and_matches_contract(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and set(r.json()) == KEYS
    assert r.json() == {"status": "ok", "database": True, "model_loaded": False, "model_trained": False}


def test_model_loaded_is_not_claimed_for_a_model_that_cannot_load(client, db):
    add_model(db, trained=True)
    body = client.get("/api/health").json()
    assert body["model_trained"] is True and body["model_loaded"] is False


def test_untrained_active_model_is_reported_as_untrained(client, db):
    add_model(db, trained=False)
    assert client.get("/api/health").json()["model_trained"] is False


def test_health_degrades_when_database_is_down(client):
    broken = MagicMock()
    broken.execute.side_effect = RuntimeError("connection refused")
    client.app.dependency_overrides[get_db] = lambda: broken
    try:
        r = client.get("/api/health")
    finally:
        client.app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json() == {"status": "degraded", "database": False, "model_loaded": False, "model_trained": False}


def test_unexpected_errors_return_safe_500():
    from fastapi.testclient import TestClient
    from app.main import create_app

    def boom():
        raise RuntimeError("secret internal detail")

    app = create_app()
    app.dependency_overrides[get_db] = boom
    with TestClient(app, raise_server_exceptions=False) as c:  # behave like a real client, not a debugger
        r = c.get("/api/health")
    assert r.status_code == 500 and r.json() == {"detail": "Internal server error."}
    assert "secret" not in r.text


def test_api_responses_are_not_cacheable(client):
    r = client.get("/api/health")
    assert r.headers["cache-control"] == "no-store" and r.headers["x-content-type-options"] == "nosniff"


def test_model_loaded_is_true_only_when_the_active_model_loads(client, admin, tmp_path, monkeypatch):
    import pytest
    pytest.importorskip("onnx")
    from tests.test_model_upload import post_model
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "data_dir", str(tmp_path / "data"))
    m = post_model(client, admin["h"], tmp_path).json()
    assert client.get("/api/health").json()["model_loaded"] is False  # registered, not active
    client.post(f"/api/models/{m['id']}/activate", headers=admin["h"])
    assert client.get("/api/health").json()["model_loaded"] is True
