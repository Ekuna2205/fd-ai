import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Query, Request, Response

from app.api.deps import CurrentUser, DbSession, client_ip
from app.models.enums import SessionMode, VerificationStatus
from app.schemas.face import VerificationOut
from app.schemas.history import HistoryPage
from app.services import history_service, verification_service as svc

router = APIRouter(prefix="/verifications", tags=["verifications"])
Sort = Literal["created_at", "status", "processing_ms", "confidence"]
Order = Literal["asc", "desc"]


@router.get("", response_model=HistoryPage)
def list_verifications(
    db: DbSession, user: CurrentUser,
    q: str | None = Query(None, max_length=64, description="ID prefix or text in the explanation"),
    status: VerificationStatus | None = None, mode: SessionMode | None = None,
    date_from: date | None = None, date_to: date | None = None,
    sort: Sort = "created_at", order: Order = "desc",
    page: int = Query(1, ge=1, le=100_000), page_size: int = Query(20, ge=1, le=100),
) -> HistoryPage:
    """The caller's own verifications only. There is no way to list another user's records."""
    return history_service.list_history(db, user, sort=sort, order=order, page=page, page_size=page_size, q=q,
                                        status=status, mode=mode, date_from=date_from, date_to=date_to)


@router.get("/export")
def export_verifications(
    request: Request, db: DbSession, user: CurrentUser, q: str | None = Query(None, max_length=64),
    status: VerificationStatus | None = None, mode: SessionMode | None = None,
    date_from: date | None = None, date_to: date | None = None, sort: Sort = "created_at", order: Order = "desc",
) -> Response:
    body, n = history_service.export_csv(db, user, client_ip(request), sort=sort, order=order, q=q, status=status,
                                         mode=mode, date_from=date_from, date_to=date_to)
    return Response(body, media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": 'attachment; filename="verifications.csv"', "Cache-Control": "private, no-store",
        "X-Exported-Rows": str(n)})


@router.get("/{verification_id}", response_model=VerificationOut)
def get_verification(verification_id: uuid.UUID, request: Request, db: DbSession, user: CurrentUser) -> VerificationOut:
    """Only the user who created the verification can read it (404 otherwise)."""
    return svc.get_verification(db, user, client_ip(request), verification_id)


@router.delete("/{verification_id}", status_code=204)
def delete_verification(verification_id: uuid.UUID, request: Request, db: DbSession, user: CurrentUser) -> Response:
    """Owner-only secure deletion of one verification record."""
    history_service.delete_one(db, user, client_ip(request), verification_id)
    return Response(status_code=204)
