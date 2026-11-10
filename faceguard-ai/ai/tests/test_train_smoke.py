"""Pipeline MECHANICS only. The images below are synthetic noise patterns, generated here purely so the code path
(manifest -> identity-disjoint split -> train -> checkpoint -> ONNX export -> ONNX inference) can execute.
Nothing here measures, or says anything about, real anti-spoofing accuracy. Skipped when PyTorch is absent."""
import csv
import json
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")
cv2 = pytest.importorskip("cv2")
onnxruntime = pytest.importorskip("onnxruntime")
pytest.importorskip("onnx")

from faceguard_ai.config import TrainConfig  # noqa: E402
from faceguard_ai.data import preprocess  # noqa: E402
from faceguard_ai.export import export_onnx, predict_bgr  # noqa: E402
from faceguard_ai.model import load_checkpoint  # noqa: E402
from faceguard_ai.train import run  # noqa: E402


def make_dataset(root: Path, identities=12, per_identity=6) -> Path:
    rng = np.random.default_rng(0)
    rows = []
    for i in range(identities):
        for k in range(per_identity):
            label = "real" if k % 2 == 0 else "spoof"
            img = rng.integers(0, 255, (96, 96, 3), dtype=np.uint8)
            if label == "spoof":
                img[::4] = 0  # arbitrary synthetic pattern, NOT a model of any real attack
            rel = f"id{i}_{k}.png"
            cv2.imwrite(str(root / rel), img)
            rows.append({"path": rel, "label": label, "identity": f"p{i}"})
    manifest = root / "manifest.csv"
    with manifest.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["path", "label", "identity"])
        w.writeheader()
        w.writerows(rows)
    return manifest


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    root = tmp_path_factory.mktemp("data")
    manifest = make_dataset(root)
    out = tmp_path_factory.mktemp("run")
    cfg = TrainConfig(manifest=str(manifest), root=str(root), out_dir=str(out), epochs=2, batch_size=8, image_size=64,
                      min_samples_per_class=10, device="cpu", base_channels=8)
    return run(cfg), Path(out)


def test_training_produces_artifacts_and_honest_split_report(trained):
    result, out = trained
    for name in ["best.pt", "last.pt", "config.json", "split_report.json", "history.json", "test_metrics.json", "train.log"]:
        assert (out / name).exists(), name
    report = json.loads((out / "split_report.json").read_text())
    assert report["identity_disjoint"] is True
    assert result is not None


def test_checkpoint_loads_with_weights_only(trained):
    _, out = trained
    model, ck = load_checkpoint(out / "best.pt")
    assert ck["config"]["image_size"] == 64 and not model.training


def test_onnx_export_matches_pytorch(trained):
    _, out = trained
    onnx_path = export_onnx(str(out / "best.pt"), str(out / "model.onnx"))
    assert not (out / "model.onnx.data").exists(), "weights must be embedded: copying model.onnx alone has to be enough"
    model, ck = load_checkpoint(out / "best.pt")
    sess = onnxruntime.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    bgr = np.random.default_rng(5).integers(0, 255, (96, 96, 3), dtype=np.uint8)
    x = preprocess(bgr, 64)[None].astype(np.float32)
    logits = sess.run(None, {"input": x})[0][0]
    p_onnx = float(np.exp(logits[1]) / np.exp(logits).sum())
    assert abs(p_onnx - predict_bgr(model, bgr, 64)) < 1e-4  # same preprocessing, same probability
    batch = sess.run(None, {"input": np.repeat(x, 3, axis=0)})[0]
    assert batch.shape == (3, 2)  # dynamic batch axis works


def test_refuses_trivially_small_datasets(tmp_path):
    manifest = make_dataset(tmp_path, identities=2, per_identity=2)
    cfg = TrainConfig(manifest=str(manifest), root=str(tmp_path), out_dir=str(tmp_path / "o"), epochs=1, device="cpu")
    with pytest.raises(Exception):
        run(cfg)
