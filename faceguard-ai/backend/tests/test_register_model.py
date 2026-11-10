"""The training-run -> registry bridge. Run folders here are hand-made JSON (no PyTorch needed)."""
import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models.ai import AIModel, ModelEvaluation

spec = importlib.util.spec_from_file_location("register_model", Path(__file__).parents[1] / "scripts" / "register_model.py")
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)


def make_run(tmp_path, n=500, disjoint=True, metrics_disjoint=True, sidecar=False, onnx=b"fake-onnx-bytes"):
    run = tmp_path / "run1"
    run.mkdir()
    (run / "model.onnx").write_bytes(onnx)
    if sidecar:
        (run / "model.onnx.data").write_bytes(b"w")
    (run / "test_metrics.json").write_text(json.dumps({
        "n": n, "n_bona_fide": n // 2, "n_attack": n // 2, "threshold": 0.55, "accuracy": 0.97, "precision": 0.96, "recall": 0.95,
        "f1": 0.955, "roc_auc": 0.99, "apcer": 0.04, "bpcer": 0.03, "acer": 0.035, "identity_disjoint_split": metrics_disjoint,
        "confusion_matrix": {"labels": ["attack", "bona_fide"], "matrix": [[240, 10], [8, 242]]}}))
    (run / "split_report.json").write_text(json.dumps({"counts": {"train": 3000, "val": 500, "test": n}, "identity_disjoint": disjoint, "warnings": []}))
    return run


@pytest.fixture(autouse=True)
def _stub_validation(request, monkeypatch):
    """Registration logic is tested with placeholder bytes; real ONNX validation has its own test below."""
    if "onnx_validation" not in request.node.name:
        monkeypatch.setattr(rm, "validate_onnx", lambda path, *_: "validated with onnxruntime (stubbed in this test).")


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "data_dir", str(tmp_path / "data"))
    return tmp_path / "data"


def test_registers_measured_metrics_and_copies_the_file(tmp_path, data_dir, db):
    model, note, blockers = rm.register(make_run(tmp_path), "smallcnn", "1.0.0")
    assert (data_dir / "models" / "smallcnn-1.0.0.onnx").read_bytes() == b"fake-onnx-bytes"
    m = db.scalar(select(AIModel).where(AIModel.name == "smallcnn"))
    assert m.is_trained and m.is_active is False and m.onnx_path == "smallcnn-1.0.0.onnx"
    e = db.scalar(select(ModelEvaluation).where(ModelEvaluation.model_id == m.id))
    assert (e.sample_count, e.apcer, e.bpcer, e.acer, e.roc_auc, e.threshold) == (500, 0.04, 0.03, 0.035, 0.99, 0.55)
    assert e.report["identity_disjoint"] is True and e.report["confusion_matrix"]["matrix"] == [[240, 10], [8, 242]]
    assert blockers == [] and "validated" in note


def test_never_activates_even_when_everything_is_sufficient(tmp_path, data_dir, db):
    rm.register(make_run(tmp_path), "m", "1")
    assert db.scalar(select(AIModel)).is_active is False


def test_small_test_sets_are_registered_but_blocked(tmp_path, data_dir):
    _, _, blockers = rm.register(make_run(tmp_path, n=12), "tiny", "1")
    assert any("at least" in b for b in blockers)


def test_leaky_split_is_registered_but_blocked(tmp_path, data_dir):
    _, _, blockers = rm.register(make_run(tmp_path, disjoint=False), "leaky", "1")
    assert any("identity-disjoint" in b for b in blockers)
    _, _, blockers = rm.register(make_run(tmp_path / "b", disjoint=True, metrics_disjoint=False) if (tmp_path / "b").mkdir() is None else None, "leaky", "2")
    assert any("identity-disjoint" in b for b in blockers)


def test_registered_model_can_then_be_activated_through_the_api(tmp_path, data_dir, client, admin):
    rm.register(make_run(tmp_path), "ok", "1")
    listed = client.get("/api/models", headers=admin["h"]).json()
    assert listed[0]["blockers"] == [] and listed[0]["has_onnx"] is True
    r = client.post(f"/api/models/{listed[0]['id']}/activate", headers=admin["h"])
    assert r.status_code == 200 and r.json()["is_active"] is True


@pytest.mark.parametrize("name,version", [("../evil", "1"), ("ok", "../1"), ("a/b", "1"), ("", "1"), ("x y", "1"), ("a" * 65, "1")])
def test_unsafe_names_are_rejected_before_any_write(tmp_path, data_dir, name, version):
    with pytest.raises(rm.RegisterError):
        rm.register(make_run(tmp_path), name, version)
    assert not (data_dir / "models").exists()


def test_incomplete_or_unsafe_runs_are_rejected(tmp_path, data_dir):
    with pytest.raises(rm.RegisterError, match="not found"):
        rm.register(tmp_path, "a", "1")
    with pytest.raises(rm.RegisterError, match="not self-contained"):
        rm.register(make_run(tmp_path, sidecar=True), "a", "1")
    run = make_run(tmp_path / "x") if (tmp_path / "x").mkdir() is None else None
    (run / "test_metrics.json").unlink()
    with pytest.raises(rm.RegisterError, match="Missing test_metrics.json"):
        rm.register(run, "a", "1")


def test_duplicate_version_is_refused_and_does_not_overwrite(tmp_path, data_dir):
    rm.register(make_run(tmp_path), "dup", "1")
    other = tmp_path / "other"
    other.mkdir()
    run2 = make_run(other, onnx=b"different")
    with pytest.raises(rm.RegisterError, match="already registered"):
        rm.register(run2, "dup", "1")
    assert (data_dir / "models" / "dup-1.onnx").read_bytes() == b"fake-onnx-bytes"


def test_onnx_validation_accepts_a_good_model_and_rejects_a_wrong_one(tmp_path):
    onnx = pytest.importorskip("onnx")
    pytest.importorskip("onnxruntime")
    from onnx import TensorProto, helper

    def build(out_dim):
        x = helper.make_tensor_value_info("input", TensorProto.FLOAT, ["N", 3, 8, 8])
        y = helper.make_tensor_value_info("logits", TensorProto.FLOAT, ["N", out_dim])
        nodes = [helper.make_node("GlobalAveragePool", ["input"], ["g"]), helper.make_node("Flatten", ["g"], ["f"]),
                 helper.make_node("Slice", ["f", "starts", "ends", "axes"], ["logits"])]
        inits = [helper.make_tensor(n, TensorProto.INT64, [1], v) for n, v in (("starts", [0]), ("ends", [out_dim]), ("axes", [1]))]
        return helper.make_model(helper.make_graph(nodes, "g", [x], [y], inits), opset_imports=[helper.make_opsetid("", 18)], ir_version=10)

    good, bad = tmp_path / "good.onnx", tmp_path / "bad.onnx"
    onnx.save(build(2), good)
    onnx.save(build(3), bad)
    assert "validated with onnxruntime" in rm.validate_onnx(good)
    with pytest.raises(rm.RegisterError, match="2 logits"):
        rm.validate_onnx(bad)
    (tmp_path / "junk.onnx").write_bytes(b"not a model")
    with pytest.raises(rm.RegisterError, match="cannot be loaded"):
        rm.validate_onnx(tmp_path / "junk.onnx")
