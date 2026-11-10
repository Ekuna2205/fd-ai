"""Server-side liveness (presentation-attack) inference with ONNX Runtime.

Only the ACTIVE model is ever used, and a model can only become active after model_service.blockers() is empty
(trained, ONNX present, evaluated on >= MIN_EVAL_SAMPLES identity-disjoint test samples with APCER/BPCER/ACER).

Decision rule (deliberately conservative):
    p = P(bona fide) from the model, t = the threshold chosen on the validation split during training
    p >= t + margin  -> REAL       p <= t - margin -> FAKE       otherwise -> UNCERTAIN
A REAL/FAKE verdict is additionally withheld (UNCERTAIN) when the image fails the quality checks, because the model
was not evaluated on such inputs. The score is always reported so a human reviewer can see it.

Preprocessing must match training exactly: `preprocess()` is a copy of ai/faceguard_ai/data.preprocess and a test
asserts the two produce identical tensors.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai import AIModel
from app.services.face.detector import DetectedFace

log = logging.getLogger("faceguard.inference")
CROP_MODES = ("full", "face")
DEFAULT_FACE_MARGIN = 0.4


class ModelLoadError(RuntimeError):
    """The ONNX file cannot be used. Message is safe to show to administrators."""


def preprocess(bgr: np.ndarray, size: int) -> np.ndarray:
    """BGR uint8 -> float32 CHW in [-1, 1], resized to size x size. IDENTICAL to ai/faceguard_ai/data.preprocess."""
    img = cv2.resize(bgr, (size, size), interpolation=cv2.INTER_AREA)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    return ((img - 0.5) / 0.5).transpose(2, 0, 1)


def crop_face(bgr: np.ndarray, face: DetectedFace, margin: float = DEFAULT_FACE_MARGIN) -> np.ndarray:
    """Square crop around a detected face, enlarged by `margin` (0.4 = 40% larger) so screen bezels, paper edges and
    moire around the face stay visible to the model. Pixels outside the image are replicated, never invented.
    The same function produces the training crops (dataset ZIP export with crop=face), so train and serve match."""
    h, w = bgr.shape[:2]
    cx, cy = (face.x + face.w / 2) * w, (face.y + face.h / 2) * h
    side = max(face.w * w, face.h * h) * (1 + margin)
    x0, y0 = round(cx - side / 2), round(cy - side / 2)
    x1, y1 = x0 + round(side), y0 + round(side)
    pad = max(0, -x0, -y0, x1 - w, y1 - h)
    if pad:
        bgr = cv2.copyMakeBorder(bgr, pad, pad, pad, pad, cv2.BORDER_REPLICATE)
        x0, y0, x1, y1 = x0 + pad, y0 + pad, x1 + pad, y1 + pad
    return bgr[y0:y1, x0:x1]


def normalise_preprocessing(p: dict | None) -> dict:
    p = dict(p or {})
    crop = p.get("crop", "full")
    if crop not in CROP_MODES:
        raise ValueError(f"crop must be one of {CROP_MODES}")
    margin = float(p.get("face_margin", DEFAULT_FACE_MARGIN))
    if not 0 <= margin <= 2:
        raise ValueError("face_margin must be between 0 and 2")
    return {"crop": crop, "face_margin": margin}


class LivenessModel:
    """A loaded ONNX classifier: input float32 [N,3,S,S], output [N,2] logits (attack, bona fide)."""

    def __init__(self, path: str | Path, preprocessing: dict | None = None):
        try:
            import onnxruntime as ort
        except ImportError:
            raise ModelLoadError("onnxruntime is not installed on the server (pip install onnxruntime).") from None
        try:
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = max(1, get_settings().inference_threads)
            self._sess = ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])
        except Exception as e:  # noqa: BLE001
            raise ModelLoadError(f"The ONNX file cannot be loaded: {e}") from None
        inp, out = self._sess.get_inputs(), self._sess.get_outputs()
        if len(inp) != 1 or len(inp[0].shape) != 4 or inp[0].shape[1] not in (3, "3"):
            raise ModelLoadError(f"Expected one image input (N,3,S,S); found {[(i.name, i.shape) for i in inp]}.")
        if len(out) != 1 or out[0].shape[-1] != 2:
            raise ModelLoadError(f"Expected one output with 2 logits; found {[(o.name, o.shape) for o in out]}.")
        hw = inp[0].shape[2:]
        if not all(isinstance(v, int) and v > 0 for v in hw) or hw[0] != hw[1]:
            raise ModelLoadError(f"The model input must have a fixed square size; found {hw}.")
        self.size: int = hw[0]
        self.input_name = inp[0].name
        self.preprocessing = normalise_preprocessing(preprocessing)
        self._lock = threading.Lock()

    def prepare(self, bgr: np.ndarray, face: DetectedFace | None) -> np.ndarray:
        if self.preprocessing["crop"] == "face":
            if face is None:
                raise ValueError("This model needs a detected face.")
            bgr = crop_face(bgr, face, self.preprocessing["face_margin"])
        return preprocess(bgr, self.size)

    def predict(self, batch: list[tuple[np.ndarray, DetectedFace | None]]) -> list[float]:
        """Returns P(bona fide) for each (image, face) pair."""
        if not batch:
            return []
        x = np.stack([self.prepare(img, face) for img, face in batch]).astype(np.float32)
        with self._lock:
            (logits,) = self._sess.run(None, {self.input_name: x})
        logits = logits.astype(np.float64)
        e = np.exp(logits - logits.max(axis=1, keepdims=True))
        return [float(v) for v in (e[:, 1] / e.sum(axis=1))]


@dataclass
class ActiveModel:
    id: str
    label: str  # "name v1.2.0", stored on every result it produces
    threshold: float
    model: LivenessModel


_cache: dict[tuple, LivenessModel] = {}
_cache_lock = threading.Lock()


def _resolve(onnx_path: str) -> Path:
    from app.services.model_service import model_dir
    p = Path(onnx_path)
    return (model_dir() / p).resolve() if not p.is_absolute() else p.resolve()


def load_active(db: Session) -> tuple[ActiveModel | None, str | None]:
    """(model, None) when inference is possible, else (None, reason). Loaded sessions are cached per file version."""
    from app.services import model_service
    m = db.scalar(select(AIModel).where(AIModel.is_active.is_(True)))
    if m is None:
        return None, "No liveness model is registered and active."
    if not m.is_trained:
        return None, "The active model is an untrained baseline and is not used for decisions."
    problems = model_service.blockers(m)
    if problems:  # e.g. the ONNX file was deleted after activation
        return None, "The active model no longer meets the activation requirements: " + " ".join(problems)
    ev = model_service.latest_evaluation(m)
    threshold = ev.threshold if ev and ev.threshold is not None else 0.5
    path = _resolve(m.onnx_path or "")
    key = (str(m.id), str(path), path.stat().st_mtime_ns, repr(sorted((m.preprocessing or {}).items())))
    with _cache_lock:
        lm = _cache.get(key)
        if lm is None:
            try:
                lm = LivenessModel(path, m.preprocessing)
            except (ModelLoadError, ValueError) as e:
                log.error("Active model %s v%s cannot be used: %s", m.name, m.version, e)
                return None, f"The active model cannot be loaded: {e}"
            _cache.clear()  # only one active model at a time; drop stale sessions
            _cache[key] = lm
    return ActiveModel(str(m.id), f"{m.name} v{m.version}", float(threshold), lm), None


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


@dataclass
class Verdict:
    status: str  # REAL | FAKE | UNCERTAIN
    confidence: float | None  # probability of the reported class (REAL/FAKE only)
    reason: str


def decide(p: float, threshold: float, quality_ok: bool = True, margin: float | None = None) -> Verdict:
    m = get_settings().liveness_uncertainty_margin if margin is None else margin
    pct = f"{p * 100:.1f}%"
    if not quality_ok:
        return Verdict("UNCERTAIN", None, f"The model's bona fide score is {pct}, but the sample failed quality checks, "
                                          "so no real/fake verdict is given.")
    if p >= min(1.0, threshold + m):
        return Verdict("REAL", round(p, 4), f"The model's bona fide score is {pct} (threshold {threshold:.2f}).")
    if p <= max(0.0, threshold - m):
        return Verdict("FAKE", round(1 - p, 4), f"The model's bona fide score is {pct} (threshold {threshold:.2f}), "
                                               "which indicates a presentation attack.")
    return Verdict("UNCERTAIN", None, f"The model's bona fide score is {pct}, too close to the threshold "
                                      f"({threshold:.2f} ± {m:.2f}) for a verdict.")


class FrameSampler:
    """Keeps at most `cap` evenly spread (frame, face) pairs from a stream of unknown length, in bounded memory:
    when full, every second item is dropped and only every 2nd/4th/... later frame is kept."""

    def __init__(self, cap: int = 16, max_side: int = 480):
        self.cap, self.max_side, self.stride, self.seen = cap, max_side, 1, 0
        self.items: list[tuple[np.ndarray, DetectedFace, bool]] = []

    def add(self, frame: np.ndarray, face: DetectedFace, quality_ok: bool = True) -> None:
        self.seen += 1
        if (self.seen - 1) % self.stride:
            return
        h, w = frame.shape[:2]
        s = min(1.0, self.max_side / max(h, w))
        small = cv2.resize(frame, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else frame.copy()
        self.items.append((small, face, quality_ok))  # face coordinates are normalised, so they survive the resize
        if len(self.items) >= 2 * self.cap:
            self.items = self.items[::2]
            self.stride *= 2

    def pairs(self) -> list[tuple[np.ndarray, DetectedFace]]:
        return [(f, d) for f, d, _ in self.items]

    @property
    def quality_ratio(self) -> float:
        return sum(ok for *_, ok in self.items) / len(self.items) if self.items else 0.0
