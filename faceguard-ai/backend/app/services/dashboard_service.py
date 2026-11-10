import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.enums import VerificationStatus as S
from app.repositories import dashboard_repository as repo
from app.schemas.dashboard import (ActiveModel, DailyPoint, DashboardOverview, RecentItem, SpoofCategory, Totals)

DAILY_WINDOW_DAYS = 14
RECENT_LIMIT = 10


def build_overview(db: Session, user_id: uuid.UUID | None) -> DashboardOverview:
    """`user_id` scopes every figure to one user. None = administrator aggregate over all users."""
    counts = repo.status_counts(db, user_id)
    attempts = sum(n for s, n in counts.items() if s != S.PROCESSING)
    real = counts.get(S.REAL, 0)
    totals = Totals(
        attempts=attempts,
        real=real,
        fake=counts.get(S.FAKE, 0),
        uncertain=counts.get(S.UNCERTAIN, 0),
        failed=sum(counts.get(s, 0) for s in repo.FAILED),
        success_rate=(real / attempts) if attempts else None,
    )

    start = repo.window_start(DAILY_WINDOW_DAYS)
    per_day = repo.daily_counts(db, start, user_id)
    daily: list[DailyPoint] = []
    if per_day:  # an empty window returns [] so the UI shows its empty state instead of a flat chart
        for i in range(DAILY_WINDOW_DAYS):
            d = (start + timedelta(days=i)).date()
            c = per_day.get(d, {})
            daily.append(DailyPoint(date=d, real=c.get(S.REAL, 0), fake=c.get(S.FAKE, 0), uncertain=c.get(S.UNCERTAIN, 0)))

    active = repo.active_model_with_latest_evaluation(db)
    active_model = None
    if active:
        model, ev = active
        active_model = ActiveModel(
            name=model.name, version=model.version, trained=model.is_trained,
            apcer=ev.apcer if ev else None, bpcer=ev.bpcer if ev else None, acer=ev.acer if ev else None,
            evaluated_at=ev.evaluated_at if ev else None,
        )

    return DashboardOverview(
        totals=totals,
        daily=daily,
        spoof_categories=[SpoofCategory(category=c, count=n) for c, n in repo.spoof_category_counts(db, user_id)],
        recent=[RecentItem(id=r.id, created_at=r.created_at, status=r.status,
                           spoof_type=r.spoof_type.value if r.spoof_type else None, confidence=r.confidence)
                for r in repo.recent_results(db, RECENT_LIMIT, user_id)],
        active_model=active_model,
    )
