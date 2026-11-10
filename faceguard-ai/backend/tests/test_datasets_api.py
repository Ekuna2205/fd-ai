"""Dataset API: ownership, roles, validation, export. Uses synthetic images created in the test."""
import io
import zipfile

import cv2
import numpy as np
import pytest

from app.api.routes import datasets as routes
from app.core.config import get_settings
from tests.conftest import headers, register


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "data_dir", str(tmp_path))
    routes.get_store.cache_clear()
    yield
    routes.get_store.cache_clear()


def _researcher(client, admin, email):
    body = register(client, email, "Res Earcher").json()
    client.patch(f"/api/users/{body['user']['id']}", json={"role": "researcher"}, headers=admin["h"])
    return {"user": body["user"], "h": headers(body["access_token"])}


@pytest.fixture
def res_a(client, admin):
    return _researcher(client, admin, "ra@example.com")


@pytest.fixture
def res_b(client, admin):
    return _researcher(client, admin, "rb@example.com")


def png(seed, side=96):
    return cv2.imencode(".png", np.random.default_rng(seed).integers(0, 255, (side, side, 3), dtype=np.uint8))[1].tobytes()


def upload(client, h, ds, data, name="a.png", **form):
    return client.post(f"/api/datasets/{ds}/images", headers=h, files={"file": (name, data, "image/png")}, data=form)


def make(client, h, name="set1"):
    r = client.post("/api/datasets", headers=h, json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_requires_authentication_and_a_writer_role(client, viewer, operator):
    assert client.get("/api/datasets").status_code == 401
    assert client.post("/api/datasets", json={"name": "x"}).status_code == 401
    for who in (viewer, operator):
        assert client.get("/api/datasets", headers=who["h"]).status_code == 403
        assert client.post("/api/datasets", headers=who["h"], json={"name": "x"}).status_code == 403


def test_full_lifecycle(client, res_a):
    h = res_a["h"]; ds = make(client, h)
    r = upload(client, h, ds, png(1), label="REAL", identity="p001"); assert r.status_code == 201
    sha = r.json()["sha256"]
    assert upload(client, h, ds, png(1)).status_code == 409                              # duplicate
    assert upload(client, h, ds, b"MZ not an image", name="x.png").status_code == 415    # content sniffing
    assert upload(client, h, ds, png(2), label="MAYBE").status_code == 422
    assert client.patch(f"/api/datasets/{ds}/images/{sha}", headers=h, json={"label": "FAKE"}).json()["label"] == "FAKE"
    assert client.patch(f"/api/datasets/{ds}/images/{sha}", headers=h, json={"label": None}).json()["label"] is None
    assert client.patch(f"/api/datasets/{ds}/images/{sha}", headers=h, json={"label": "BOGUS"}).status_code == 422
    got = client.get(f"/api/datasets/{ds}", headers=h).json(); assert got["images"] == 1 and got["unlabeled"] == 1
    st = client.get(f"/api/datasets/{ds}/stats", headers=h).json(); assert st["images"] == 1 and st["identities"] == 1
    v = client.get(f"/api/datasets/{ds}/validation", headers=h).json(); assert v["ready"] is False and v["problems"]
    f = client.get(f"/api/datasets/{ds}/images/{sha}/file", headers=h)
    assert f.status_code == 200 and f.headers["content-type"] == "image/png" and "no-store" in f.headers["cache-control"]
    client.patch(f"/api/datasets/{ds}/images/{sha}", headers=h, json={"label": "REAL"})
    z = client.get(f"/api/datasets/{ds}/export", headers=h)
    assert z.status_code == 200 and z.headers["x-exported-images"] == "1"
    names = zipfile.ZipFile(io.BytesIO(z.content)).namelist(); assert "manifest.csv" in names and f"images/{sha}.png" in names
    assert client.delete(f"/api/datasets/{ds}/images/{sha}", headers=h).status_code == 204
    assert client.delete(f"/api/datasets/{ds}", headers=h).status_code == 204
    assert client.get(f"/api/datasets/{ds}", headers=h).status_code == 404


def test_other_users_and_admins_cannot_reach_a_dataset(client, admin, res_a, res_b):
    ds = make(client, res_a["h"]); sha = upload(client, res_a["h"], ds, png(1), label="REAL").json()["sha256"]
    for who in (res_b, admin):
        h = who["h"]
        assert client.get("/api/datasets", headers=h).json() == []
        for method, path in (("GET", ""), ("GET", "/stats"), ("GET", "/validation"), ("GET", "/export"), ("DELETE", ""),
                             ("GET", f"/images/{sha}/file"), ("DELETE", f"/images/{sha}")):
            assert client.request(method, f"/api/datasets/{ds}{path}", headers=h).status_code == 404, (method, path)
        assert upload(client, h, ds, png(5)).status_code == 404
        assert client.patch(f"/api/datasets/{ds}/images/{sha}", headers=h, json={"label": "FAKE"}).status_code == 404
    assert client.get(f"/api/datasets/{ds}", headers=res_a["h"]).json()["images"] == 1


def test_path_traversal_ids_are_not_found(client, res_a):
    for bad in ("..", "%2e%2e", "0" * 32 + "x", "not-a-dataset"):
        assert client.get(f"/api/datasets/{bad}", headers=res_a["h"]).status_code in (404, 422)


def test_duplicate_name_and_oversized_upload(client, res_a, monkeypatch):
    make(client, res_a["h"], "same")
    assert client.post("/api/datasets", headers=res_a["h"], json={"name": "Same"}).status_code == 409
    ds = make(client, res_a["h"], "other"); monkeypatch.setattr(get_settings(), "max_image_mb", 1)
    big = cv2.imencode(".png", np.random.default_rng(2).integers(0, 255, (900, 900, 3), dtype=np.uint8))[1].tobytes()
    assert len(big) > (1 << 20) and upload(client, res_a["h"], ds, big).status_code == 413


def test_dataset_actions_are_audited_without_content(client, res_a, db):
    from sqlalchemy import select
    from app.models.system import AuditLog
    ds = make(client, res_a["h"]); client.delete(f"/api/datasets/{ds}", headers=res_a["h"])
    rows = {a.action: a for a in db.scalars(select(AuditLog).where(AuditLog.action.like("dataset.%")))}
    assert set(rows) == {"dataset.create", "dataset.delete"} and rows["dataset.delete"].details == {"images": 0}


def test_face_crop_export_matches_inference_and_skips_images_without_one_face(client, res_a):
    from tests.conftest import portrait
    ds = make(client, res_a["h"])
    face = cv2.imencode(".png", portrait())[1].tobytes()
    assert upload(client, res_a["h"], ds, face, "face.png", label="REAL", identity="p1").status_code == 201
    assert upload(client, res_a["h"], ds, png(7), "noise.png", label="FAKE", identity="p2").status_code == 201
    r = client.get(f"/api/datasets/{ds}/export?crop=face&face_margin=0.4", headers=res_a["h"])
    assert r.status_code == 200 and r.headers["x-exported-images"] == "1" and r.headers["x-skipped-no-face"] == "1"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert '"crop": "face"' in z.read("preprocessing.json").decode()
    rows = z.read("manifest.csv").decode().strip().splitlines()
    assert len(rows) == 2 and rows[1].startswith("images/") and rows[1].split(",")[0].endswith(".png")
    crop = cv2.imdecode(np.frombuffer(z.read(rows[1].split(",")[0]), np.uint8), cv2.IMREAD_COLOR)
    assert crop.shape[0] == crop.shape[1] and 100 < crop.shape[0] < 300  # a face-sized square, not the 512 px image
    full = client.get(f"/api/datasets/{ds}/export", headers=res_a["h"])
    assert "x-skipped-no-face" not in full.headers and full.headers["x-exported-images"] == "2"
