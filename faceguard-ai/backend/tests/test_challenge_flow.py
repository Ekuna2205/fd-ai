"""Server-side challenge flow. Pure logic: needs neither FastAPI nor a database (so it also runs offline)."""
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1]))
from app.services import challenge as ch  # noqa: E402
from app.services import challenge_flow as cf  # noqa: E402
from app.services import challenge_video as cv  # noqa: E402

SECRET = "x" * 40
K, O = ch.Kind, ch.Observation


def _tok(user="u1", now=1000.0, seed=1, **kw):
    return cf.issue(SECRET, user, ch.Config(sequence_length=1, allowed=(K.BLINK,)), seed=seed, now=now, **kw)


def _pass_obs(offset=0.0):
    return [O(offset + i * .1, 1, e, 0.0) for i, e in enumerate([.3, .3, .15, .15, .3, .3])]


def test_token_roundtrip_and_public_view_hides_signature():
    token, view = _tok()
    p = cf.open_token(SECRET, token, "u1", cf.NonceStore(), now=1001.0)
    assert p["seq"] == ["BLINK"] and view["steps"][0]["instruction"] == "Blink once, naturally."
    assert token not in str(view) and "sig" not in view
    assert view["expires_at"] == 1120


def test_token_cannot_be_forged_edited_or_reused():
    token, _ = _tok()
    store = cf.NonceStore()
    body, sig = token.split(".")
    for bad in (token[:-2] + "AA", body + ".", "garbage", "", f"{body}x.{sig}", cf._b64(b"{}") + "." + sig):
        try:
            cf.open_token(SECRET, bad, "u1", store, now=1001.0); raise AssertionError(f"accepted {bad!r}")
        except cf.TokenError:
            pass
    # a different secret cannot validate it
    try:
        cf.open_token("y" * 40, token, "u1", store, now=1001.0); raise AssertionError("wrong secret accepted")
    except cf.TokenError:
        pass
    cf.open_token(SECRET, token, "u1", store, now=1001.0)
    try:
        cf.open_token(SECRET, token, "u1", store, now=1002.0); raise AssertionError("replay accepted")
    except cf.TokenError as e:
        assert "already used" in str(e)


def test_token_is_bound_to_user_and_expires():
    token, _ = _tok()
    try:
        cf.open_token(SECRET, token, "someone-else", cf.NonceStore(), now=1001.0); raise AssertionError
    except cf.TokenError as e:
        assert str(e) == "The challenge is not valid."
    try:
        cf.open_token(SECRET, token, "u1", cf.NonceStore(), now=1121.0); raise AssertionError
    except cf.TokenError as e:
        assert "expired" in str(e)


def test_failed_user_binding_does_not_burn_the_nonce():
    token, _ = _tok()
    store = cf.NonceStore()
    try:
        cf.open_token(SECRET, token, "attacker", store, now=1001.0)
    except cf.TokenError:
        pass
    cf.open_token(SECRET, token, "u1", store, now=1002.0)  # the real owner can still use it


def test_nonce_store_prunes_expired_entries():
    s = cf.NonceStore()
    assert s.consume("a", 10, now=0) and not s.consume("a", 10, now=1)
    assert s.consume("a", 30, now=20)  # expired entry was pruned, so this is a fresh nonce
    assert len(s._seen) == 1


def test_evaluate_passes_only_when_server_measurements_show_the_action():
    token, _ = _tok()
    p = cf.open_token(SECRET, token, "u1", cf.NonceStore(), now=1001.0)
    r = cf.evaluate(p, _pass_obs())
    assert r["outcome"] == "PASSED" and "does not prove" in r["note"]
    still = [O(i * .1, 1, .3, 0.0) for i in range(30)]
    assert cf.evaluate(p, still)["outcome"] == "FAILED"                 # nothing happened
    assert cf.evaluate(p, [])["outcome"] == "FAILED"                    # empty recording
    assert cf.evaluate(p, _pass_obs()[:3])["outcome"] == "FAILED"       # too few measurable frames
    assert cf.evaluate(p, [O(i * .1, 2, None, None) for i in range(30)])["outcome"] == "FAILED"
    late = [O(0, 1, .3, 0), O(30, 1, .3, 0)]
    assert cf.evaluate(p, late + _pass_obs(31))["outcome"] == "TIMED_OUT"


def test_evaluate_uses_the_signed_sequence_not_anything_client_supplied():
    token, _ = cf.issue(SECRET, "u1", ch.Config(sequence_length=1, allowed=(K.TURN_LEFT,)), seed=1, now=1000.0)
    p = cf.open_token(SECRET, token, "u1", cf.NonceStore(), now=1001.0)
    assert cf.evaluate(p, _pass_obs())["outcome"] == "FAILED"           # a blink does not satisfy a turn challenge
    turn = [O(i * .1, 1, .3, y) for i, y in enumerate([0, 0, .2, .4, .5, .5])]
    assert cf.evaluate(p, turn)["outcome"] == "PASSED"


def test_unsorted_observations_are_ordered_by_server_time():
    token, _ = _tok()
    p = cf.open_token(SECRET, token, "u1", cf.NonceStore(), now=1001.0)
    assert cf.evaluate(p, list(reversed(_pass_obs())))["outcome"] == "PASSED"


def test_describe_never_claims_liveness_or_classification():
    d = cf.describe(face_detected=True, quality_passed=True, challenge_outcome="PASSED")
    assert d["challenge_completed"] is True
    assert d["liveness_assessed"] is False and d["ai_classification_available"] is False
    assert "NOT been verified" in d["statement"]
    assert cf.describe(face_detected=False, quality_passed=None, challenge_outcome=None)["challenge_completed"] is False


# ---------- recording -> observations, with a fake detector that reads its "face" from pixel colour ----------
def _landmarks(ear_h: float, nose_x: float):
    p = [(0.5, 0.5)] * 68
    p = list(p); p[0] = (0.2, .5); p[16] = (0.8, .5); p[30] = (0.2 + 0.6 * nose_x, .55)
    for base in (36, 42):
        x0 = 0.3 if base == 36 else 0.55
        p[base] = (x0, .4); p[base + 3] = (x0 + .1, .4)
        p[base + 1] = (x0 + .03, .4 - ear_h * .05); p[base + 5] = (x0 + .03, .4 + ear_h * .05)
        p[base + 2] = (x0 + .07, .4 - ear_h * .05); p[base + 4] = (x0 + .07, .4 + ear_h * .05)
    return p


class FakeDetector:
    """Blue channel encodes eye openness (200 = open, 40 = closed); green encodes yaw (128 = frontal)."""
    def detect(self, bgr):
        b, g = float(bgr[:, :, 0].mean()), float(bgr[:, :, 1].mean())
        if b < 10:
            return SimpleNamespace(faces=[])
        ear_h = 0.3 if b > 120 else 0.1
        nose = 0.5 + (g - 128) / 255.0
        return SimpleNamespace(faces=[SimpleNamespace(landmarks=_landmarks(ear_h, nose))])


def _write(path, blues, greens=None, fps=10):
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (128, 128))
    for i, b in enumerate(blues):
        f = np.zeros((128, 128, 3), np.uint8); f[:, :, 0] = b; f[:, :, 1] = greens[i] if greens else 128
        w.write(f)
    w.release()


def test_recording_pipeline_detects_a_blink_and_rejects_a_still_face():
    with tempfile.TemporaryDirectory() as d:
        blink, still = Path(d) / "blink.mp4", Path(d) / "still.mp4"
        _write(blink, [200] * 6 + [40] * 3 + [200] * 6)
        _write(still, [200] * 15)
        for path, expected in ((blink, "PASSED"), (still, "FAILED")):
            obs, info = cv.observe(str(path), FakeDetector(), max_seconds=20)
            assert info["face_detected"] and info["frames_analysed"] >= 10
            payload = {"seq": ["BLINK"], "timeout": 8.0, "mirrored": True}
            assert cf.evaluate(payload, obs)["outcome"] == expected, (path.name, expected)


def test_recording_pipeline_rejects_unreadable_and_overlong_files():
    with tempfile.TemporaryDirectory() as d:
        junk = Path(d) / "junk.mp4"; junk.write_bytes(b"not a video at all" * 10)
        try:
            cv.observe(str(junk), FakeDetector(), 20); raise AssertionError
        except cv.VideoError:
            pass
        long = Path(d) / "long.mp4"; _write(long, [200] * 60)           # 6 s
        try:
            cv.observe(str(long), FakeDetector(), max_seconds=2); raise AssertionError
        except cv.VideoError as e:
            assert "too long" in str(e)
