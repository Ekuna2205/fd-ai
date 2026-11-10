"""Manifest loading, validation and torch datasets. Never generates or downloads data."""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import cv2
import numpy as np

from .splits import Sample

LABELS = {"real": 1, "bona_fide": 1, "live": 1, "1": 1, "spoof": 0, "attack": 0, "fake": 0, "0": 0}
IMG_EXT = {".jpg", ".jpeg", ".png"}


class DatasetError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(manifest: str | Path, root: str | Path = "", compute_hashes: bool = True,
                  min_per_class: int = 1) -> tuple[list[Sample], list[str]]:
    """Reads and validates a manifest. Returns (samples, problems). Bad rows are reported, not silently used."""
    manifest = Path(manifest)
    if not manifest.is_file():
        raise DatasetError(f"Manifest not found: {manifest}")
    base = Path(root) if root else manifest.parent
    samples: list[Sample] = []
    problems: list[str] = []
    with manifest.open(newline="", encoding="utf-8") as f:
        rows = csv.DictReader(f)
        if not rows.fieldnames or not {"path", "label"} <= set(rows.fieldnames):
            raise DatasetError("Manifest needs at least the columns: path,label")
        for n, row in enumerate(rows, start=2):
            label = LABELS.get(str(row["label"]).strip().lower())
            p = (base / row["path"]).resolve()
            if label is None:
                problems.append(f"line {n}: unknown label {row['label']!r}")
            elif base.resolve() not in p.parents:
                problems.append(f"line {n}: path escapes the dataset root")
            elif p.suffix.lower() not in IMG_EXT or not p.is_file():
                problems.append(f"line {n}: missing or unsupported image {row['path']!r}")
            else:
                samples.append(Sample(str(p), label, row.get("sha256") or (sha256_file(p) if compute_hashes else None),
                                      (row.get("identity") or None), (row.get("group") or None)))
    counts = {c: sum(s.label == c for s in samples) for c in (0, 1)}
    for c, name in ((1, "real"), (0, "spoof")):
        if counts[c] < min_per_class:
            raise DatasetError(f"Need at least {min_per_class} {name} samples, found {counts[c]}. "
                               "Training requires real labelled data; none is generated.")
    return samples, problems


def preprocess(bgr: np.ndarray, size: int) -> np.ndarray:
    """BGR uint8 -> float32 CHW in [-1, 1], resized to size x size. Shared by training and inference."""
    img = cv2.resize(bgr, (size, size), interpolation=cv2.INTER_AREA)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    return ((img - 0.5) / 0.5).transpose(2, 0, 1)


def augment(bgr: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Mild, label-preserving augmentation. No blur/JPEG-heavy transforms that could erase spoof cues."""
    out = bgr
    if rng.random() < 0.5:
        out = cv2.flip(out, 1)
    if rng.random() < 0.5:
        out = np.clip(out.astype(np.float32) * rng.uniform(0.8, 1.2) + rng.uniform(-15, 15), 0, 255).astype(np.uint8)
    if rng.random() < 0.5:
        h, w = out.shape[:2]
        m = cv2.getRotationMatrix2D((w / 2, h / 2), rng.uniform(-10, 10), rng.uniform(0.92, 1.08))
        out = cv2.warpAffine(out, m, (w, h), borderMode=cv2.BORDER_REFLECT)
    return out


def make_torch_dataset(samples: list[Sample], size: int, train: bool, seed: int):
    import torch
    from torch.utils.data import Dataset

    class FaceDataset(Dataset):
        def __init__(self) -> None:
            self.samples, self.size, self.train = samples, size, train
            self.rng = np.random.default_rng(seed)

        def __len__(self) -> int:
            return len(self.samples)

        def __getitem__(self, i: int):
            s = self.samples[i]
            bgr = cv2.imread(s.path, cv2.IMREAD_COLOR)
            if bgr is None:
                raise DatasetError(f"Unreadable image: {s.path}")
            if self.train:
                bgr = augment(bgr, self.rng)
            return torch.from_numpy(preprocess(bgr, self.size)), torch.tensor(s.label, dtype=torch.long)

    return FaceDataset()
