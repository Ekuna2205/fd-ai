"""Liveness inference with a real ONNX Runtime session.

The test models are tiny hand-built ONNX graphs whose output is known exactly (a fixed logit bias, or a logit that
follows image brightness), so every decision path - REAL, FAKE, UNCERTAIN, quality gate, broken model - is exercised
through the real API without a trained network or any biometric data."""
import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from app.core.config import get_settings
from app.models.ai import AIModel, ModelEvaluation
from app.services import inference
from app.services.face.detector import DetectedFace
from tests.conftest import files, jpeg, portrait, write_video

onnx = pytest.importorskip("onnx")
pytest.importorskip("onnxruntime")
from onnx import TensorProto, helper  # noqa: E402

AI_DIR = Path(__file__).resolve().parents[2] / "ai"


def build_onnx(path: Path, bias: float, size: int = 16, brightness_gain: float = 0.0, out_dim: int = 2,
               square: bool = True) -> Path:
    """logits = [0, bias + gain * mean(pixels)]  ->  P(bona fide) = sigmoid(bias + gain * mean)."""
    x = helper.make_tensor_value_info("input", TensorProto.FLOAT, ["N", 3, size, size if square else size + 1])
    y = helper.make_tensor_value_info("logits", TensorProto.FLOAT, ["N", out_dim])
    w = np.zeros((3, out_dim), np.float32)
    w[:, -1] = brightness_gain / 3
    b = np.zeros(out_dim, np.float32)
    b[-1] = bias
    nodes = [helper.make_node("GlobalAveragePool", ["input"], ["g"]), helper.make_node("Flatten", ["g"], ["f"]),
             helper.make_node("Gemm", ["f", "W", "B"], ["logits"])]
    inits = [helper.make_tensor("W", TensorProto.FLOAT, w.shape, w.ravel()),
             helper.make_tensor("B", TensorProto.FLOAT, b.shape, b.ravel())]
    model = helper.make_model(helper.make_graph(nodes, "g", [x], [y], inits),
                              opset_imports=[helper.make_opsetid("", 18)], ir_version=10)
    onnx.save(model, path)
    return path


def sigmoid(v: float) -> float:
    return 1 / (1 + np.exp(-v))


@pytest.fixture(autouse=True)
def _fresh_cache():
    inference.clear_cache()
    yield
    inference.clear_cache()


@pytest.fixture
def activate(db):
    """Registers a fully evidenced, ACTIVE model whose ONNX file returns a known score."""
    def _make(bias=0.0, threshold=0.5, crop="full", gain=0.0, name="test-pad"):
        models = Path(get_settings().data_dir) / "models"
        models.mkdir(parents=True, exist_ok=True)
        build_onnx(models / f"{name}.onnx", bias, brightness_gain=gain)
        m = AIModel(name=name, version="1.0.0", architecture="SmallCNN", is_trained=True, is_active=True,
                    onnx_path=f"{name}.onnx", preprocessing={"crop": crop, "face_margin": 0.4})
        m.evaluations.append(ModelEvaluation(
            evaluated_at=datetime.now(UTC), sample_count=get_settings().min_eval_samples, threshold=threshold,
            apcer=0.05, bpcer=0.05, acer=0.05, report={"identity_disjoint": True}))
        db.add(m)
        db.commit()
        return m
    return _make


def selfie() -> np.ndarray:
    """The reference portrait cropped to a centred, close-up face that passes every quality check (like a webcam
    capture). The full portrait shows a small, off-centre face, which correctly fails the quality gate."""
    return cv2.resize(portrait()[0:300, 90:360], None, fx=2, fy=2)


def upload(client, h, img):
    return client.post("/api/uploads/image", headers=h, files=files("a.jpg", jpeg(img), "image/jpeg"), data={"consent": "true"})


# ---- pure functions ---------------------------------------------------------------------------------------------------
def test_decision_rule_has_an_uncertainty_band_and_a_quality_gate():
    assert inference.decide(0.9, 0.5, margin=0.1).status == "REAL"
    assert inference.decide(0.9, 0.5, margin=0.1).confidence == 0.9
    assert inference.decide(0.2, 0.5, margin=0.1).status == "FAKE"
    assert inference.decide(0.2, 0.5, margin=0.1).confidence == 0.8
    for p in (0.41, 0.5, 0.59):
        v = inference.decide(p, 0.5, margin=0.1)
        assert v.status == "UNCERTAIN" and v.confidence is None
    gated = inference.decide(0.99, 0.5, quality_ok=False, margin=0.1)
    assert gated.status == "UNCERTAIN" and "quality" in gated.reason
    assert inference.decide(0.6, 0.5, margin=0.0).status == "REAL"


def test_preprocessing_is_identical_to_the_training_pipeline():
    spec = importlib.util.spec_from_file_location("faceguard_ai", AI_DIR / "faceguard_ai" / "__init__.py",
                                                  submodule_search_locations=[str(AI_DIR / "faceguard_ai")])
    pkg = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("faceguard_ai", pkg)
    spec.loader.exec_module(pkg)
    from faceguard_ai.data import preprocess as train_preprocess
    img = portrait()
    assert np.array_equal(inference.preprocess(img, 112), train_preprocess(img, 112))


def test_face_crop_is_square_enlarged_and_padded_at_the_edges():
    img = np.zeros((100, 200, 3), np.uint8)
    face = DetectedFace(0.4, 0.3, 0.1, 0.2, None, None)  # 20x20 px at (80, 30)
    crop = inference.crop_face(img, face, 0.5)
    assert crop.shape[:2] == (30, 30)
    edge = DetectedFace(0.0, 0.0, 0.2, 0.4, None, None)  # touches the corner: needs replicated padding
    assert inference.crop_face(img, edge, 0.4).shape[:2] == (56, 56)


def test_frame_sampler_keeps_memory_bounded_and_spread():
    s = inference.FrameSampler(cap=4)
    face = DetectedFace(0.1, 0.1, 0.5, 0.5, None, None)
    for i in range(100):
        s.add(np.full((1000, 1000, 3), i % 255, np.uint8), face, quality_ok=i % 2 == 0)
    assert 4 <= len(s.items) < 8
    assert max(f.shape[0] for f, *_ in s.items) == 480  # downscaled copies
    firsts = [int(f[0, 0, 0]) for f, *_ in s.items]
    assert firsts == sorted(firsts) and firsts[-1] - firsts[0] > 50  # spread across the stream


def test_model_loader_rejects_unusable_files(tmp_path):
    with pytest.raises(inference.ModelLoadError, match="2 logits"):
        inference.LivenessModel(build_onnx(tmp_path / "a.onnx", 0, out_dim=3))
    with pytest.raises(inference.ModelLoadError, match="square"):
        inference.LivenessModel(build_onnx(tmp_path / "b.onnx", 0, square=False))
    (tmp_path / "junk.onnx").write_bytes(b"junk")
    with pytest.raises(inference.ModelLoadError, match="cannot be loaded"):
        inference.LivenessModel(tmp_path / "junk.onnx")
    with pytest.raises(ValueError):
        inference.LivenessModel(build_onnx(tmp_path / "c.onnx", 0), {"crop": "body"})


def test_scores_follow_the_input_and_face_crop_changes_what_the_model_sees(tmp_path):
    path = build_onnx(tmp_path / "bright.onnx", 0.0, brightness_gain=4.0)
    full = inference.LivenessModel(path)
    cropped = inference.LivenessModel(path, {"crop": "face", "face_margin": 0.0})
    dark, light = np.zeros((64, 64, 3), np.uint8), np.full((64, 64, 3), 255, np.uint8)
    p_dark, p_light = full.predict([(dark, None), (light, None)])
    assert p_dark == pytest.approx(sigmoid(-4), abs=1e-4) and p_light == pytest.approx(sigmoid(4), abs=1e-4)
    img = dark.copy()
    img[16:48, 16:48] = 255  # a bright "face" on a dark background
    face = DetectedFace(0.25, 0.25, 0.5, 0.5, None, None)
    assert cropped.predict([(img, face)])[0] > full.predict([(img, face)])[0] + 0.3
    with pytest.raises(ValueError):
        cropped.predict([(img, None)])


# ---- through the API ---------------------------------------------------------------------------------------------------
def test_capabilities_name_the_active_model(client, operator, activate):
    activate(bias=3.0)
    live = client.get("/api/face/capabilities", headers=operator["h"]).json()["liveness"]
    assert live == {"available": True, "reason": None, "model": "test-pad v1.0.0"}


@pytest.mark.parametrize("bias,expected", [(3.0, "REAL"), (-3.0, "FAKE"), (0.0, "UNCERTAIN")])
def test_image_verdict_comes_from_the_model(client, operator, activate, bias, expected):
    activate(bias=bias)
    r = upload(client, operator["h"], selfie())
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["status"] == expected
    assert b["model_version"] == "test-pad v1.0.0"
    assert b["score"]["bona_fide_score"] == pytest.approx(sigmoid(bias), abs=1e-3)
    assert b["score"]["threshold"] == 0.5 and b["score"]["frames_scored"] == 1
    assert (b["confidence"] is None) == (expected == "UNCERTAIN")
    stored = client.get(f"/api/verifications/{b['id']}", headers=operator["h"]).json()
    assert stored["status"] == expected and stored["score"] == b["score"]


def test_model_threshold_from_the_evaluation_is_used(client, operator, activate):
    activate(bias=1.0, threshold=0.9)  # p = 0.73: real at 0.5, but FAKE against a strict 0.9 threshold
    assert upload(client, operator["h"], selfie()).json()["status"] == "FAKE"


def test_full_portrait_with_small_off_centre_face_is_gated(client, operator, activate):
    activate(bias=3.0)
    b = upload(client, operator["h"], portrait()).json()
    assert b["status"] == "UNCERTAIN" and b["score"]["bona_fide_score"] > 0.9


def test_poor_quality_withholds_the_verdict_but_still_shows_the_score(client, operator, activate):
    activate(bias=3.0)
    b = upload(client, operator["h"], (selfie() * 0.15).astype(np.uint8)).json()
    if b["face_count"] != 1:
        pytest.skip("detector lost the face in the dark image")
    assert b["status"] == "UNCERTAIN" and b["score"]["bona_fide_score"] > 0.9 and "quality" in b["explanation"]


def test_quality_gate_can_be_switched_off(client, operator, activate, monkeypatch):
    activate(bias=3.0)
    monkeypatch.setattr(get_settings(), "liveness_require_quality", False)
    b = upload(client, operator["h"], (selfie() * 0.15).astype(np.uint8)).json()
    if b["face_count"] == 1:
        assert b["status"] == "REAL"


def test_no_face_is_never_scored(client, operator, activate):
    activate(bias=3.0)
    b = upload(client, operator["h"], np.full((480, 640, 3), 128, np.uint8)).json()
    assert b["status"] == "NO_FACE" and b["score"] is None and b["confidence"] is None


def test_face_crop_model_runs_on_real_detections(client, operator, activate):
    activate(bias=3.0, crop="face")
    b = upload(client, operator["h"], selfie()).json()
    assert b["status"] == "REAL"


def test_missing_onnx_after_activation_falls_back_to_uncertain(client, operator, activate):
    m = activate(bias=3.0)
    (Path(get_settings().data_dir) / "models" / m.onnx_path).unlink()
    live = client.get("/api/face/capabilities", headers=operator["h"]).json()["liveness"]
    assert live["available"] is False and "no longer meets" in live["reason"]
    b = upload(client, operator["h"], selfie()).json()
    assert b["status"] == "UNCERTAIN" and b["score"] is None and "no longer meets" in b["explanation"]


def test_corrupt_onnx_is_reported_not_crashed(client, operator, activate):
    m = activate(bias=3.0)
    (Path(get_settings().data_dir) / "models" / m.onnx_path).write_bytes(b"corrupted")
    b = upload(client, operator["h"], selfie()).json()
    assert b["status"] == "UNCERTAIN" and "cannot be loaded" in b["explanation"]


def test_inactive_trained_model_is_never_used(client, operator, activate, db):
    m = activate(bias=3.0)
    m.is_active = False
    db.commit()
    b = upload(client, operator["h"], selfie()).json()
    assert b["status"] == "UNCERTAIN" and b["score"] is None


def test_video_verdict_is_the_mean_over_sampled_frames(client, operator, activate, tmp_path):
    activate(bias=-3.0)
    path = write_video(tmp_path / "v.mp4", [selfie()] * 12)
    r = client.post("/api/uploads/video", headers=operator["h"], files=files("v.mp4", path.read_bytes(), "video/mp4"),
                    data={"consent": "true"})
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["status"] == "FAKE" and b["score"]["frames_scored"] >= 3 and "scored frames" in b["explanation"]


# ---- challenge: REAL needs BOTH the model and a passed challenge --------------------------------------------------------
@pytest.fixture
def fake_challenge_detector(monkeypatch):
    from tests.test_challenge_api import _Det
    monkeypatch.setattr("app.api.routes.face.get_detector", lambda: _Det())


@pytest.mark.parametrize("bias,still,expected", [(3.0, False, "REAL"), (3.0, True, "UNCERTAIN"), (-3.0, False, "FAKE"),
                                                 (-3.0, True, "FAKE")])
def test_challenge_combines_model_and_movements(client, operator, activate, fake_challenge_detector, bias, still, expected):
    from tests.test_challenge_api import _post, _video
    activate(bias=bias)
    c = client.post("/api/face/challenge", headers=operator["h"]).json()
    b = _post(client, operator["h"], c["token"], _video(c["steps"], still=still)).json()
    assert b["status"] == expected, b
    assert b["assessment"]["ai_classification_available"] is True and b["assessment"]["liveness_assessed"] is True
    stored = client.get(f"/api/verifications/{b['verification_id']}", headers=operator["h"]).json()
    assert stored["status"] == expected and stored["score"]["frames_scored"] >= 1


def test_detector_faces_without_boxes_are_fine_for_full_image_models():
    m = SimpleNamespace(preprocessing={"crop": "full"})
    assert inference.normalise_preprocessing(m.preprocessing) == {"crop": "full", "face_margin": 0.4}
    assert inference.normalise_preprocessing(None)["crop"] == "full"
