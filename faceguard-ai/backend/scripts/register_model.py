"""Registers a finished training run in the model registry (database) so it appears on the Models page.

    python scripts/register_model.py --run-dir ../ai/runs/exp1 --name smallcnn --version 1.0.0

What it does:  copies model.onnx into DATA_DIR/models, stores the run's MEASURED test metrics as an evaluation.
The same logic backs the "Register a model" upload form on the Models page (app/services/model_service.py).
What it never does:  activate the model, invent a metric, or mark a model production-ready. Activation is a
separate step (Models page or POST /api/models/{id}/activate) and is refused unless the evidence is sufficient.
"""
import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.errors import AppError  # noqa: E402
from app.database.session import get_sessionmaker  # noqa: E402
from app.models.ai import AIModel  # noqa: E402
from app.services import model_service  # noqa: E402

class RegisterError(Exception):
    """A problem the operator can fix. Raised before anything is written."""


def _json(path: Path) -> dict:
    try:
        return model_service.parse_json(path.read_bytes(), path.name)
    except FileNotFoundError:
        raise RegisterError(f"Missing {path.name} in the run folder. Was the run completed?") from None
    except model_service.RegistrationError as e:
        raise RegisterError(e.detail) from None


def validate_onnx(path: Path, preprocessing: dict | None = None) -> str:
    """Loads the file exactly as the API's inference runtime will. Returns a note for the operator."""
    try:
        return model_service.validate_onnx(path, preprocessing)
    except model_service.RegistrationError as e:
        raise RegisterError(e.detail) from None


def register(run_dir: Path, name: str, version: str, *, architecture: str = "SmallCNN", description: str | None = None,
             data_dir: Path | None = None, crop: str = "full", face_margin: float = 0.4) -> tuple[AIModel, str, list[str]]:
    """Returns (model, validation note, activation blockers). Everything is checked before the first write."""
    try:
        model_service.check_names(name, version)
    except model_service.RegistrationError as e:
        raise RegisterError(e.detail.replace("The name", "--name").replace("The version", "--version")) from None
    run_dir = Path(run_dir)
    onnx = run_dir / "model.onnx"
    if not onnx.is_file():
        raise RegisterError(f"{onnx} not found. Export first: python -m faceguard_ai.export best.pt model.onnx")
    if (run_dir / "model.onnx.data").exists():
        raise RegisterError("model.onnx.data exists: the ONNX file is not self-contained. Re-export with the current exporter.")
    metrics, split = _json(run_dir / "test_metrics.json"), _json(run_dir / "split_report.json")
    prep = {"crop": crop, "face_margin": face_margin}
    note = validate_onnx(onnx, prep)

    from app.core.config import get_settings
    if data_dir is not None:
        get_settings().data_dir = str(data_dir)
    trained_at = datetime.fromtimestamp((run_dir / "test_metrics.json").stat().st_mtime, UTC)
    with get_sessionmaker()() as db:
        try:
            model = model_service.register_model(
                db, onnx_file=onnx, metrics=metrics, split=split, name=name, version=version, architecture=architecture,
                description=description, preprocessing=prep, trained_at=trained_at, source=run_dir.name)
        except AppError as e:
            raise RegisterError(e.detail) from None
        return model, note, model_service.blockers(model)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True, type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--architecture", default="SmallCNN")
    ap.add_argument("--description")
    ap.add_argument("--crop", choices=("full", "face"), default="full",
                    help="Input the model was trained on: full images (default) or face crops (dataset export with crop=face)")
    ap.add_argument("--face-margin", type=float, default=0.4, help="Face crop enlargement used in training (crop=face)")
    a = ap.parse_args()
    try:
        model, note, blockers = register(a.run_dir, a.name, a.version, architecture=a.architecture, description=a.description,
                                         crop=a.crop, face_margin=a.face_margin)
    except RegisterError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"Registered {model.name} v{model.version} (id {model.id}). ONNX {note}")
    if blockers:
        print("It CANNOT be activated yet:")
        for b in blockers:
            print(f"  - {b}")
    else:
        print("It meets the activation requirements. Activate it on the Models page if you accept the evidence.")
    print("Nothing was activated automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
