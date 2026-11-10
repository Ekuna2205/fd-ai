"""Liveness challenge API. A fake detector reads 'eye openness' and 'yaw' from frame colour, so the REAL route, token
checks, video decoding, backend measurement and persistence run end to end without the landmark model."""
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.models.system import AuditLog  # noqa: F401
from tests.conftest import headers, register
from tests.test_challenge_flow import FakeDetector


class _Det(FakeDetector):
    has_landmarks = True


@pytest.fixture(autouse=True)
def _fake_detector(monkeypatch):
    monkeypatch.setattr("app.api.routes.face.get_detector", lambda: _Det())


def _video(steps, fps=10, still=False) -> bytes:
    blues, greens = [], []
    def add(n, b=200, g=128):
        blues.extend([b] * n); greens.extend([g] * n)
    add(5)
    for s in steps:
        if still: add(10); continue
        if s["kind"] == "BLINK": add(3, 40); add(4)
        elif s["kind"] == "TURN_LEFT": add(5, g=188); add(3)
        else: add(5, g=68); add(3)
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.mp4"
        w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"mp4v"), fps, (128, 128))
        for b, g in zip(blues, greens):
            f = np.zeros((128, 128, 3), np.uint8); f[:, :, 0] = b; f[:, :, 1] = g; w.write(f)
        w.release()
        return p.read_bytes()


def _post(client, h, token, data, consent="true"):
    return client.post("/api/face/challenge/verify", headers=h, data={"token": token, "consent": consent},
                       files={"video": ("c.mp4", data, "video/mp4")})


def test_requires_authentication_and_operator_role(client, viewer):
    assert client.post("/api/face/challenge").status_code == 401
    assert client.post("/api/face/challenge/verify").status_code == 401
    assert client.post("/api/face/challenge", headers=viewer["h"]).status_code == 403


def test_issue_returns_instructions_and_no_way_to_choose_the_sequence(client, operator):
    c = client.post("/api/face/challenge", headers=operator["h"]).json()
    assert c["token"] and len(c["steps"]) == 2 and all(s["instruction"] for s in c["steps"])
    assert c["step_timeout_seconds"] > 0 and c["expires_at"] > 0


def test_completed_challenge_is_verified_by_the_backend_and_is_not_liveness(client, operator, db):
    c = client.post("/api/face/challenge", headers=operator["h"]).json()
    r = _post(client, operator["h"], c["token"], _video(c["steps"]))
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["outcome"] == "PASSED" and b["status"] == "UNCERTAIN"                 # never REAL
    a = b["assessment"]
    assert a["challenge_completed"] is True and a["liveness_assessed"] is False and a["ai_classification_available"] is False
    assert "NOT been verified" in a["statement"] and "does not prove" in b["note"]
    mine = client.get(f"/api/verifications/{b['verification_id']}", headers=operator["h"])
    assert mine.status_code == 200 and mine.json()["status"] == "UNCERTAIN"


def test_frontend_cannot_claim_success_without_the_movements(client, operator):
    c = client.post("/api/face/challenge", headers=operator["h"]).json()
    b = _post(client, operator["h"], c["token"], _video(c["steps"], still=True)).json()
    assert b["outcome"] in ("FAILED", "TIMED_OUT") and b["assessment"]["challenge_completed"] is False
    assert b["can_retry"] is True and b["retry_requires_new_challenge"] is True


def test_token_is_single_use_user_bound_and_unforgeable(client, admin, operator):
    c = client.post("/api/face/challenge", headers=operator["h"]).json(); vid = _video(c["steps"])
    assert _post(client, operator["h"], c["token"], vid).status_code == 201
    again = _post(client, operator["h"], c["token"], vid); assert again.status_code == 400 and "already used" in again.json()["detail"]
    other = client.post("/api/face/challenge", headers=operator["h"]).json()
    assert _post(client, admin["h"], other["token"], vid).status_code == 400            # someone else's token
    assert _post(client, operator["h"], other["token"][:-3] + "AAA", vid).status_code == 400
    assert _post(client, operator["h"], "garbage", vid).status_code == 400


def test_consent_and_file_validation(client, operator):
    c = client.post("/api/face/challenge", headers=operator["h"]).json()
    assert _post(client, operator["h"], c["token"], _video(c["steps"]), consent="false").status_code == 400
    c2 = client.post("/api/face/challenge", headers=operator["h"]).json()
    assert _post(client, operator["h"], c2["token"], b"MZ not a video").status_code == 415


def test_challenge_result_stays_with_its_owner(client, admin, operator):
    c = client.post("/api/face/challenge", headers=operator["h"]).json()
    vid = _post(client, operator["h"], c["token"], _video(c["steps"])).json()["verification_id"]
    assert client.get(f"/api/verifications/{vid}", headers=admin["h"]).status_code == 404
