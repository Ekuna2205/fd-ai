import csv
import io
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import VerificationStatus as S
from app.models.verification import VerificationResult as R
from app.repositories import dashboard_repository as repo
from app.schemas.dashboard import SpoofCategory, Totals
from app.schemas.history import ReportSummary, SeriesPoint, StatusCount
from app.services.history_service import csv_safe

ROW_CAP = 50_000
Period = Literal["day", "week", "month"]


def _bucket(d: date, period: Period) -> date:
    if period == "day":
        return d
    if period == "week":
        return d - timedelta(days=d.weekday())  # Monday
    return d.replace(day=1)


def _next(d: date, period: Period) -> date:
    if period == "day":
        return d + timedelta(days=1)
    if period == "week":
        return d + timedelta(days=7)
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def build(db: Session, user_id, *, scope: str, period: Period, days: int) -> ReportSummary:
    """`user_id=None` is the explicit administrator aggregate (counts only, never individual records)."""
    today = datetime.now(UTC).date()
    start = today - timedelta(days=days - 1)
    stmt = repo.owned_by(select(R.created_at, R.status, R.spoof_type, R.processing_ms).select_from(R), user_id)
    rows = db.execute(stmt.where(R.created_at >= datetime.combine(start, datetime.min.time(), tzinfo=UTC),
                                 R.status != S.PROCESSING).limit(ROW_CAP)).all()

    per_bucket: dict[date, Counter] = defaultdict(Counter)
    statuses: Counter = Counter()
    spoofs: Counter = Counter()
    times: list[int] = []
    for created, status, spoof, ms in rows:
        day = created.date() if isinstance(created, datetime) else created
        key = "failed" if status in repo.FAILED else status.value.lower()
        per_bucket[_bucket(day, period)][key] += 1
        statuses[status] += 1
        if status == S.FAKE and spoof is not None:
            spoofs[spoof.value] += 1
        if ms is not None:
            times.append(ms)

    series: list[SeriesPoint] = []
    if rows:  # an empty window returns [] so the UI shows an empty state, not a flat zero chart
        b, last = _bucket(start, period), _bucket(today, period)
        while b <= last:
            c = per_bucket.get(b, Counter())
            series.append(SeriesPoint(bucket=b, real=c["real"], fake=c["fake"], uncertain=c["uncertain"], failed=c["failed"]))
            b = _next(b, period)

    attempts = sum(statuses.values())
    real = statuses[S.REAL]
    totals = Totals(attempts=attempts, real=real, fake=statuses[S.FAKE], uncertain=statuses[S.UNCERTAIN],
                    failed=sum(statuses[s] for s in repo.FAILED), success_rate=(real / attempts) if attempts else None)
    return ReportSummary(
        scope="all" if user_id is None else "own", period=period, days=days, totals=totals, series=series,
        status_distribution=[StatusCount(status=s, count=n) for s, n in sorted(statuses.items(), key=lambda kv: -kv[1])],
        spoof_categories=[SpoofCategory(category=c, count=n) for c, n in spoofs.most_common()],
        avg_processing_ms=round(sum(times) / len(times), 1) if times else None)


def to_csv(rep: ReportSummary) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([f"FaceGuard AI report: scope={rep.scope}, period={rep.period}, last {rep.days} days"])
    w.writerow(["period_start", "real", "fake", "uncertain", "failed"])
    for p in rep.series:
        w.writerow([p.bucket.isoformat(), p.real, p.fake, p.uncertain, p.failed])
    w.writerow([])
    w.writerow(["total_attempts", rep.totals.attempts]); w.writerow(["real", rep.totals.real]); w.writerow(["fake", rep.totals.fake])
    w.writerow(["uncertain", rep.totals.uncertain]); w.writerow(["failed", rep.totals.failed])
    w.writerow(["success_rate", "" if rep.totals.success_rate is None else round(rep.totals.success_rate, 4)])
    w.writerow([]); w.writerow(["spoof_category", "count"])
    for c in rep.spoof_categories:
        w.writerow([csv_safe(c.category), c.count])
    return out.getvalue()
