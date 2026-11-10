"""Face detection + 68-point landmarks (OpenCV Facemark LBF).

Two box detectors are available behind one interface:

* **YuNet** (OpenCV Zoo CNN, MIT licence): default when its 230 KB ONNX file is installed. Finds faces turned
  further to the side, small faces and faces in poor light far more reliably than Haar, with fewer false positives.
* **Haar cascade**: always available (ships with OpenCV); used when YuNet is missing or FACE_DETECTOR=haar.

This is a *detection* module only. It says where faces are, never whether they are live.
Boxes from both detectors are returned in the same square, Haar-like geometry, because the LBF landmark model and the
quality thresholds were built around that geometry.
"""
import logging
import math
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from app.core.config import get_settings

log = logging.getLogger("faceguard.detector")
MAX_SIDE = 640  # frames are downscaled to this before detection: speed over pixels we do not need
# Haar produces occasional false positives on hair/background. Candidates are kept only if their cascade
# weight is above an absolute floor and not far below the strongest candidate. Eyes are deliberately NOT required
# (a blinking person has closed eyes). Values were tuned on one public-domain portrait: validate on real data.
MIN_WEIGHT = 2.0
RELATIVE_WEIGHT = 0.3
# YuNet: confidence floor and NMS overlap. 0.8 keeps blurred/dark real faces while rejecting textures.
YUNET_SCORE = 0.8
YUNET_NMS = 0.3


@dataclass
class DetectedFace:
    x: float  # normalised 0..1
    y: float
    w: float
    h: float
    landmarks: list[tuple[float, float]] | None
    roll_degrees: float | None
    score: float | None = None  # detector confidence (YuNet only)


@dataclass
class Detection:
    width: int  # original image size
    height: int
    faces: list[DetectedFace]


Box = tuple[int, int, int, int]


class FaceDetector:
    """Base: downscaling, landmark fitting and normalisation. Subclasses only find boxes."""

    name = "base"

    def __init__(self, landmark_model: str | None = None):
        self._facemark = None
        path = landmark_model or get_settings().landmark_model_path
        if path and Path(path).is_file():
            try:
                self._facemark = cv2.face.createFacemarkLBF()
                self._facemark.loadModel(path)
            except Exception:  # noqa: BLE001
                log.exception("Landmark model failed to load; continuing without landmarks")
                self._facemark = None
        else:
            log.warning("Landmark model not found at %s (run scripts/fetch_models.py); boxes only", path)
        self._lock = threading.Lock()  # OpenCV detectors/facemark are not thread-safe

    @property
    def has_landmarks(self) -> bool:
        return self._facemark is not None

    @property
    def display_name(self) -> str:
        return f"{self.name} + lbf68" if self.has_landmarks else self.name

    def _boxes(self, small: np.ndarray) -> list[tuple[Box, float | None]]:
        raise NotImplementedError

    def detect(self, bgr: np.ndarray) -> Detection:
        h, w = bgr.shape[:2]
        scale = min(1.0, MAX_SIDE / max(h, w))
        small = cv2.resize(bgr, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA) if scale < 1 else bgr
        sh, sw = small.shape[:2]
        with self._lock:
            found = sorted(self._boxes(small), key=lambda t: t[0][2] * t[0][3], reverse=True)
            boxes = [b for b, _ in found]
            marks = self._fit_landmarks(small, boxes)
        faces = []
        for ((x, y, bw, bh), score), lm in zip(found, marks):
            pts = [(float(px) / sw, float(py) / sh) for px, py in lm] if lm is not None else None
            faces.append(DetectedFace(x / sw, y / sh, bw / sw, bh / sh, pts, _roll(lm), score))
        return Detection(w, h, faces)

    def _fit_landmarks(self, img: np.ndarray, boxes: list[Box]):
        if not boxes or self._facemark is None:
            return [None] * len(boxes)
        try:
            ok, fitted = self._facemark.fit(img, np.array(boxes, dtype=np.int32))
        except cv2.error:
            return [None] * len(boxes)
        if not ok:
            return [None] * len(boxes)
        return [np.asarray(f).reshape(-1, 2) for f in fitted]


class HaarFaceDetector(FaceDetector):
    name = "opencv-haar-frontal"

    def __init__(self, landmark_model: str | None = None):
        super().__init__(landmark_model)
        cascade = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        self._cascade = cv2.CascadeClassifier(str(cascade))
        if self._cascade.empty():
            raise RuntimeError(f"Could not load OpenCV face cascade at {cascade}")

    def _boxes(self, small: np.ndarray) -> list[tuple[Box, float | None]]:
        sh, sw = small.shape[:2]
        gray = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
        min_size = max(40, int(0.1 * min(sh, sw)))
        found, _, weights = self._cascade.detectMultiScale3(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(min_size, min_size), outputRejectLevels=True)
        weights = [float(w) for w in np.ravel(weights)]
        top = max(weights, default=0.0)
        return [(tuple(int(v) for v in b), None) for b, w in zip(found, weights)
                if w >= MIN_WEIGHT and w >= RELATIVE_WEIGHT * top]


def yunet_to_square(x: float, y: float, w: float, h: float, img_w: int, img_h: int) -> Box:
    """YuNet boxes are tall (forehead to chin). Convert to the square, slightly higher box Haar produces, which is what
    the LBF landmark model was trained on. Ratios measured on the reference portrait (Haar 93x93 vs YuNet 90x113)."""
    side = 0.5 * (w + 0.82 * h)
    cx, cy = x + w / 2, y + h / 2 - 0.05 * h
    x0, y0 = max(0.0, cx - side / 2), max(0.0, cy - side / 2)
    side = min(side, img_w - x0, img_h - y0)
    return round(x0), round(y0), max(1, round(side)), max(1, round(side))


class YuNetFaceDetector(FaceDetector):
    name = "opencv-yunet"

    def __init__(self, model_path: str, landmark_model: str | None = None):
        super().__init__(landmark_model)
        self._net = cv2.FaceDetectorYN.create(model_path, "", (320, 320), YUNET_SCORE, YUNET_NMS, 5000)
        self._size: tuple[int, int] = (320, 320)

    def _boxes(self, small: np.ndarray) -> list[tuple[Box, float | None]]:
        sh, sw = small.shape[:2]
        if (sw, sh) != self._size:
            self._net.setInputSize((sw, sh))
            self._size = (sw, sh)
        _, faces = self._net.detect(small)
        if faces is None:
            return []
        min_side = max(24, int(0.06 * min(sh, sw)))
        out = []
        for f in faces:
            box = yunet_to_square(float(f[0]), float(f[1]), float(f[2]), float(f[3]), sw, sh)
            if box[2] >= min_side:
                out.append((box, round(float(f[14]), 3)))
        return out


def _roll(lm) -> float | None:
    """Head roll from the line between the two eye centres (iBUG 68: right eye 36-41, left eye 42-47)."""
    if lm is None or len(lm) < 48:
        return None
    a, b = lm[36:42].mean(axis=0), lm[42:48].mean(axis=0)
    return round(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])), 1)


def build_detector(kind: str | None = None, yunet_path: str | None = None, landmark_model: str | None = None) -> FaceDetector:
    """kind: auto (YuNet when its model file exists, else Haar) | yunet (required) | haar."""
    s = get_settings()
    kind = (kind or s.face_detector).lower()
    path = yunet_path or s.yunet_model_path
    if kind not in ("auto", "yunet", "haar"):
        raise ValueError(f"FACE_DETECTOR must be auto, yunet or haar, not {kind!r}")
    if kind in ("auto", "yunet"):
        if path and Path(path).is_file():
            try:
                return YuNetFaceDetector(path, landmark_model)
            except cv2.error:
                if kind == "yunet":
                    raise
                log.exception("YuNet model failed to load; falling back to the Haar cascade")
        elif kind == "yunet":
            raise RuntimeError(f"FACE_DETECTOR=yunet but {path} is missing (run scripts/fetch_models.py)")
        else:
            log.warning("YuNet model not found at %s (run scripts/fetch_models.py); using the Haar cascade", path)
    return HaarFaceDetector(landmark_model)


@lru_cache
def get_detector() -> FaceDetector:
    return build_detector()
