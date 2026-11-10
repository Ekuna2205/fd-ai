"""Test setup. Uses TEST_DATABASE_URL (PostgreSQL recommended) or falls back to a temporary SQLite file."""
import os
import secrets
import tempfile
from datetime import UTC, datetime
from pathlib import Path

_default_db = Path(tempfile.mkdtemp(prefix="faceguard-test-")) / "test.db"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_default_db}"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="faceguard-test-data-")  # datasets/models never land in the source tree
os.environ["JWT_SECRET"] = secrets.token_hex(32)  # random per run; never a real secret
os.environ["RATE_LIMIT_AUTH_PER_MINUTE"] = "0"
os.environ["REGISTRATION_ENABLED"] = "true"

from sqlalchemy.engine import make_url  # noqa: E402

_url = make_url(os.environ["DATABASE_URL"])
if _url.get_backend_name() == "postgresql" and "test" not in (_url.database or ""):
    # The suite drops every table; never let it near a real database.
    raise SystemExit(f"Refusing to run tests against database '{_url.database}'. Use a database whose name contains 'test'.")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.rate_limit import limiter  # noqa: E402
from app.database.base import Base  # noqa: E402
from app.database.session import get_engine, get_sessionmaker  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.ai import AIModel, ModelEvaluation  # noqa: E402
from app.models.enums import SessionMode, SpoofType, VerificationStatus  # noqa: E402
from app.models.verification import VerificationResult, VerificationSession  # noqa: E402

PASSWORD = "Correct-horse-9"
MODELS_STATE: dict = {"ok": True, "why": ""}
# Modules that run real face detection and therefore need the landmark model file.
NEEDS_MODELS = {"test_face_api.py", "test_face_detection.py", "test_video.py"}


@pytest.fixture(scope="session", autouse=True)
def _models():
    """The landmark model is not in git. Download it (checksum-verified) on the first run.

    Offline: tests that need the model are SKIPPED (never reported as passed); everything else still runs.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("fetch_models", Path(__file__).parents[1] / "scripts" / "fetch_models.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        MODELS_STATE["ok"] = mod.main() == 0
    except Exception as exc:  # no network, DNS failure, disk error...
        MODELS_STATE["ok"] = False
        MODELS_STATE["why"] = f"{type(exc).__name__}: {exc}"


@pytest.fixture(autouse=True)
def _skip_without_models(request):
    if Path(str(request.node.fspath)).name in NEEDS_MODELS and not MODELS_STATE["ok"]:
        pytest.skip("Landmark model unavailable (offline). Run `python scripts/fetch_models.py` with network access, "
                    f"then re-run. {MODELS_STATE['why']}")


@pytest.fixture(scope="session", autouse=True)
def _schema():
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _clean():
    limiter.reset()
    yield
    with get_engine().begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def client():
    with TestClient(create_app()) as c:  # entering the context runs the startup role seeding
        yield c


@pytest.fixture
def db():
    with get_sessionmaker()() as session:
        yield session


def register(client, email="admin@example.com", name="Ada Admin", password=PASSWORD):
    return client.post("/api/auth/register", json={"email": email, "full_name": name, "password": password})


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin(client):
    """First registered account = administrator."""
    body = register(client).json()
    return {"token": body["access_token"], "user": body["user"], "h": headers(body["access_token"])}


@pytest.fixture
def viewer(client, admin):
    body = register(client, "viewer@example.com", "Vic Viewer").json()
    return {"token": body["access_token"], "user": body["user"], "h": headers(body["access_token"])}


def add_result(db, status, spoof=None, confidence=None, created=None, user_id=None):
    """Inserts a verification result owned by `user_id` (str or UUID). No owner = an orphaned session."""
    import uuid as _uuid
    if isinstance(user_id, str):
        user_id = _uuid.UUID(user_id)
    s = VerificationSession(mode=SessionMode.LIVE, consent_given=True, user_id=user_id)
    r = VerificationResult(session=s, status=VerificationStatus(status),
                           spoof_type=SpoofType(spoof) if spoof else None, confidence=confidence,
                           created_at=created or datetime.now(UTC))
    db.add_all([s, r])
    db.commit()
    return r


def add_model(db, *, active=True, trained=False, name="baseline-cnn", version="0.0.1"):
    m = AIModel(name=name, version=version, architecture="SmallCNN", is_trained=trained, is_active=active)
    db.add(m)
    db.commit()
    return m


def add_evaluation(db, model, **metrics):
    e = ModelEvaluation(model_id=model.id, evaluated_at=datetime.now(UTC), **metrics)
    db.add(e)
    db.commit()
    return e


# ---------- media helpers (public-domain NASA portrait from scikit-image; no private biometric data) ----------
import io  # noqa: E402

import cv2  # noqa: E402
import numpy as np  # noqa: E402


@pytest.fixture
def operator(client, admin):
    body = register(client, "operator@example.com", "Olive Operator").json()
    client.patch(f"/api/users/{body['user']['id']}", json={"role": "operator"}, headers=admin["h"])
    return {"token": body["access_token"], "user": body["user"], "h": headers(body["access_token"])}


def portrait() -> np.ndarray:
    skimage_data = pytest.importorskip("skimage.data")
    return cv2.cvtColor(skimage_data.astronaut(), cv2.COLOR_RGB2BGR)


def jpeg(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    assert ok
    return buf.tobytes()


def png(img: np.ndarray) -> bytes:
    return cv2.imencode(".png", img)[1].tobytes()


def noise(h=480, w=640) -> np.ndarray:
    return np.random.default_rng(1).integers(0, 255, (h, w, 3), dtype=np.uint8)


def write_video(path, frames, fourcc="mp4v", fps=10):
    h, w = frames[0].shape[:2]
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*fourcc), fps, (w, h))
    for f in frames:
        out.write(f)
    out.release()
    return path


def files(name: str, data: bytes, mime: str = "application/octet-stream"):
    return {"file": (name, data, mime)}


def post_frame(client, h, data: bytes, url="/api/face/detect", consent="true", name="frame.jpg"):
    return client.post(url, headers=h, files={"image": (name, data, "image/jpeg")}, data={"consent": consent})
