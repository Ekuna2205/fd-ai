from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.api.deps import CurrentUser, DbSession, client_ip, require_roles
from app.core.config import get_settings
from app.core.rate_limit import user_rate_limit
from app.models.enums import RoleName, SessionMode
from app.models.user import User
from app.schemas.face import Capabilities, DetectionOut, DetectorInfo, Limits, VerificationOut
from app.services import challenge_flow as cflow, challenge_video, inference, liveness, verification_service as svc
from app.core.errors import AppError
from app.services.face import media
from app.services.face.detector import get_detector

router = APIRouter(prefix="/face", tags=["face"])
# Viewers are read-only: only these roles may submit biometric samples.
Verifier = Annotated[User, Depends(require_roles(RoleName.ADMINISTRATOR, RoleName.RESEARCHER, RoleName.OPERATOR))]


@router.get("/capabilities", response_model=Capabilities)
def capabilities(db: DbSession, _: CurrentUser) -> Capabilities:
    s, d = get_settings(), get_detector()
    return Capabilities(
        detector=DetectorInfo(name=d.display_name, landmarks=d.has_landmarks),
        liveness=liveness.availability(db),
        limits=Limits(max_image_mb=s.max_image_mb, max_video_mb=s.max_video_mb, max_video_seconds=s.max_video_seconds,
                      image_types=sorted(media.IMAGE_EXT), video_types=sorted(media.VIDEO_EXT)),
    )


@router.post("/detect", response_model=DetectionOut, dependencies=[Depends(user_rate_limit("rate_limit_detect_per_minute"))])
def detect(user: Verifier, db: DbSession, request: Request, image: UploadFile = File(...), consent: bool = Form(...)) -> DetectionOut:
    """Stateless live-preview detection: boxes, landmarks, quality and guidance. Nothing is stored."""
    svc.require_consent(consent)
    data = media.read_limited(image, get_settings().max_image_mb * (1 << 20))
    media.validate("image", image.filename, data)
    return svc.detect_frame(data)


@router.post("/verify", response_model=VerificationOut, status_code=201,
             dependencies=[Depends(user_rate_limit("rate_limit_verify_per_minute"))])
def verify(user: Verifier, db: DbSession, request: Request, image: UploadFile = File(...), consent: bool = Form(...)) -> VerificationOut:
    """Analyses one captured frame and stores the result metadata (not the image)."""
    svc.require_consent(consent)
    return svc.verify_image(db, user, client_ip(request), image, SessionMode.LIVE)


_nonces = cflow.NonceStore()  # in-process; use a shared store if you run several backend workers


@router.post("/challenge", dependencies=[Depends(user_rate_limit("rate_limit_challenge_per_minute"))])
def new_challenge(user: Verifier) -> dict:
    """Issues a signed, single-use, short-lived challenge. The UI shows `steps`; the required sequence lives in the
    signed token, so the client cannot choose an easier one."""
    token, view = cflow.issue(get_settings().jwt_secret, str(user.id), ttl=get_settings().challenge_ttl_seconds)
    return {"token": token, **view}


@router.post("/challenge/verify", status_code=201, dependencies=[Depends(user_rate_limit("rate_limit_challenge_per_minute"))])
def verify_challenge(user: Verifier, db: DbSession, request: Request, token: str = Form(...), consent: bool = Form(...),
                     video: UploadFile = File(...)) -> dict:
    """Judges the recording with the backend's own detector. A pass alone is supporting evidence, never REAL; with an
    active model, REAL needs both a model REAL score and a passed challenge, and a model FAKE score gives FAKE."""
    svc.require_consent(consent)
    s = get_settings()
    try:
        payload = cflow.open_token(s.jwt_secret, token, str(user.id), _nonces)
    except cflow.TokenError as e:
        raise AppError(str(e), 400) from None
    detector = get_detector()
    if not detector.has_landmarks:
        raise AppError("The landmark model is not installed on the server (run scripts/fetch_models.py), "
                       "so challenges cannot be evaluated.", 503)
    data = media.read_limited(video, s.max_video_mb * (1 << 20))
    sniffed = media.validate("video", video.filename, data)
    try:
        with media.temp_media(data, ".mp4" if sniffed == "mp4" else ".webm") as path:
            sampler = inference.FrameSampler() if liveness.availability(db).available else None
            obs, info = challenge_video.observe(path, detector, cflow.public_view(payload)["max_recording_seconds"],
                                                on_face=sampler.add if sampler else None)
    except challenge_video.VideoError as e:
        raise AppError(str(e), 422) from None
    result = cflow.evaluate(payload, obs)
    out = svc.record_challenge_result(db, user, client_ip(request), info=info, result=result, sampler=sampler)
    assessment = cflow.describe(face_detected=info["face_detected"], quality_passed=None, challenge_outcome=result["outcome"],
                                model_status=out.status.value if out.score else None)
    return {"verification_id": str(out.id), "status": out.status.value, "assessment": assessment,
            "outcome": result["outcome"], "progress": result["progress"], "note": result["note"],
            "can_retry": result["outcome"] != "PASSED", "retry_requires_new_challenge": True}
