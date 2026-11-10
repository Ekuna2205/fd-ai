"""Image quality assessment for a single detected face.

Thresholds are practical heuristics for webcam capture, not biometric-standard values.
Tune them in THRESHOLDS; they are applied identically to live frames, uploads and video.
"""
import cv2
import numpy as np

from app.schemas.face import Quality, QualityCheck
from app.services.face.detector import DetectedFace
from app.core.i18n import tr

THRESHOLDS = {
    "face_width_min": 0.18,   # fraction of image width
    "face_width_max": 0.65,
    "center_x": (0.30, 0.70),
    "center_y": (0.25, 0.75),
    "roll_max_deg": 20.0,
    "brightness": (70.0, 200.0),  # mean grey level of the face region (0..255)
    "sharpness_min": 40.0,        # variance of Laplacian on a 128x128 face crop
    "contrast_min": 25.0,         # std of grey level in the face region
}


def _crop(bgr: np.ndarray, f: DetectedFace) -> np.ndarray:
    h, w = bgr.shape[:2]
    x0, y0 = max(0, int(f.x * w)), max(0, int(f.y * h))
    x1, y1 = min(w, int((f.x + f.w) * w)), min(h, int((f.y + f.h) * h))
    return bgr[y0:y1, x0:x1]


def assess(bgr: np.ndarray, face: DetectedFace) -> Quality:
    t = THRESHOLDS
    crop = cv2.resize(cv2.cvtColor(_crop(bgr, face), cv2.COLOR_BGR2GRAY), (128, 128), interpolation=cv2.INTER_AREA)
    brightness, contrast = float(crop.mean()), float(crop.std())
    sharpness = float(cv2.Laplacian(crop, cv2.CV_64F).var())
    cx, cy = face.x + face.w / 2, face.y + face.h / 2

    def check(name, label, value, ok, message):
        return QualityCheck(name=name, label=tr(label), value=None if value is None else round(value, 3),
                            ok=ok, message=None if ok else tr(message))

    size_msg = "Move closer to the camera." if face.w < t["face_width_min"] else "Move back a little."
    checks = [
        check("size", "Face size", face.w, t["face_width_min"] <= face.w <= t["face_width_max"], size_msg),
        check("position", "Face position", cx,
              t["center_x"][0] <= cx <= t["center_x"][1] and t["center_y"][0] <= cy <= t["center_y"][1],
              "Center your face in the frame."),
        check("brightness", "Lighting", brightness, t["brightness"][0] <= brightness <= t["brightness"][1],
              "Improve lighting: your face is too dark." if brightness < t["brightness"][0]
              else "Reduce bright light on your face."),
        check("contrast", "Contrast", contrast, contrast >= t["contrast_min"], "Improve lighting: the image looks flat."),
        check("sharpness", "Sharpness", sharpness, sharpness >= t["sharpness_min"], "Hold still: the image is blurry."),
    ]
    if face.roll_degrees is not None:
        checks.append(check("roll", "Head tilt", face.roll_degrees, abs(face.roll_degrees) <= t["roll_max_deg"],
                            "Keep your head level."))
    return Quality(ready=all(c.ok for c in checks), checks=checks)


def guidance(face_count: int, quality: Quality | None) -> list[str]:
    if face_count == 0:
        return [tr("Position your face inside the frame.")]
    if face_count > 1:
        return [tr("Only one person should be in the frame.")]
    assert quality is not None
    issues = [c.message for c in quality.checks if c.message]
    return issues or [tr("Looks good. Keep your face visible.")]
