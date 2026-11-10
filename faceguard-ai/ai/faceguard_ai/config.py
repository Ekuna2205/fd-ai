from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class TrainConfig:
    manifest: str = ""  # CSV with columns: path,label[,identity,group,sha256]  (label: real|spoof or 1|0)
    root: str = ""  # directory the manifest paths are relative to
    out_dir: str = "runs/baseline"
    image_size: int = 112
    batch_size: int = 32
    epochs: int = 20
    lr: float = 1e-3
    weight_decay: float = 1e-4
    seed: int = 42
    ratios: tuple[float, float, float] = (0.7, 0.15, 0.15)
    num_workers: int = 0
    device: str = "auto"  # auto | cpu | cuda
    balance: str = "weighted_loss"  # weighted_loss | oversample | none
    augment: bool = True
    base_channels: int = 16
    dropout: float = 0.3
    min_samples_per_class: int = 20  # refuse to train on trivially small data
    extra: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, path: str | Path) -> "TrainConfig":
        d = json.loads(Path(path).read_text())
        if "ratios" in d:
            d["ratios"] = tuple(d["ratios"])
        return cls(**d)
