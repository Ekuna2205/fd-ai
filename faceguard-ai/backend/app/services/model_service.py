"""Model registry rules. A model can only be activated when there is real evidence for it."""
import uuid
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.i18n import tr_list
from app.core.errors import Conflict, NotFound
from app.models.ai import AIModel, ModelEvaluation
from app.models.user import User
from app.schemas.history import EvaluationOut, ModelDetail, ModelOut
from app.services import audit_service

PAD_METRICS = ("apcer", "bpcer", "acer")


def model_dir() -> Path:
    return (Path(get_settings().data_dir) / "models").resolve()


def _onnx_ok(path: str | None) -> bool:
    """The ONNX file must exist INSIDE the model directory (blocks path tricks like ../../etc/passwd)."""
    if not path:
        return False
    p = Path(path)
    p = (model_dir() / p).resolve() if not p.is_absolute() else p.resolve()
    return p.is_file() and model_dir() in p.parents


def _eval_out(e: ModelEvaluation) -> EvaluationOut:
    report = e.report or {}
    return EvaluationOut(id=e.id, evaluated_at=e.evaluated_at, sample_count=e.sample_count, threshold=e.threshold,
                         accuracy=e.accuracy, precision=e.precision, recall=e.recall, f1=e.f1, roc_auc=e.roc_auc,
                         apcer=e.apcer, bpcer=e.bpcer, acer=e.acer, identity_disjoint=report.get("identity_disjoint"))


def latest_evaluation(m: AIModel) -> ModelEvaluation | None:
    return max(m.evaluations, key=lambda e: e.evaluated_at, default=None)


def blockers(m: AIModel) -> list[str]:
    """Reasons activation is refused. Empty list = allowed. Never relaxed for convenience."""
    out: list[str] = []
    if not m.is_trained:
        out.append("The model is not trained (baseline weights are never production-ready).")
    if not _onnx_ok(m.onnx_path):
        out.append("No ONNX file was found in the model directory.")
    ev = latest_evaluation(m)
    if ev is None:
        out.append("The model has not been evaluated.")
        return out
    if any(getattr(ev, k) is None for k in PAD_METRICS):
        out.append("The latest evaluation is missing APCER/BPCER/ACER.")
    if (ev.sample_count or 0) < get_settings().min_eval_samples:
        out.append(f"The evaluation used {ev.sample_count or 0} test samples; at least {get_settings().min_eval_samples} are required.")
    if (ev.report or {}).get("identity_disjoint") is not True:
        out.append("The evaluation was not run on an identity-disjoint test split.")
    return out


def to_out(m: AIModel) -> ModelOut:
    ev = latest_evaluation(m)
    return ModelOut(id=m.id, name=m.name, version=m.version, architecture=m.architecture, description=m.description,
                    is_trained=m.is_trained, is_active=m.is_active, trained_at=m.trained_at, created_at=m.created_at,
                    has_onnx=_onnx_ok(m.onnx_path),
                    input_crop=(m.preprocessing or {}).get("crop", "full"), latest_evaluation=_eval_out(ev) if ev else None, blockers=tr_list(blockers(m)))


def list_models(db: Session) -> list[ModelOut]:
    return [to_out(m) for m in db.scalars(select(AIModel).order_by(AIModel.created_at.desc()))]


def _get(db: Session, model_id: uuid.UUID) -> AIModel:
    m = db.get(AIModel, model_id)
    if m is None:
        raise NotFound("Model not found.")
    return m


def detail(db: Session, model_id: uuid.UUID) -> ModelDetail:
    m = _get(db, model_id)
    evs = sorted(m.evaluations, key=lambda e: e.evaluated_at, reverse=True)
    return ModelDetail(**to_out(m).model_dump(), evaluations=[_eval_out(e) for e in evs])


def activate(db: Session, user: User, ip: str | None, model_id: uuid.UUID) -> ModelOut:
    m = _get(db, model_id)
    problems = blockers(m)
    if problems:
        audit_service.record(db, "model.activate_refused", user_id=user.id, ip=ip, entity_type="model", entity_id=str(m.id),
                             details={"blockers": problems})
        db.commit()
        raise Conflict("This model cannot be activated: " + " ".join(problems))
    db.execute(update(AIModel).where(AIModel.is_active.is_(True), AIModel.id != m.id).values(is_active=False)
               .execution_options(synchronize_session="fetch"))
    m.is_active = True
    audit_service.record(db, "model.activate", user_id=user.id, ip=ip, entity_type="model", entity_id=str(m.id))
    db.commit()
    return to_out(m)


def deactivate(db: Session, user: User, ip: str | None, model_id: uuid.UUID) -> ModelOut:
    m = _get(db, model_id)
    if m.is_active:
        m.is_active = False
        audit_service.record(db, "model.deactivate", user_id=user.id, ip=ip, entity_type="model", entity_id=str(m.id))
        db.commit()
    return to_out(m)


# ---- registration (shared by scripts/register_model.py and the upload form on the Models page) ------------------------
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402
from datetime import UTC, datetime  # noqa: E402

from app.core.errors import AppError  # noqa: E402

SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ONNX_MAGIC_MAX_JSON = 1 << 20  # metrics/split JSON files are small; anything bigger is not what we expect


class RegistrationError(AppError):
    """A problem the operator can fix. Raised before anything is written."""
    status_code = 400


def check_names(name: str, version: str) -> None:
    for label, value in (("name", name), ("version", version)):
        if not SAFE_NAME.match(value or ""):
            raise RegistrationError(f"The {label} may contain only letters, digits, '.', '_' and '-' (max 64).")


def parse_json(data: bytes, filename: str) -> dict:
    if len(data) > ONNX_MAGIC_MAX_JSON:
        raise RegistrationError(f"{filename} is too large to be a metrics file.")
    try:
        out = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise RegistrationError(f"{filename} is not valid JSON: {e}") from None
    if not isinstance(out, dict):
        raise RegistrationError(f"{filename} must contain a JSON object.")
    return out


def validate_onnx(path: Path, preprocessing: dict | None = None) -> str:
    """Loads the file exactly as inference will. Returns a note; raises RegistrationError when it cannot be served."""
    from app.services import inference
    try:
        lm = inference.LivenessModel(path, preprocessing)
    except inference.ModelLoadError as e:
        if "onnxruntime is not installed" in str(e):
            return "NOT validated: onnxruntime is not installed (pip install onnxruntime to validate)."
        raise RegistrationError(str(e)) from None
    except ValueError as e:
        raise RegistrationError(str(e)) from None
    return f"validated with onnxruntime (input N,3,{lm.size},{lm.size}; output 2 logits)."


def _num(v, name: str, lo: float | None = 0.0, hi: float | None = 1.0) -> float | None:
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise RegistrationError(f"test_metrics.json: {name} must be a number.")
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        raise RegistrationError(f"test_metrics.json: {name}={v} is outside {lo}..{hi}.")
    return float(v)


def register_model(db: Session, *, onnx_file: Path, metrics: dict, split: dict, name: str, version: str,
                   architecture: str = "SmallCNN", description: str | None = None, preprocessing: dict | None = None,
                   trained_at: datetime | None = None, source: str | None = None, actor: User | None = None,
                   ip: str | None = None) -> AIModel:
    """Copies the ONNX file into the model directory and stores the run's MEASURED metrics. Never activates.
    The caller validates the ONNX file first (validate_onnx)."""
    from app.services import inference
    check_names(name, version)
    if architecture and len(architecture) > 120:
        raise RegistrationError("Architecture is too long (max 120 characters).")
    try:
        prep = inference.normalise_preprocessing(preprocessing)
    except ValueError as e:
        raise RegistrationError(str(e)) from None
    n = metrics.get("n")
    if n is not None and (isinstance(n, bool) or not isinstance(n, int) or n < 0):
        raise RegistrationError("test_metrics.json: n must be a non-negative integer.")
    values = {k: _num(metrics.get(k), k) for k in ("threshold", "accuracy", "precision", "recall", "f1", "roc_auc",
                                                    "apcer", "bpcer", "acer")}
    if db.scalar(select(AIModel).where(AIModel.name == name, AIModel.version == version)):
        raise Conflict(f"Model {name} v{version} is already registered. Use a new version.")
    target_dir = model_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{name}-{version}.onnx"
    if target.exists():
        raise Conflict(f"A model file named {target.name} already exists. Use a new version.")
    shutil.copyfile(onnx_file, target)
    when = trained_at or datetime.now(UTC)
    model = AIModel(name=name, version=version, architecture=architecture or "unknown", description=description or None,
                    is_trained=True, is_active=False, trained_at=when, onnx_path=target.name, preprocessing=prep,
                    created_by=actor.id if actor else None)
    model.evaluations.append(ModelEvaluation(
        evaluated_at=when, sample_count=n, **values,
        report={"identity_disjoint": bool(split.get("identity_disjoint")) and bool(metrics.get("identity_disjoint_split")),
                "n_bona_fide": metrics.get("n_bona_fide"), "n_attack": metrics.get("n_attack"),
                "split_counts": split.get("counts"), "confusion_matrix": metrics.get("confusion_matrix"),
                "source_run": source}))
    db.add(model)
    db.flush()
    audit_service.record(db, "model.register", user_id=actor.id if actor else None, ip=ip, entity_type="model",
                         entity_id=str(model.id), details={"name": name, "version": version, "crop": prep["crop"]})
    db.commit()
    return model


def register_upload(db: Session, user: User, ip: str | None, *, onnx_data: bytes, metrics_data: bytes,
                    split_data: bytes, name: str, version: str, architecture: str, description: str | None,
                    input_crop: str) -> ModelOut:
    """Upload form on the Models page: the three files a training run produces (model.onnx, test_metrics.json,
    split_report.json). Everything is validated before the model directory is touched."""
    check_names(name, version)
    metrics, split = parse_json(metrics_data, "test_metrics.json"), parse_json(split_data, "split_report.json")
    if not onnx_data:
        raise RegistrationError("The ONNX file is empty.")
    prep = {"crop": input_crop}
    fd, tmp = tempfile.mkstemp(suffix=".onnx", dir=get_settings().upload_temp_dir or None)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(onnx_data)
        validate_onnx(Path(tmp), prep)
        m = register_model(db, onnx_file=Path(tmp), metrics=metrics, split=split, name=name, version=version,
                           architecture=architecture, description=description, preprocessing=prep, source="upload",
                           actor=user, ip=ip)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return to_out(m)


def delete(db: Session, user: User, ip: str | None, model_id: uuid.UUID) -> None:
    """Removes an INACTIVE model, its evaluations and its ONNX file. Results it produced keep their model label."""
    m = _get(db, model_id)
    if m.is_active:
        raise Conflict("Deactivate the model before deleting it.")
    if m.onnx_path and _onnx_ok(m.onnx_path):
        (model_dir() / m.onnx_path).resolve().unlink(missing_ok=True)
    audit_service.record(db, "model.delete", user_id=user.id, ip=ip, entity_type="model", entity_id=str(m.id),
                         details={"name": m.name, "version": m.version})
    db.delete(m)
    db.commit()
