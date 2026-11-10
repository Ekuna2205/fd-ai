"""Model registry rules: nothing is activated without real, sufficient, identity-disjoint evidence."""
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models.ai import AIModel
from app.models.system import AuditLog
from tests.conftest import add_evaluation, add_model


@pytest.fixture
def model_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "data_dir", str(tmp_path))
    d = tmp_path / "models"
    d.mkdir()
    return d


def good_model(db, model_dir, name="cnn", version="1", **kw):
    m = add_model(db, active=False, trained=True, name=name, version=version)
    (model_dir / f"{name}-{version}.onnx").write_bytes(b"onnx-bytes")
    m.onnx_path = f"{name}-{version}.onnx"
    db.commit()
    add_evaluation(db, m, apcer=0.04, bpcer=0.03, acer=0.035, sample_count=kw.get("n", 500), threshold=0.5,
                   report={"identity_disjoint": kw.get("disjoint", True)})
    return m


def activate(client, h, m):
    return client.post(f"/api/models/{m.id}/activate", headers=h)


def test_requires_authentication(client):
    assert client.get("/api/models").status_code == 401


def test_empty_registry(client, viewer):
    assert client.get("/api/models", headers=viewer["h"]).json() == []


def test_list_and_detail_expose_evidence_and_blockers(client, viewer, db, model_dir):
    m = good_model(db, model_dir)
    body = client.get("/api/models", headers=viewer["h"]).json()[0]
    assert body["blockers"] == [] and body["has_onnx"] is True and body["latest_evaluation"]["acer"] == 0.035
    assert body["latest_evaluation"]["identity_disjoint"] is True
    detail = client.get(f"/api/models/{m.id}", headers=viewer["h"]).json()
    assert len(detail["evaluations"]) == 1
    assert client.get("/api/models/00000000-0000-4000-8000-000000000000", headers=viewer["h"]).status_code == 404


def test_untrained_model_cannot_be_activated(client, admin, db, model_dir):
    m = add_model(db, active=False, trained=False)
    r = activate(client, admin["h"], m)
    assert r.status_code == 409 and "not trained" in r.json()["detail"]
    db.expire_all()
    assert db.get(AIModel, m.id).is_active is False
    assert db.scalar(select(AuditLog).where(AuditLog.action == "model.activate_refused")) is not None


@pytest.mark.parametrize("case,expect", [
    ("no_onnx", "No ONNX file"), ("no_eval", "not been evaluated"), ("few", "at least"),
    ("not_disjoint", "identity-disjoint"), ("no_pad", "APCER/BPCER/ACER"),
])
def test_each_missing_piece_of_evidence_blocks_activation(client, admin, db, model_dir, case, expect):
    m = add_model(db, active=False, trained=True)
    if case != "no_onnx":
        (model_dir / "m.onnx").write_bytes(b"x")
        m.onnx_path = "m.onnx"
        db.commit()
    if case != "no_eval":
        kw = dict(apcer=0.1, bpcer=0.1, acer=0.1, sample_count=500, report={"identity_disjoint": True})
        if case == "few": kw["sample_count"] = 5
        if case == "not_disjoint": kw["report"] = {"identity_disjoint": False}
        if case == "no_pad": kw["acer"] = None
        add_evaluation(db, m, **kw)
    r = activate(client, admin["h"], m)
    assert r.status_code == 409 and expect in r.json()["detail"]


def test_onnx_path_cannot_escape_model_directory(client, admin, db, model_dir, tmp_path):
    secret = tmp_path / "secret.onnx"
    secret.write_bytes(b"not a model")
    m = good_model(db, model_dir)
    m.onnx_path = "../secret.onnx"
    db.commit()
    assert "No ONNX file" in activate(client, admin["h"], m).json()["detail"]
    m.onnx_path = str(secret)
    db.commit()
    assert activate(client, admin["h"], m).status_code == 409


def test_valid_model_activates_and_replaces_the_previous_one(client, admin, db, model_dir):
    a, b = good_model(db, model_dir, "a"), good_model(db, model_dir, "b")
    assert activate(client, admin["h"], a).json()["is_active"] is True
    assert activate(client, admin["h"], b).json()["is_active"] is True
    db.expire_all()
    assert [m.name for m in db.scalars(select(AIModel).where(AIModel.is_active.is_(True)))] == ["b"]
    assert client.get("/api/dashboard/overview", headers=admin["h"]).json()["active_model"]["name"] == "b"


def test_deactivate(client, admin, db, model_dir):
    m = good_model(db, model_dir)
    activate(client, admin["h"], m)
    assert client.post(f"/api/models/{m.id}/deactivate", headers=admin["h"]).json()["is_active"] is False
    assert client.get("/api/dashboard/overview", headers=admin["h"]).json()["active_model"] is None


def test_only_administrators_and_researchers_manage_models(client, admin, viewer, operator, db, model_dir):
    m = good_model(db, model_dir)
    for who in (viewer, operator):
        assert activate(client, who["h"], m).status_code == 403
        assert client.post(f"/api/models/{m.id}/deactivate", headers=who["h"]).status_code == 403
    db.expire_all()
    assert db.get(AIModel, m.id).is_active is False
    client.patch(f"/api/users/{viewer['user']['id']}", json={"role": "researcher"}, headers=admin["h"])
    assert activate(client, viewer["h"], m).status_code == 200
