import os

import numpy as np
from sqlalchemy import select

from app.core.config import get_settings
from app.models.verification import UploadedFile
from tests.conftest import files, noise, portrait, write_video


def _shifted_face_frames(n=20):
    base = portrait()
    return [np.roll(base, i * 3, axis=1) for i in range(n)]


def _upload(client, h, path, name):
    with open(path, "rb") as f:
        return client.post("/api/uploads/video", headers=h, files={"file": (name, f.read(), "video/mp4")}, data={"consent": "true"})


def test_mp4_with_a_face_is_analysed_but_not_classified(client, operator, db, tmp_path, monkeypatch):
    scratch = tmp_path / "scratch"; scratch.mkdir()
    monkeypatch.setattr(get_settings(), "upload_temp_dir", str(scratch))
    r = _upload(client, operator["h"], write_video(tmp_path / "a.mp4", _shifted_face_frames()), "a.mp4")
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["status"] == "UNCERTAIN" and v["confidence"] is None and v["mode"] == "UPLOAD_VIDEO"
    s = v["video"]
    assert s["frames_analyzed"] >= 8 and s["face_presence_ratio"] == 1.0 and s["frames_single_face"] == s["frames_analyzed"]
    assert s["position_jitter"] is not None and s["duration_seconds"] == 2.0
    assert os.listdir(scratch) == []  # temp video was securely removed
    f = db.scalar(select(UploadedFile))
    assert f.content_type == "video/mp4" and f.storage_path is None and f.deleted_at is not None


def test_webm_is_supported(client, operator, tmp_path):
    p = write_video(tmp_path / "a.webm", _shifted_face_frames(12), fourcc="VP80")
    r = _upload(client, operator["h"], p, "a.webm")
    assert r.status_code == 201 and r.json()["video"]["frames_analyzed"] > 0


def test_video_without_a_face_is_no_face(client, operator, tmp_path):
    r = _upload(client, operator["h"], write_video(tmp_path / "n.mp4", [noise(480, 640)] * 15), "n.mp4")
    assert r.json()["status"] == "NO_FACE" and r.json()["video"]["frames_no_face"] == r.json()["video"]["frames_analyzed"]


def test_video_with_two_faces_is_multiple_faces(client, operator, tmp_path):
    two = np.hstack([portrait(), portrait()])
    r = _upload(client, operator["h"], write_video(tmp_path / "m.mp4", [two] * 10), "m.mp4")
    assert r.json()["status"] == "MULTIPLE_FACES"


def test_overlong_video_is_rejected(client, operator, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_video_seconds", 1)
    r = _upload(client, operator["h"], write_video(tmp_path / "l.mp4", _shifted_face_frames(20)), "l.mp4")  # 2 s
    assert r.status_code == 413 and "too long" in r.json()["detail"]


def test_corrupt_video_is_rejected_not_classified(client, operator, db):
    junk = b"\x00\x00\x00\x18ftypmp42" + os.urandom(4000)
    r = client.post("/api/uploads/video", headers=operator["h"], files=files("bad.mp4", junk), data={"consent": "true"})
    assert r.status_code == 422
    assert db.scalar(select(UploadedFile)) is None


def test_video_endpoint_rejects_images_and_viewers(client, operator, viewer, tmp_path):
    from tests.conftest import jpeg
    assert client.post("/api/uploads/video", headers=operator["h"], files=files("a.mp4", jpeg(portrait())), data={"consent": "true"}).status_code == 415
    p = write_video(tmp_path / "a.mp4", _shifted_face_frames(10))
    assert _upload(client, viewer["h"], p, "a.mp4").status_code == 403
