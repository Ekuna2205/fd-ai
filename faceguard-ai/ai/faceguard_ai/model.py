"""Small configurable CNN baseline for real-vs-spoof classification.

This is a deliberately simple baseline, not a state-of-the-art PAD model. Its quality is unknown until it is trained
and evaluated on real, labelled, representative data. Output class 1 = bona fide (real), 0 = attack (spoof).
"""
from __future__ import annotations

import torch
from torch import nn


def _block(cin: int, cout: int) -> nn.Sequential:
    return nn.Sequential(nn.Conv2d(cin, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
                         nn.Conv2d(cout, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
                         nn.MaxPool2d(2))


class SmallCNN(nn.Module):
    def __init__(self, base_channels: int = 16, dropout: float = 0.3) -> None:
        super().__init__()
        c = base_channels
        self.features = nn.Sequential(_block(3, c), _block(c, 2 * c), _block(2 * c, 4 * c), _block(4 * c, 8 * c))
        self.head = nn.Sequential(nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Dropout(dropout), nn.Linear(8 * c, 2))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.features(x))


def build_model(base_channels: int = 16, dropout: float = 0.3) -> SmallCNN:
    return SmallCNN(base_channels, dropout)


def save_checkpoint(path, model, cfg, extra: dict | None = None) -> None:
    from dataclasses import asdict
    torch.save({"state_dict": model.state_dict(), "config": asdict(cfg), "extra": extra or {}}, path)


def load_checkpoint(path, device="cpu"):
    ck = torch.load(path, map_location=device, weights_only=True)  # weights only: no arbitrary pickle execution
    cfg = ck["config"]
    model = build_model(cfg.get("base_channels", 16), cfg.get("dropout", 0.3))
    model.load_state_dict(ck["state_dict"])
    return model.to(device).eval(), ck
