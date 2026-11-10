"""Registering a model from the Models page (multipart upload) and deleting it."""
import json
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models.ai import AIModel
from app.models.system import AuditLog
from tests.conftest import headers, register

pytest.importorskip("onnx")
pytest.importorskip("onnxruntime")
from tests.test_inference import build_onnx  # noqa: E402

METRICS = {"n": 400, "n_bona_fide": 200, "n_attack": 200, "threshold": 0.6, "accuracy": 0.95, "precision": 0.94,
           "recall": 0.96, "f1": 0.95, "roc_auc": 0.98, "apcer": 0.05, "bpcer": 0.04, "acer": 0.045,
           "identity_disjoint_split": True}
SPLIT = {"counts": {"train": 2000, "val": 400, "test": 400}, "identity_disjoint": True}


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "data_dir", str(tmp_path / "data"))


def model_files() -> list[Path]:
    return list((Path(get_settings().data_dir) / "models").glob("*.onnx"))


@pytest.fixture
def researcher(client, admin):
    body = register(client, "res@example.com", "Rea Searcher").json()
    client.patch(f"/api/users/{body['user']['id']}", json={"role": "researcher"}, headers=admin["h"])
    return {"user": body["user"], "h": headers(body["access_token"])}


def post_model(client, h, tmp_path, *, name="uploaded", version="1.0.0", onnx_bytes=None, metrics=None, split=None,
               crop="full"):
    data = onnx_bytes if onnx_bytes is not None else build_onnx(tmp_path / "m.onnx", 2.0).read_bytes()
    return client.post("/api/models", headers=h, data={"name": name, "version": version, "architecture": "TinyNet",
                                                        "description": "test", "input_crop": crop},
                       files={"onnx": ("model.onnx", data, "application/octet-stream"),
                              "test_metrics": ("test_metrics.json", json.dumps(metrics or METRICS), "application/json"),
                              "split_report": ("split_report.json", json.dumps(split or SPLIT), "application/json")})


def test_researcher_uploads_validated_model_which_is_not_activated(client, researcher, tmp_path, db):
    r = post_model(client, researcher["h"], tmp_path, crop="face")
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["is_active"] is False and b["is_trained"] and b["has_onnx"] and b["blockers"] == []
    assert b["input_crop"] == "face" and b["latest_evaluation"]["threshold"] == 0.6
    assert (Path(get_settings().data_dir) / "models" / "uploaded-1.0.0.onnx").is_file()
    assert db.scalar(select(AuditLog).where(AuditLog.action == "model.register")) is not None
    act = client.post(f"/api/models/{b['id']}/activate", headers=researcher["h"])
    assert act.status_code == 200 and act.json()["is_active"] is True
    live = client.get("/api/face/capabilities", headers=researcher["h"]).json()["liveness"]
    assert live["available"] is True and live["model"] == "uploaded v1.0.0"


def test_upload_requires_researcher_or_admin(client, viewer, tmp_path):
    assert post_model(client, viewer["h"], tmp_path).status_code == 403


@pytest.mark.parametrize("kwargs,status,fragment", [
    ({"onnx_bytes": b"not a model"}, 400, "cannot be loaded"),
    ({"name": "../evil"}, 400, "may contain only"),
    ({"metrics": {**METRICS, "apcer": 4}}, 400, "outside"),
    ({"metrics": {**METRICS, "n": "lots"}}, 400, "non-negative integer"),
])
def test_bad_uploads_are_rejected_before_anything_is_written(client, admin, tmp_path, kwargs, status, fragment):
    r = post_model(client, admin["h"], tmp_path, **kwargs)
    assert r.status_code == status and fragment in r.json()["detail"], r.text
    assert model_files() == []


def test_wrong_output_shape_is_rejected(client, admin, tmp_path):
    bad = build_onnx(tmp_path / "bad.onnx", 0.0, out_dim=3).read_bytes()
    r = post_model(client, admin["h"], tmp_path, onnx_bytes=bad)
    assert r.status_code == 400 and "2 logits" in r.json()["detail"]


def test_invalid_json_and_duplicate_versions(client, admin, tmp_path):
    files = {"onnx": ("m.onnx", build_onnx(tmp_path / "m.onnx", 0.0).read_bytes()),
             "test_metrics": ("t.json", b"{nope"), "split_report": ("s.json", b"{}")}
    r = client.post("/api/models", headers=admin["h"], data={"name": "x", "version": "1"}, files=files)
    assert r.status_code == 400 and "not valid JSON" in r.json()["detail"]
    assert post_model(client, admin["h"], tmp_path).status_code == 201
    assert post_model(client, admin["h"], tmp_path).status_code == 409


def test_weak_evidence_is_registered_but_blocked(client, admin, tmp_path):
    b = post_model(client, admin["h"], tmp_path, metrics={**METRICS, "n": 12}, split={**SPLIT, "identity_disjoint": False}).json()
    assert any("at least" in x for x in b["blockers"]) and any("identity-disjoint" in x for x in b["blockers"])
    assert client.post(f"/api/models/{b['id']}/activate", headers=admin["h"]).status_code == 409


def test_delete_requires_deactivation_and_removes_the_file(client, admin, tmp_path, db):
    b = post_model(client, admin["h"], tmp_path).json()
    client.post(f"/api/models/{b['id']}/activate", headers=admin["h"])
    assert client.delete(f"/api/models/{b['id']}", headers=admin["h"]).status_code == 409
    client.post(f"/api/models/{b['id']}/deactivate", headers=admin["h"])
    assert client.delete(f"/api/models/{b['id']}", headers=admin["h"]).status_code == 204
    assert not (Path(get_settings().data_dir) / "models" / "uploaded-1.0.0.onnx").exists()
    assert db.scalar(select(AIModel)) is None
    assert client.get(f"/api/models/{b['id']}", headers=admin["h"]).status_code == 404


def test_results_keep_their_model_label_after_the_model_is_deleted(client, admin, tmp_path):
    from tests.test_inference import selfie, upload
    b = post_model(client, admin["h"], tmp_path).json()
    client.post(f"/api/models/{b['id']}/activate", headers=admin["h"])
    res = upload(client, admin["h"], selfie()).json()
    assert res["status"] == "REAL" and np.isclose(res["score"]["threshold"], 0.6)
    client.post(f"/api/models/{b['id']}/deactivate", headers=admin["h"])
    client.delete(f"/api/models/{b['id']}", headers=admin["h"])
    again = client.get(f"/api/verifications/{res['id']}", headers=admin["h"]).json()
    assert again["model_version"] == "uploaded v1.0.0" and again["score"]["model"] == "uploaded v1.0.0"
