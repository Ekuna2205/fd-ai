from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.api.deps import DbSession, client_ip
from app.api.routes.face import Verifier
from app.core.rate_limit import user_rate_limit
from app.models.enums import SessionMode
from app.schemas.face import VerificationOut
from app.services import verification_service as svc

router = APIRouter(prefix="/uploads", tags=["uploads"], dependencies=[Depends(user_rate_limit("rate_limit_verify_per_minute"))])


@router.post("/image", response_model=VerificationOut, status_code=201)
def upload_image(user: Verifier, db: DbSession, request: Request, file: UploadFile = File(...), consent: bool = Form(...)) -> VerificationOut:
    svc.require_consent(consent)
    return svc.verify_image(db, user, client_ip(request), file, SessionMode.UPLOAD_IMAGE)


@router.post("/video", response_model=VerificationOut, status_code=201)
def upload_video(user: Verifier, db: DbSession, request: Request, file: UploadFile = File(...), consent: bool = Form(...)) -> VerificationOut:
    svc.require_consent(consent)
    return svc.verify_video(db, user, client_ip(request), file)
