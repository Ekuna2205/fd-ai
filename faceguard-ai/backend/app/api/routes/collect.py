"""Public data collection (like collect.ekyc.mn): a participant opens a dataset's collection link WITHOUT an account,
chooses "real" (their own live face) or "fake" (a presentation attack: photo, screen, replay), consents, and records a
few seconds of video. The server keeps up to COLLECT_FRAMES single-face frames as labelled dataset images.

* The link token is the only credential. It can add images to that one dataset and read its name; nothing else.
* Every participant gets a random pseudonymous id from their browser; it becomes the image identity, so the training
  split can keep each person in only one of train/val/test.
* The video itself is never stored: it is decoded from a securely deleted temp file and discarded.
"""
from __future__ import annotations

import re
import uuid
from typing import Literal

import cv2
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, client_ip
from app.api.routes.datasets import _mapped, _validator, get_store
from app.core.config import get_settings
from app.core.errors import AppError, NotFound
from app.core.i18n import tr
from app.core.rate_limit import limiter
from app.models.enums import RoleName
from app.models.user import Role, User
from app.services import audit_service
from app.services import dataset_store as store_mod
from app.services.face import media
from app.services.face import video as video_mod
from app.services import challenge as ch
from app.services import inference
from app.services.face import quality as qual
from app.services.face.detector import get_detector

router = APIRouter(prefix="/collect", tags=["collect"])
PARTICIPANT = re.compile(r"^[a-f0-9]{12,32}$")
ATTACKS = ("PRINTED_PHOTO", "PHONE_SCREEN", "COMPUTER_SCREEN", "REPLAY_VIDEO", "MASK", "OTHER")


def _limit(setting: str):
    def dependency(request: Request) -> None:
        limit = getattr(get_settings(), setting)
        if limit <= 0:
            return
        host = request.client.host if request.client else "unknown"
        wait = limiter.check(f"{setting}:{host}", limit)
        if wait is not None:
            raise AppError("Too many requests. Slow down and try again shortly.", 429,
                           headers={"Retry-After": str(max(1, int(wait) + 1))})
    return dependency


ip_limit = _limit("rate_limit_collect_per_minute")
frame_limit = _limit("rate_limit_collect_frame_per_minute")


def _dataset(token: str) -> dict:
    meta = get_store().find_by_token(token)
    if meta is None:
        raise NotFound("This collection link is not valid or has been turned off.")
    return meta


DEFAULT_NAME = "Үндсэн цуглуулга"  # "Main collection"


@router.get("/default", dependencies=[Depends(ip_limit)])
def default_link() -> dict:
    """Token of the site's main camera page (the most recently opened collection link). No account needed."""
    meta = get_store().latest_collection()
    if meta is None:
        raise NotFound("No collection link is open yet.")
    return {"token": meta["collect"]["token"], "name": meta["name"]}


@router.post("/default", dependencies=[Depends(ip_limit)])
def ensure_default_link(user: CurrentUser, db: DbSession, request: Request) -> dict:
    """Signed-in users (any role) open the camera page; if no collection link exists yet, one is created in a dataset
    owned by the first administrator, so the camera works out of the box."""
    meta = get_store().latest_collection()
    if meta is None:
        admin = db.scalar(select(User).join(User.role).where(Role.name == RoleName.ADMINISTRATOR.value)
                          .order_by(User.created_at).limit(1))
        owner = admin or user
        with _mapped():
            store = get_store()
            mine = [d for d in store.list(str(owner.id)) if d["name"] == DEFAULT_NAME]
            ds = mine[0] if mine else store.create(str(owner.id), DEFAULT_NAME, "Камераар цуглуулсан бичлэгүүд")
            store.set_collection(str(owner.id), ds["id"], True)
        audit_service.record(db, "dataset.collect_link", user_id=user.id, ip=client_ip(request), entity_type="dataset",
                             entity_id=ds["id"], details={"enabled": True, "auto_default": True})
        db.commit()
        meta = get_store().latest_collection()
    return {"token": meta["collect"]["token"], "name": meta["name"]}


@router.get("/{token}", dependencies=[Depends(ip_limit)])
def info(token: str) -> dict:
    meta = _dataset(token)
    s = get_settings()
    return {"name": meta["name"], "description": meta["description"], "step_seconds": s.collect_step_seconds,
            "max_video_mb": s.max_video_mb, "attack_types": list(ATTACKS)}


def _spread(items: list, n: int) -> list:
    if len(items) <= n:
        return items
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


@router.post("/{token}/frame", dependencies=[Depends(frame_limit)])
def frame(token: str, image: UploadFile = File(...)) -> dict:
    """Live guidance for the camera steps (about 4 frames per second): where the face is and how the head is turned.
    Nothing is stored. yaw: -1..1 in raw (unmirrored) camera coordinates; the user's LEFT is positive."""
    _dataset(token)
    data = media.read_limited(image, 2 << 20)
    media.validate("image", image.filename, data)
    bgr = media.decode_image(data)
    det = get_detector().detect(bgr)
    out: dict = {"face_count": len(det.faces), "box": None, "yaw": None, "ear": None, "quality_ready": None}
    if len(det.faces) == 1:
        f = det.faces[0]
        out["box"] = {"x": round(f.x, 4), "y": round(f.y, 4), "w": round(f.w, 4), "h": round(f.h, 4)}
        if f.landmarks:
            ear, yaw = ch.measure(f.landmarks)
            out["yaw"], out["ear"] = round(yaw, 3), round(ear, 3)
        out["quality_ready"] = qual.assess(bgr, f).ready
    return out


@router.post("/{token}", status_code=201, dependencies=[Depends(ip_limit)])
def submit(token: str, request: Request, db: DbSession, video: UploadFile = File(...),
           label: Literal["REAL", "FAKE"] = Form(...), consent: bool = Form(...), participant: str = Form(...),
           attack_type: str | None = Form(None)) -> dict:
    if not consent:
        raise AppError("Consent is required before any biometric analysis.", 400)
    if not PARTICIPANT.match(participant or ""):
        raise AppError("Invalid participant id.", 422)
    if label == "FAKE" and attack_type not in ATTACKS:
        raise AppError("Choose how you tried to deceive the camera.", 422)
    meta = _dataset(token)
    s = get_settings()
    data = media.read_limited(video, s.max_video_mb * (1 << 20))
    sniffed = media.validate("video", video.filename, data)

    frames: list = []
    with media.temp_media(data, ".mp4" if sniffed == "mp4" else ".webm") as path:
        summary = video_mod.analyze(path, get_detector(), on_face=lambda frame, face, ok: frames.append(frame))
    if not frames:
        raise AppError("No single face was visible in the recording. Keep one face inside the frame and try again.", 422)

    kept = _spread(frames, s.collect_frames)
    score = None
    active, _ = inference.load_active(db)
    if active is not None:  # optional: show the participant what the active model thinks (like collect.ekyc.mn)
        faces = []
        for fr in kept:
            d = get_detector().detect(fr)
            if len(d.faces) == 1:
                faces.append((fr, d.faces[0]))
        if faces:
            p = sum(active.model.predict(faces)) / len(faces)
            v = inference.decide(p, active.threshold)
            score = {"model": active.label, "bona_fide_score": round(p, 4), "status": v.status, "threshold": active.threshold}

    identity = f"p-{participant[:16]}"
    group = "LIVE" if label == "REAL" else attack_type
    added = duplicates = 0
    for frame in kept:
        ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not ok:
            continue
        try:
            with _mapped():
                get_store().add_image(meta["owner"], meta["id"], f"collect-{uuid.uuid4().hex[:8]}.jpg", jpg.tobytes(),
                                      _validator, label=label, identity=identity, group=group, source="collect")
            added += 1
        except store_mod.DatasetConflict:
            duplicates += 1
        except AppError as e:
            if e.status_code == 409:
                duplicates += 1
                continue
            raise
    audit_service.record(db, "collect.submit", ip=client_ip(request), entity_type="dataset", entity_id=meta["id"],
                         details={"label": label, "group": group, "added": added, "frames_analyzed": summary.frames_analyzed})
    db.commit()
    return {"added": added, "skipped": duplicates, "frames_analyzed": summary.frames_analyzed, "label": label,
            "group": group, "score": score, "message": tr("Thank you! Your recording was added.")}
