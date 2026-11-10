"""Verification pipeline: validate -> detect -> assess quality -> liveness model (if active) -> decide -> persist.

Raw images and videos are processed in memory (or a securely deleted temp file) and are never stored.
REAL/FAKE is only ever produced by an ACTIVE, validated ONNX model (services/inference.py), never by detection,
quality or a passed challenge. Without an active model a single clean face is reported UNCERTAIN.
"""
import hashlib
import time
import uuid
from datetime import UTC, datetime

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.i18n import tr
from app.core.errors import AppError, NotFound
from app.models.enums import FileStatus, SessionMode, VerificationStatus as S
from app.models.user import User
from app.models.verification import UploadedFile, VerificationResult, VerificationSession
from app.schemas.face import (Box, DetectionOut, DetectorInfo, Face, ImageInfo, LivenessScore, Quality,
                              VerificationOut, VideoSummary)
from app.repositories import dashboard_repository as dashboard_repo
from app.services import audit_service, inference, liveness
from app.services.face import media, quality as qual, video as video_mod
from app.services.face.detector import Detection, get_detector

NO_MODEL_NOTE = "No trained liveness model is active, so this sample cannot be classified as real or fake."
VIDEO_MIN_PRESENCE = 0.5
VIDEO_MULTI_RATIO = 0.3


def require_consent(consent: bool) -> None:
    if not consent:
        raise AppError("Consent is required before any biometric analysis.", 400)


def _faces_out(det: Detection) -> list[Face]:
    return [Face(box=Box(x=f.x, y=f.y, w=f.w, h=f.h), landmarks=f.landmarks, roll_degrees=f.roll_degrees) for f in det.faces]


def _analyse_image(data: bytes):
    bgr = media.decode_image(data)
    det = get_detector().detect(bgr)
    quality = qual.assess(bgr, det.faces[0]) if len(det.faces) == 1 else None
    return det, quality, qual.guidance(len(det.faces), quality), bgr


def _score(active: inference.ActiveModel, p: float, frames: int) -> LivenessScore:
    return LivenessScore(model=active.label, bona_fide_score=round(p, 4), threshold=active.threshold,
                         uncertainty_margin=get_settings().liveness_uncertainty_margin, frames_scored=frames)


def _quality_gate(ok: bool) -> bool:
    return ok or not get_settings().liveness_require_quality


def detect_frame(data: bytes) -> DetectionOut:
    """Stateless live-preview detection. Nothing is stored."""
    start = time.perf_counter()
    det, quality, guidance, _ = _analyse_image(data)
    d = get_detector()
    return DetectionOut(
        image=ImageInfo(width=det.width, height=det.height), face_count=len(det.faces), faces=_faces_out(det),
        quality=quality, guidance=guidance, detector=DetectorInfo(name=d.display_name, landmarks=d.has_landmarks),
        processing_ms=round((time.perf_counter() - start) * 1000),
    )


def _read_validated(db: Session, user: User, ip: str | None, kind: str, file: UploadFile) -> tuple[bytes, str]:
    limit = get_settings().max_image_mb if kind == "image" else get_settings().max_video_mb
    try:
        data = media.read_limited(file, limit * (1 << 20))
        return data, media.validate(kind, file.filename, data)
    except AppError as e:
        audit_service.record(db, "upload.rejected", user_id=user.id, ip=ip, details={"kind": kind, "reason": e.detail})
        db.commit()
        raise


def _persist(db: Session, user: User, ip: str | None, *, mode: SessionMode, status: S, face_count: int | None,
             quality: Quality | None, video: VideoSummary | None, explanation: str, ms: int,
             file_meta: dict | None, score: LivenessScore | None = None,
             confidence: float | None = None) -> VerificationOut:
    now = datetime.now(UTC)
    session = VerificationSession(user_id=user.id, mode=mode, consent_given=True, consent_at=now, completed_at=now)
    result = VerificationResult(
        session=session, status=status, face_count=face_count, explanation=tr(explanation), processing_ms=ms,
        confidence=confidence, model_version=score.model if score else None,
        quality={"image": quality.model_dump() if quality else None, "video": video.model_dump() if video else None,
                 "liveness": score.model_dump() if score else None},
    )
    db.add_all([session, result])
    db.flush()
    if file_meta:  # metadata only: the media itself is already gone
        db.add(UploadedFile(user_id=user.id, session_id=session.id, status=FileStatus.PROCESSED, deleted_at=now, **file_meta))
    audit_service.record(db, "verification.run", user_id=user.id, ip=ip, entity_type="verification",
                         entity_id=str(result.id), details={"mode": mode.value, "status": status.value})
    db.commit()
    return to_out(db, result)


def to_out(db: Session, r: VerificationResult) -> VerificationOut:
    stored = r.quality or {}
    return VerificationOut(
        id=r.id, created_at=r.created_at, mode=r.session.mode, status=r.status,
        spoof_type=r.spoof_type.value if r.spoof_type else None, confidence=r.confidence, face_count=r.face_count,
        quality=Quality.model_validate(stored["image"]) if stored.get("image") else None,
        video=VideoSummary.model_validate(stored["video"]) if stored.get("video") else None,
        explanation=r.explanation, model_version=r.model_version, processing_ms=r.processing_ms,
        liveness=liveness.availability(db),
        score=LivenessScore.model_validate(stored["liveness"]) if stored.get("liveness") else None,
    )


def _file_meta(file: UploadFile, data: bytes, sniffed: str) -> dict:
    return dict(original_filename=media.safe_filename(file.filename), content_type=media.MIME[sniffed],
                size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def _image_decision(face_count: int, quality: Quality | None, verdict: inference.Verdict | None = None,
                    no_model: str = NO_MODEL_NOTE) -> tuple[S, str]:
    if face_count == 0:
        return S.NO_FACE, "No face was detected in the image."
    if face_count > 1:
        return S.MULTIPLE_FACES, f"{face_count} faces were detected. Verification needs exactly one."
    issues = [c.label.lower() for c in (quality.checks if quality else []) if not c.ok]
    note = f" Quality issues: {', '.join(issues)}." if issues else " Image quality checks passed."
    if verdict is None:
        return S.UNCERTAIN, f"One face was detected.{note} {no_model}"
    return S(verdict.status), f"One face was detected.{note} {verdict.reason}"


def verify_image(db: Session, user: User, ip: str | None, file: UploadFile, mode: SessionMode) -> VerificationOut:
    start = time.perf_counter()
    data, sniffed = _read_validated(db, user, ip, "image", file)
    det, quality, _, bgr = _analyse_image(data)
    verdict = score = None
    active, reason = inference.load_active(db)
    if active is not None and len(det.faces) == 1:
        p = active.model.predict([(bgr, det.faces[0])])[0]
        verdict = inference.decide(p, active.threshold, _quality_gate(bool(quality and quality.ready)))
        score = _score(active, p, 1)
    status, why = _image_decision(len(det.faces), quality, verdict, no_model=_no_model_note(reason))
    ms = round((time.perf_counter() - start) * 1000)
    meta = _file_meta(file, data, sniffed) if mode == SessionMode.UPLOAD_IMAGE else None
    return _persist(db, user, ip, mode=mode, status=status, face_count=len(det.faces), quality=quality, video=None,
                    explanation=why, ms=ms, file_meta=meta, score=score, confidence=verdict.confidence if verdict else None)


def _no_model_note(reason: str | None) -> str:
    """The generic note, plus the concrete reason when an active model exists but cannot be used."""
    if reason and reason.startswith("The active model"):
        return f"{reason} This sample cannot be classified as real or fake."
    return NO_MODEL_NOTE


def _video_decision(v: VideoSummary, verdict: inference.Verdict | None = None, frames_scored: int = 0,
                    no_model: str = NO_MODEL_NOTE) -> tuple[S, str]:
    n = v.frames_analyzed
    if v.frames_multiple_faces / n >= VIDEO_MULTI_RATIO:
        return S.MULTIPLE_FACES, f"More than one face appeared in {v.frames_multiple_faces} of {n} sampled frames."
    if v.face_presence_ratio < VIDEO_MIN_PRESENCE:
        seen = v.frames_single_face + v.frames_multiple_faces
        return S.NO_FACE, f"A face was found in only {seen} of {n} sampled frames."
    base = f"A single face was present in {v.frames_single_face} of {n} sampled frames."
    if verdict is None:
        return S.UNCERTAIN, f"{base} Temporal measurements were recorded but are not used for a decision. {no_model}"
    return S(verdict.status), f"{base} Mean over {frames_scored} scored frames: {verdict.reason}"


def _video_verdict(active: inference.ActiveModel, sampler: inference.FrameSampler):
    s = get_settings()
    scores = active.model.predict(sampler.pairs())
    p = sum(scores) / len(scores)
    if len(scores) < s.liveness_min_video_frames:
        v = inference.Verdict("UNCERTAIN", None, f"Only {len(scores)} frames could be scored; at least "
                                                 f"{s.liveness_min_video_frames} are needed for a verdict.")
    else:
        v = inference.decide(p, active.threshold, _quality_gate(sampler.quality_ratio >= 0.5))
    return v, _score(active, p, len(scores))


def verify_video(db: Session, user: User, ip: str | None, file: UploadFile) -> VerificationOut:
    start = time.perf_counter()
    data, sniffed = _read_validated(db, user, ip, "video", file)
    active, reason = inference.load_active(db)
    sampler = inference.FrameSampler()
    try:
        with media.temp_media(data, ".mp4" if sniffed == "mp4" else ".webm") as path:
            summary = video_mod.analyze(path, get_detector(), on_face=sampler.add if active else None)
    except AppError as e:
        audit_service.record(db, "upload.rejected", user_id=user.id, ip=ip, details={"kind": "video", "reason": e.detail})
        db.commit()
        raise
    verdict = score = None
    if active is not None and sampler.items:
        verdict, score = _video_verdict(active, sampler)
    status, why = _video_decision(summary, verdict, score.frames_scored if score else 0, _no_model_note(reason))
    ms = round((time.perf_counter() - start) * 1000)
    return _persist(db, user, ip, mode=SessionMode.UPLOAD_VIDEO, status=status, face_count=None, quality=None,
                    video=summary, explanation=why, ms=ms, file_meta=_file_meta(file, data, sniffed), score=score,
                    confidence=verdict.confidence if verdict else None)


def get_verification(db: Session, user: User, ip: str | None, verification_id: uuid.UUID) -> VerificationOut:
    """Owner-only. A result that exists but belongs to someone else is indistinguishable from a missing one (404),
    so IDs cannot be probed. Administrators get no exception here: raw per-user results are not an admin feature."""
    r = dashboard_repo.get_owned_result(db, verification_id, user.id)
    if r is None:
        if db.get(VerificationResult, verification_id) is not None:  # exists but not theirs: leave an audit trail
            audit_service.record(db, "verification.access_denied", user_id=user.id, ip=ip,
                                 entity_type="verification", entity_id=str(verification_id))
            db.commit()
        raise NotFound("Verification not found.")
    return to_out(db, r)


def record_challenge_result(db: Session, user: User, ip: str | None, *, info: dict, result: dict,
                            sampler: inference.FrameSampler | None = None) -> VerificationOut:
    """Stores a challenge attempt. The challenge alone never produces REAL/FAKE. With an active model:
    model FAKE -> FAKE (a replayed or printed face can still follow instructions badly or well);
    model REAL and challenge PASSED -> REAL; anything else -> UNCERTAIN."""
    from app.services import challenge as ch
    base = f"{ch.verdict_note(result['outcome'])} Frames measured: {result['frames_measurable']} of {result['frames_total']}."
    active, reason = inference.load_active(db)
    status, score, confidence = S.UNCERTAIN, None, None
    if active is None or sampler is None or not sampler.items:
        explanation = f"{base} Liveness has NOT been verified. {_no_model_note(reason)}"
    else:
        verdict, score = _video_verdict(active, sampler)
        passed = result["outcome"] == "PASSED"
        if verdict.status == "FAKE":
            status, confidence = S.FAKE, verdict.confidence
            explanation = f"{base} {verdict.reason}"
        elif verdict.status == "REAL" and passed:
            status, confidence = S.REAL, verdict.confidence
            explanation = f"{base} The challenge was passed and {verdict.reason[0].lower()}{verdict.reason[1:]}"
        elif verdict.status == "REAL":
            explanation = f"{base} {verdict.reason} A REAL verdict also requires a passed challenge."
        else:
            explanation = f"{base} {verdict.reason}"
    return _persist(db, user, ip, mode=SessionMode.LIVE, status=status,
                    face_count=1 if info["face_detected"] else 0, quality=None, video=None, explanation=explanation,
                    ms=0, file_meta=None, score=score, confidence=confidence)
