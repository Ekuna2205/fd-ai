"""Run the retention purge now (schedule it daily with cron / Windows Task Scheduler).

    python scripts/purge_retention.py            # uses RETENTION_DAYS
    python scripts/purge_retention.py --days 30  # override
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database.session import get_sessionmaker  # noqa: E402
from app.services import retention_service  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--days", type=int)
args = ap.parse_args()
with get_sessionmaker()() as db:
    print(retention_service.purge(db, args.days))
