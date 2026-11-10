import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

from app.database.base import Base
from app.database.session import get_engine
from app.models.ai import Dataset, DatasetSample
from app.models.enums import DatasetSource, SampleLabel
from app.models.verification import VerificationResult, VerificationSession
from tests.conftest import add_model, add_result

EXPECTED = {"users", "roles", "verification_sessions", "verification_results", "verification_challenges",
            "uploaded_files", "datasets", "dataset_samples", "ai_models", "model_evaluations", "audit_logs",
            "system_settings", "revoked_tokens", "refresh_tokens", "password_reset_tokens"}


def test_all_required_tables_exist():
    assert EXPECTED <= set(inspect(get_engine()).get_table_names()) and EXPECTED == set(Base.metadata.tables)


def test_only_one_model_can_be_active(db):
    add_model(db, active=True, name="a")
    with pytest.raises(IntegrityError):
        add_model(db, active=True, name="b")
    db.rollback()
    add_model(db, active=False, name="c")  # any number of inactive models is fine
    add_model(db, active=False, name="d")


def test_model_name_version_is_unique(db):
    add_model(db, active=False, name="m", version="1")
    with pytest.raises(IntegrityError):
        add_model(db, active=False, name="m", version="1")


def test_deleting_a_session_removes_its_results(db):
    r = add_result(db, "REAL")
    db.delete(db.get(VerificationSession, r.session_id))
    db.commit()
    assert db.scalar(select(func.count()).select_from(VerificationResult)) == 0


def test_dataset_sample_external_id_is_unique_per_dataset(db):
    ds = Dataset(name="demo", source=DatasetSource.CSV)
    db.add(ds)
    db.flush()
    db.add(DatasetSample(dataset_id=ds.id, external_id="7", uri="a.jpg", label=SampleLabel.REAL))
    db.commit()
    db.add(DatasetSample(dataset_id=ds.id, external_id="7", uri="b.jpg", label=SampleLabel.UNKNOWN))
    with pytest.raises(IntegrityError):
        db.commit()
