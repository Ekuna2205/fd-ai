import cv2
import numpy as np

from app.services.face import quality as q
from app.services.face.detector import get_detector
from tests.conftest import noise, portrait


def test_detects_one_face_with_landmarks_in_normalised_coordinates():
    det = get_detector().detect(portrait())
    assert len(det.faces) == 1
    f = det.faces[0]
    assert 0 <= f.x < 1 and 0 <= f.y < 1 and 0 < f.w <= 1 and f.x + f.w <= 1.01 and f.y + f.h <= 1.01
    assert f.landmarks is not None and len(f.landmarks) == 68
    assert all(0 <= px <= 1 and 0 <= py <= 1 for px, py in f.landmarks)
    assert f.roll_degrees is not None and abs(f.roll_degrees) < 15


def test_no_face_in_noise_or_blank_image():
    d = get_detector()
    assert d.detect(noise()).faces == []
    assert d.detect(np.full((480, 640, 3), 128, np.uint8)).faces == []


def test_two_faces_are_both_found():
    two = np.hstack([portrait(), portrait()])
    assert len(get_detector().detect(two).faces) == 2


def test_quality_passes_for_a_good_portrait():
    img = portrait()
    face = get_detector().detect(img).faces[0]
    quality = q.assess(img, face)
    names = {c.name for c in quality.checks}
    assert {"size", "position", "brightness", "contrast", "sharpness", "roll"} <= names
    assert quality.checks[2].ok and quality.checks[4].ok  # lighting and sharpness fine on the reference image


def test_quality_flags_dark_and_blurry_images_with_user_hints():
    img = portrait()
    face = get_detector().detect(img).faces[0]
    dark = q.assess((img * 0.2).astype(np.uint8), face)
    assert not dark.ready and "too dark" in next(c.message for c in dark.checks if c.name == "brightness")
    blurry = q.assess(cv2.GaussianBlur(img, (0, 0), 12), face)
    assert "blurry" in next(c.message for c in blurry.checks if c.name == "sharpness")


def test_guidance_messages():
    assert q.guidance(0, None) == ["Position your face inside the frame."]
    assert q.guidance(2, None) == ["Only one person should be in the frame."]
    img = portrait()
    face = get_detector().detect(img).faces[0]
    good = q.assess(img, face)
    if good.ready:
        assert q.guidance(1, good) == ["Looks good. Keep your face visible."]


def test_false_positive_on_jpeg_compressed_pair_is_filtered():
    """Regression: JPEG artefacts on hair/background once produced a third, low-weight 'face'."""
    two = np.hstack([portrait(), portrait()])
    decoded = cv2.imdecode(cv2.imencode(".jpg", two, [cv2.IMWRITE_JPEG_QUALITY, 92])[1], 1)
    assert len(get_detector().detect(decoded).faces) == 2


def test_real_face_survives_common_degradations():
    d = get_detector()
    img = portrait()
    for variant in [(img * 0.3).astype(np.uint8), cv2.GaussianBlur(img, (0, 0), 8), cv2.resize(img, None, fx=0.5, fy=0.5),
                    cv2.imdecode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 30])[1], 1)]:
        assert len(d.detect(variant).faces) == 1


# ---- detector selection (YuNet with Haar fallback) ------------------------------------------------------------------
import pytest  # noqa: E402

from app.services.face.detector import HaarFaceDetector, YuNetFaceDetector, build_detector, yunet_to_square  # noqa: E402


def _rotated(img, degrees):
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), degrees, 1)
    return cv2.warpAffine(img, m, (w, h), borderMode=cv2.BORDER_REFLECT)


def test_auto_prefers_yunet_when_installed():
    d = build_detector("auto")
    assert isinstance(d, YuNetFaceDetector)
    assert d.display_name == "opencv-yunet + lbf68"


def test_auto_falls_back_to_haar_when_yunet_missing(tmp_path):
    d = build_detector("auto", yunet_path=str(tmp_path / "missing.onnx"))
    assert isinstance(d, HaarFaceDetector)
    assert len(d.detect(portrait()).faces) == 1


def test_explicit_yunet_without_model_fails_loudly(tmp_path):
    with pytest.raises(RuntimeError, match="missing"):
        build_detector("yunet", yunet_path=str(tmp_path / "missing.onnx"))
    with pytest.raises(ValueError):
        build_detector("retinaface")


def test_broken_yunet_file_falls_back_in_auto_mode(tmp_path):
    bad = tmp_path / "bad.onnx"
    bad.write_bytes(b"not an onnx model")
    assert isinstance(build_detector("auto", yunet_path=str(bad)), HaarFaceDetector)


@pytest.mark.parametrize("kind", ["haar", "yunet"])
def test_both_detectors_agree_on_the_basics(kind):
    d = build_detector(kind)
    img = portrait()
    faces = d.detect(img).faces
    assert len(faces) == 1 and faces[0].landmarks is not None and len(faces[0].landmarks) == 68
    assert d.detect(noise()).faces == []
    assert len(d.detect(np.hstack([img, img])).faces) == 2


def test_yunet_boxes_match_haar_geometry_so_quality_thresholds_still_apply():
    img = portrait()
    a, b = build_detector("haar").detect(img).faces[0], build_detector("yunet").detect(img).faces[0]
    assert abs(a.x - b.x) < 0.03 and abs(a.y - b.y) < 0.03 and abs(a.w - b.w) < 0.03
    assert b.score is not None and b.score > 0.8 and a.score is None


def test_yunet_finds_a_tilted_face_that_haar_misses():
    tilted = _rotated(portrait(), 25)
    assert len(build_detector("yunet").detect(tilted).faces) == 1
    # Documents why YuNet is the default; if OpenCV's cascade ever improves this may start passing.
    assert len(build_detector("haar").detect(tilted).faces) == 0


def test_yunet_to_square_stays_inside_the_image():
    x, y, w, h = yunet_to_square(600, 450, 80, 100, 640, 480)
    assert w == h and x + w <= 640 and y + h <= 480 and x >= 0 and y >= 0
