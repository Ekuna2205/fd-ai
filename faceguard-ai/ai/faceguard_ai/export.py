"""Inference and ONNX export. The ONNX file takes float32 [N,3,S,S] already preprocessed with data.preprocess()."""
from __future__ import annotations

import argparse

import numpy as np

from .data import preprocess


def predict_bgr(model, bgr: np.ndarray, image_size: int, device="cpu") -> float:
    """Returns P(bona fide). Callers must still treat the number as uncalibrated evidence, not proof."""
    import torch
    x = torch.from_numpy(preprocess(bgr, image_size)).unsqueeze(0).to(device)
    with torch.no_grad():
        return float(torch.softmax(model(x), dim=1)[0, 1])


def export_onnx(checkpoint: str, out_path: str) -> str:
    import torch

    from .model import load_checkpoint
    model, ck = load_checkpoint(checkpoint, "cpu")
    size = ck["config"]["image_size"]
    # PyTorch >= 2.9 exports through torch.export (needs the `onnxscript` package) and takes `dynamic_shapes`,
    # keyed by the forward() argument name ("x"). The batch axis stays dynamic so one file serves any batch size.
    batch = torch.export.Dim("batch", min=1, max=256)
    torch.onnx.export(model, (torch.zeros(1, 3, size, size),), out_path, input_names=["input"], output_names=["logits"],
                      dynamic_shapes={"x": {0: batch}}, opset_version=18,
                      external_data=False)  # one self-contained file: a stray weights sidecar would break deployment
    return out_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("checkpoint")
    ap.add_argument("out")
    a = ap.parse_args()
    print(export_onnx(a.checkpoint, a.out))
