"""Turns a recording into challenge observations using the backend's own detector. The client supplies pixels only.

Timestamps come from the container (CAP_PROP_POS_MSEC) or frame index / fps, never from the client. Browser WebM files
often lack duration and fps metadata, so both paths exist; this has NOT been validated against real browser recordings.
"""
from __future__ import annotations

import cv2

from app.services import challenge as ch

TARGET_FPS = 10.0          # analyse about 10 frames per second: enough for a ~150 ms blink
HARD_FRAME_CAP = 900       # never decode more than this many frames (30 s at 30 fps)


class VideoError(ValueError):
    """Unreadable or too-long recording. Message is safe to show to the user."""


def observe(path: str, detector, max_seconds: float, on_face=None) -> tuple[list[ch.Observation], dict]:
    """`on_face(frame, face)` is called for each analysed frame with exactly one face (liveness scoring)."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise VideoError("The recording could not be opened. It may be corrupted or use an unsupported codec.")
    out: list[ch.Observation] = []
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        fps = fps if 5.0 <= fps <= 120.0 else 30.0              # nonsense or missing -> assume 30
        stride = max(1, round(fps / TARGET_FPS))
        idx, last_t, no_face = 0, -1.0, 0
        while idx < HARD_FRAME_CAP and cap.grab():
            if idx % stride == 0:
                ok, frame = cap.retrieve()
                if ok:
                    ms = cap.get(cv2.CAP_PROP_POS_MSEC)
                    t = ms / 1000.0 if ms and ms > 0 else idx / fps
                    if t <= last_t:                              # non-monotonic container clock: fall back
                        t = idx / fps
                    last_t = t
                    if t > max_seconds:
                        raise VideoError(f"The recording is too long. The limit is {max_seconds:.0f} s.")
                    det = detector.detect(frame)
                    lm = det.faces[0].landmarks if len(det.faces) == 1 else None
                    if len(det.faces) == 1 and on_face is not None:
                        on_face(frame, det.faces[0])
                    if len(det.faces) == 1 and lm is not None:
                        ear, yaw = ch.measure(lm)
                        out.append(ch.Observation(t, 1, ear, yaw))
                    else:
                        no_face += len(det.faces) != 1
                        out.append(ch.Observation(t, len(det.faces), None, None))
            idx += 1
    finally:
        cap.release()
    if not out:
        raise VideoError("No frames could be decoded from the recording.")
    first_face = next((o for o in out if o.face_count == 1), None)
    return out, {"frames_analysed": len(out), "frames_without_single_face": no_face,
                 "duration_seconds": round(out[-1].t, 2), "face_detected": first_face is not None}
