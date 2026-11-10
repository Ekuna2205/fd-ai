"""Public collection links (collect.ekyc.mn-style): anonymous participants add labelled recordings to one dataset."""
import cv2
import numpy as np
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models.system import AuditLog
from tests.conftest import portrait, write_video
from tests.test_datasets_api import make  # noqa: F401  (fixtures below)

PID = "a1b2c3d4e5f60718"


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    from app.api.routes.datasets import get_store
    monkeypatch.setattr(get_settings(), "data_dir", str(tmp_path / "data"))
    get_store.cache_clear()
    yield
    get_store.cache_clear()


@pytest.fixture
def res_a(client, admin):
    return admin


def _video(tmp_path, n=20, moving=True):
    base = portrait()
    frames = []
    for i in range(n):  # small shifts so frames differ (identical frames are de-duplicated by content hash)
        m = np.float32([[1, 0, (i % 5) * 2 if moving else 0], [0, 1, 0]])
        frames.append(cv2.warpAffine(base, m, (base.shape[1], base.shape[0]), borderMode=cv2.BORDER_REFLECT))
    return write_video(tmp_path / "v.mp4", frames).read_bytes()


def _link(client, h, ds):
    r = client.put(f"/api/datasets/{ds}/collect", headers=h, json={"enabled": True})
    assert r.status_code == 200, r.text
    return r.json()["collect"]["token"]


def _submit(client, token, data, **form):
    body = {"label": "REAL", "consent": "true", "participant": PID, **form}
    return client.post(f"/api/collect/{token}", data=body, files={"video": ("rec.mp4", data, "video/mp4")})


def test_anonymous_participant_adds_labelled_frames(client, res_a, tmp_path, db):
    ds = make(client, res_a["h"])
    token = _link(client, res_a["h"], ds)
    info = client.get(f"/api/collect/{token}")
    assert info.status_code == 200 and info.json()["step_seconds"] == get_settings().collect_step_seconds
    assert "owner" not in info.json() and "id" not in info.json()
    r = _submit(client, token, _video(tmp_path))
    assert r.status_code == 201, r.text
    assert 1 <= r.json()["added"] <= get_settings().collect_frames
    d = client.get(f"/api/datasets/{ds}", headers=res_a["h"]).json()
    assert d["real"] == r.json()["added"] and d["collect"]["participants"] == 1
    assert {i["identity"] for i in d["items"]} == {f"p-{PID}"} and {i["group"] for i in d["items"]} == {"LIVE"}
    assert db.scalar(select(AuditLog).where(AuditLog.action == "collect.submit")) is not None


def test_fake_needs_an_attack_type_and_is_grouped_by_it(client, res_a, tmp_path):
    ds = make(client, res_a["h"])
    token = _link(client, res_a["h"], ds)
    assert _submit(client, token, _video(tmp_path), label="FAKE").status_code == 422
    r = _submit(client, token, _video(tmp_path), label="FAKE", attack_type="PHONE_SCREEN")
    assert r.status_code == 201
    d = client.get(f"/api/datasets/{ds}", headers=res_a["h"]).json()
    assert d["fake"] >= 1 and {i["group"] for i in d["items"]} == {"PHONE_SCREEN"}


def test_consent_participant_and_face_are_required(client, res_a, tmp_path):
    ds = make(client, res_a["h"])
    token = _link(client, res_a["h"], ds)
    assert _submit(client, token, _video(tmp_path), consent="false").status_code == 400
    assert _submit(client, token, _video(tmp_path), participant="../../etc").status_code == 422
    blank = write_video(tmp_path / "b.mp4", [np.full((240, 320, 3), 90, np.uint8)] * 12).read_bytes()
    r = _submit(client, token, blank)
    assert r.status_code == 422 and "No single face" in r.json()["detail"]
    assert _submit(client, token, b"not a video").status_code in (400, 415, 422)


def test_links_can_be_turned_off_and_rotated(client, res_a, tmp_path):
    ds = make(client, res_a["h"])
    old = _link(client, res_a["h"], ds)
    new = client.put(f"/api/datasets/{ds}/collect", headers=res_a["h"], json={"enabled": True, "rotate": True}).json()["collect"]["token"]
    assert new != old and client.get(f"/api/collect/{old}").status_code == 404
    off = client.put(f"/api/datasets/{ds}/collect", headers=res_a["h"], json={"enabled": False}).json()
    assert off["collect"] == {"enabled": False, "token": None, "participants": 0}
    assert client.get(f"/api/collect/{new}").status_code == 404
    assert _submit(client, new, _video(tmp_path)).status_code == 404
    assert client.get("/api/collect/short").status_code == 404


def test_only_the_owner_manages_the_link(client, res_a, viewer):
    ds = make(client, res_a["h"])
    assert client.put(f"/api/datasets/{ds}/collect", headers=viewer["h"], json={"enabled": True}).status_code == 403


def test_public_link_is_rate_limited_per_ip(client, res_a, monkeypatch):
    ds = make(client, res_a["h"])
    token = _link(client, res_a["h"], ds)
    monkeypatch.setattr(get_settings(), "rate_limit_collect_per_minute", 2)
    codes = [client.get(f"/api/collect/{token}").status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_messages_in_mongolian(client, res_a, tmp_path):
    ds = make(client, res_a["h"])
    token = _link(client, res_a["h"], ds)
    r = client.post(f"/api/collect/{token}", headers={"Accept-Language": "mn"},
                    data={"label": "REAL", "consent": "true", "participant": PID},
                    files={"video": ("rec.mp4", _video(tmp_path), "video/mp4")})
    assert r.json()["message"] == "Баярлалаа! Таны бичлэг нэмэгдлээ."


def test_live_frame_guidance_reports_face_and_head_turn(client, res_a):
    from tests.conftest import jpeg
    ds = make(client, res_a["h"])
    token = _link(client, res_a["h"], ds)
    r = client.post(f"/api/collect/{token}/frame", files={"image": ("f.jpg", jpeg(portrait()), "image/jpeg")})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["face_count"] == 1 and 0 < b["box"]["w"] < 1 and abs(b["yaw"]) < 0.5
    blank = client.post(f"/api/collect/{token}/frame", files={"image": ("f.jpg", jpeg(np.full((240, 320, 3), 90, np.uint8)), "image/jpeg")})
    assert blank.json()["face_count"] == 0 and blank.json()["box"] is None
    assert client.post("/api/collect/nottherighttoken00/frame", files={"image": ("f.jpg", jpeg(portrait()), "image/jpeg")}).status_code == 404


def test_active_model_score_is_returned(client, res_a, tmp_path):
    pytest.importorskip("onnx")
    from tests.test_model_upload import post_model
    m = post_model(client, res_a["h"], tmp_path).json()
    client.post(f"/api/models/{m['id']}/activate", headers=res_a["h"])
    ds = make(client, res_a["h"])
    token = _link(client, res_a["h"], ds)
    b = _submit(client, token, _video(tmp_path)).json()
    assert b["score"]["status"] == "REAL" and b["score"]["bona_fide_score"] > 0.8
