"""Samples frames from a video and summarises detection, quality and temporal stability.

Temporal numbers are descriptive only. They are not used to classify anything until a trained model exists.
"""
import statistics
from collections.abc import Callable

import cv2
import numpy as np

from app.core.config import get_settings
from app.core.errors import AppError
from app.schemas.face import VideoSummary
from app.services.face import quality as q
from app.services.face.detector import DetectedFace, FaceDetector

FaceCallback = Callable[[np.ndarray, DetectedFace, bool], None]  # (frame, face, quality_ready)

UNKNOWN_COUNT_STRIDE = 5   # when the container does not report a frame count, keep every 5th frame
HARD_FRAME_CAP = 1800      # never decode more than this many frames


def _sample_indices(total: int, n: int) -> list[int]:
    if total <= n:
        return list(range(total))
    return sorted({round(i * (total - 1) / (n - 1)) for i in range(n)})


def analyze(path: str, detector: FaceDetector, on_face: FaceCallback | None = None) -> VideoSummary:
    """`on_face` is called for every sampled frame that holds exactly one face (used for liveness scoring)."""
    s = get_settings()
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise AppError("The video could not be opened. It may be corrupted or use an unsupported codec.", 422)
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        known = total > 0 and fps > 0
        duration = total / fps if known else None
        if duration is not None and duration > s.max_video_seconds:
            raise AppError(f"Video is too long ({duration:.0f}s). The limit is {s.max_video_seconds}s.", 413)

        frames = []
        wanted = set(_sample_indices(total, s.video_sample_frames)) if known else None
        idx = 0
        while idx < HARD_FRAME_CAP and cap.grab():
            if (wanted is not None and idx in wanted) or (wanted is None and idx % UNKNOWN_COUNT_STRIDE == 0):
                ok, frame = cap.retrieve()
                if ok:
                    frames.append(frame)
            idx += 1
        if wanted is None:
            seconds = idx / (fps or 30.0)
            if idx >= HARD_FRAME_CAP or seconds > s.max_video_seconds:
                raise AppError(f"Video is too long. The limit is {s.max_video_seconds}s.", 413)
            duration = seconds
            if len(frames) > s.video_sample_frames:
                keep = _sample_indices(len(frames), s.video_sample_frames)
                frames = [frames[i] for i in keep]
    finally:
        cap.release()

    if not frames:
        raise AppError("No frames could be decoded from the video.", 422)

    single = none = multi = ready = 0
    centers, widths = [], []
    for frame in frames:
        det = detector.detect(frame)
        if not det.faces:
            none += 1
        elif len(det.faces) > 1:
            multi += 1
        else:
            single += 1
            f = det.faces[0]
            centers.append((f.x + f.w / 2, f.y + f.h / 2))
            widths.append(f.w)
            ok = q.assess(frame, f).ready
            ready += ok
            if on_face is not None:
                on_face(frame, f, ok)

    jitter = size_var = None
    if len(centers) >= 3:
        jitter = round((statistics.pstdev(c[0] for c in centers) + statistics.pstdev(c[1] for c in centers)) / 2, 4)
        size_var = round(statistics.pstdev(widths) / statistics.fmean(widths), 4)
    n = len(frames)
    return VideoSummary(
        frames_analyzed=n, frames_single_face=single, frames_no_face=none, frames_multiple_faces=multi,
        duration_seconds=round(duration, 2) if duration else None,
        face_presence_ratio=round((single + multi) / n, 3),
        quality_pass_ratio=round(ready / single, 3) if single else None,
        position_jitter=jitter, size_variation=size_var,
    )
