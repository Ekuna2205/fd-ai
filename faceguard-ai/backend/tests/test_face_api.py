import numpy as np
import uuid

from sqlalchemy import func, select

from app.core.config import get_settings
from app.models.enums import VerificationStatus
from app.models.system import AuditLog
from app.models.verification import UploadedFile, VerificationResult
from tests.conftest import files, jpeg, noise, png, portrait, post_frame


def _count(db, model):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(model))


def test_endpoints_require_authentication(client):
    assert client.post("/api/face/detect", files={"image": ("f.jpg", b"x")}, data={"consent": "true"}).status_code == 401
    assert client.get("/api/face/capabilities").status_code == 401


def test_viewers_cannot_submit_biometric_samples(client, viewer):
    assert post_frame(client, viewer["h"], jpeg(portrait())).status_code == 403
    assert post_frame(client, viewer["h"], jpeg(portrait()), url="/api/face/verify").status_code == 403
    assert client.post("/api/uploads/image", headers=viewer["h"], files=files("a.jpg", jpeg(portrait())), data={"consent": "true"}).status_code == 403


def test_consent_is_mandatory(client, operator, db):
    r = post_frame(client, operator["h"], jpeg(portrait()), consent="false")
    assert r.status_code == 400 and "Consent" in r.json()["detail"]
    r = client.post("/api/face/detect", headers=operator["h"], files={"image": ("f.jpg", jpeg(portrait()), "image/jpeg")})
    assert r.status_code == 422  # field missing entirely
    assert _count(db, VerificationResult) == 0


def test_capabilities_report_detector_and_missing_liveness(client, operator):
    body = client.get("/api/face/capabilities", headers=operator["h"]).json()
    assert body["detector"]["landmarks"] is True and body["consent_required"] is True
    assert body["liveness"]["available"] is False and body["liveness"]["reason"]
    assert body["limits"]["max_image_mb"] == get_settings().max_image_mb
    assert ".webm" in body["limits"]["video_types"]


def test_live_detect_is_stateless_and_returns_overlay_data(client, operator, db):
    r = post_frame(client, operator["h"], jpeg(portrait()))
    assert r.status_code == 200
    body = r.json()
    assert body["face_count"] == 1 and len(body["faces"][0]["landmarks"]) == 68
    assert body["quality"]["checks"] and body["guidance"] and body["processing_ms"] >= 0
    assert _count(db, VerificationResult) == 0 and _count(db, UploadedFile) == 0  # nothing persisted per frame
    assert post_frame(client, operator["h"], jpeg(noise())).json()["guidance"] == ["Position your face inside the frame."]


def test_detect_rejects_invalid_images(client, operator):
    assert post_frame(client, operator["h"], b"MZ not an image at all").status_code == 415
    assert post_frame(client, operator["h"], jpeg(portrait())[:400]).status_code == 422


def test_verify_never_claims_real_without_a_model(client, operator, db):
    r = post_frame(client, operator["h"], jpeg(portrait()), url="/api/face/verify")
    assert r.status_code == 201
    v = r.json()
    assert v["status"] == "UNCERTAIN" and v["confidence"] is None and v["spoof_type"] is None
    assert v["model_version"] is None and v["liveness"]["available"] is False
    assert "cannot be classified" in v["explanation"] and v["mode"] == "LIVE"
    row = db.get(VerificationResult, uuid.UUID(v["id"]))
    assert row.session.consent_given and row.session.consent_at and str(row.session.user_id) == operator["user"]["id"]
    assert _count(db, UploadedFile) == 0  # live frames keep no file record at all
    again = client.get(f"/api/verifications/{v['id']}", headers=operator["h"]).json()
    assert again["id"] == v["id"] and again["quality"]["checks"]


def test_verify_no_face_and_multiple_faces(client, operator):
    assert post_frame(client, operator["h"], jpeg(noise()), url="/api/face/verify").json()["status"] == "NO_FACE"
    two = np.hstack([portrait(), portrait()])
    r = post_frame(client, operator["h"], jpeg(two), url="/api/face/verify").json()
    assert r["status"] == "MULTIPLE_FACES" and r["face_count"] == 2 and r["quality"] is None


def test_image_upload_stores_metadata_only(client, operator, db):
    data = png(portrait())
    r = client.post("/api/uploads/image", headers=operator["h"], files=files("../../my face.png", data), data={"consent": "true"})
    assert r.status_code == 201 and r.json()["mode"] == "UPLOAD_IMAGE"
    f = db.scalar(select(UploadedFile))
    assert f.original_filename == "my face.png" and f.content_type == "image/png" and f.size_bytes == len(data)
    assert len(f.sha256) == 64 and f.storage_path is None and f.deleted_at is not None and f.status.value == "PROCESSED"


def test_rejected_uploads_are_audited_and_not_recorded_as_results(client, operator, db):
    r = client.post("/api/uploads/image", headers=operator["h"], files=files("evil.jpg", b"MZ" + b"\x00" * 50), data={"consent": "true"})
    assert r.status_code == 415
    r = client.post("/api/uploads/image", headers=operator["h"], files=files("a.png", jpeg(portrait())), data={"consent": "true"})
    assert r.status_code == 415 and "extension" in r.json()["detail"]
    assert _count(db, VerificationResult) == 0
    reasons = [a.details["reason"] for a in db.scalars(select(AuditLog).where(AuditLog.action == "upload.rejected"))]
    assert len(reasons) == 2


def test_oversized_upload_is_rejected(client, operator, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_image_mb", 1)
    big = png(np.random.default_rng(2).integers(0, 255, (900, 900, 3), dtype=np.uint8))
    assert len(big) > (1 << 20)
    assert client.post("/api/uploads/image", headers=operator["h"], files=files("big.png", big), data={"consent": "true"}).status_code == 413


def test_results_flow_into_the_real_dashboard(client, operator, db):
    post_frame(client, operator["h"], jpeg(portrait()), url="/api/face/verify")
    post_frame(client, operator["h"], jpeg(noise()), url="/api/face/verify")
    body = client.get("/api/dashboard/overview", headers=operator["h"]).json()
    t = body["totals"]
    assert (t["attempts"], t["uncertain"], t["failed"], t["real"], t["fake"]) == (2, 1, 1, 0, 0)
    assert {r["status"] for r in body["recent"]} == {"UNCERTAIN", "NO_FACE"}


def test_audit_log_holds_no_biometric_content(client, operator, db):
    post_frame(client, operator["h"], jpeg(portrait()), url="/api/face/verify")
    row = db.scalar(select(AuditLog).where(AuditLog.action == "verification.run"))
    assert set(row.details) == {"mode", "status"}


def test_verification_lookup_errors(client, operator):
    assert client.get("/api/verifications/00000000-0000-4000-8000-000000000000", headers=operator["h"]).status_code == 404
    assert client.get("/api/verifications/nope", headers=operator["h"]).status_code == 422


def test_verify_is_rate_limited(client, operator, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_verify_per_minute", 2)
    codes = [post_frame(client, operator["h"], jpeg(noise()), url="/api/face/verify").status_code for _ in range(4)]
    assert codes == [201, 201, 429, 429]
