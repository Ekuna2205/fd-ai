"""Training entry point: python -m faceguard_ai.train --manifest data/manifest.csv --root data --out runs/exp1"""
from __future__ import annotations

import argparse
import json
import logging
import random
from pathlib import Path

import numpy as np

from .config import TrainConfig
from .data import load_manifest, make_torch_dataset
from .splits import assert_no_leakage, class_weights, split

log = logging.getLogger("faceguard_ai.train")


def seed_everything(seed: int) -> None:
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def pick_device(name: str):
    import torch
    if name == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but not available")
    return torch.device("cuda" if name == "cuda" or (name == "auto" and torch.cuda.is_available()) else "cpu")


def predict_scores(model, loader, device) -> tuple[list[int], list[float]]:
    import torch
    model.eval()
    ys, ps = [], []
    with torch.no_grad():
        for x, y in loader:
            p = torch.softmax(model(x.to(device)), dim=1)[:, 1]
            ys += y.tolist()
            ps += p.cpu().tolist()
    return ys, ps


def run(cfg: TrainConfig) -> dict:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, WeightedRandomSampler

    from . import metrics
    from .model import build_model, save_checkpoint

    out = Path(cfg.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), logging.FileHandler(out / "train.log")],
                        format="%(asctime)s %(levelname)s %(message)s")
    seed_everything(cfg.seed)
    device = pick_device(cfg.device)
    log.info("device=%s seed=%d", device, cfg.seed)

    samples, problems = load_manifest(cfg.manifest, cfg.root, min_per_class=cfg.min_samples_per_class)
    for p in problems:
        log.warning("manifest: %s", p)
    splits, report = split(samples, cfg.ratios, cfg.seed)
    assert_no_leakage(splits)
    for w in report.warnings:
        log.warning(w)
    if not report.identity_disjoint:
        log.warning("Some samples have no identity/group metadata: identity-disjoint generalisation is NOT guaranteed.")
    if any(len({s.label for s in splits[n]}) < 2 for n in ("train", "val", "test")):
        raise RuntimeError("A split lacks one of the classes; add data or change ratios. " + json.dumps(report.class_counts))
    (out / "split_report.json").write_text(json.dumps(report.__dict__, indent=2, default=str))
    (out / "config.json").write_text(cfg.to_json())

    ds = {n: make_torch_dataset(splits[n], cfg.image_size, n == "train" and cfg.augment, cfg.seed) for n in splits}
    g = torch.Generator().manual_seed(cfg.seed)
    train_labels = [s.label for s in splits["train"]]
    if cfg.balance == "oversample":
        cw = class_weights(train_labels)
        sampler = WeightedRandomSampler([cw[l] for l in train_labels], len(train_labels), generator=g)
        train_loader = DataLoader(ds["train"], cfg.batch_size, sampler=sampler, num_workers=cfg.num_workers)
    else:
        train_loader = DataLoader(ds["train"], cfg.batch_size, shuffle=True, generator=g, num_workers=cfg.num_workers)
    val_loader = DataLoader(ds["val"], cfg.batch_size, num_workers=cfg.num_workers)
    test_loader = DataLoader(ds["test"], cfg.batch_size, num_workers=cfg.num_workers)

    model = build_model(cfg.base_channels, cfg.dropout).to(device)
    weights = None
    if cfg.balance == "weighted_loss":
        cw = class_weights(train_labels)
        weights = torch.tensor([cw[0], cw[1]], dtype=torch.float32, device=device)
    loss_fn = nn.CrossEntropyLoss(weight=weights)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=cfg.epochs)

    best_acer, history = float("inf"), []
    for epoch in range(1, cfg.epochs + 1):
        model.train()
        total, n = 0.0, 0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            loss = loss_fn(model(x), y)
            loss.backward()
            opt.step()
            total += loss.item() * len(y)
            n += len(y)
        sched.step()
        yv, pv = predict_scores(model, val_loader, device)
        vm = metrics.evaluate(yv, pv, 0.5)
        history.append({"epoch": epoch, "train_loss": total / n, "val": vm})
        log.info("epoch %d loss=%.4f val_acc=%.3f val_acer=%s", epoch, total / n, vm["accuracy"], vm["acer"])
        score = vm["acer"] if vm["acer"] is not None else 1.0
        save_checkpoint(out / "last.pt", model, cfg, {"epoch": epoch})
        if score < best_acer:
            best_acer = score
            save_checkpoint(out / "best.pt", model, cfg, {"epoch": epoch})
    (out / "history.json").write_text(json.dumps(history, indent=2))

    # The threshold is chosen on VALIDATION data only, then applied once to the untouched TEST split.
    from .model import load_checkpoint
    best, _ = load_checkpoint(out / "best.pt", device)
    yv, pv = predict_scores(best, val_loader, device)
    thr = metrics.choose_threshold_min_acer(yv, pv)
    yt, pt = predict_scores(best, test_loader, device)
    test = metrics.evaluate(yt, pt, thr)
    test["identity_disjoint_split"] = report.identity_disjoint
    (out / "test_metrics.json").write_text(json.dumps(test, indent=2))
    log.info("TEST metrics (threshold %.3f): %s", thr, json.dumps({k: test[k] for k in ("accuracy", "apcer", "bpcer", "acer", "roc_auc")}))
    return test


def main() -> None:
    ap = argparse.ArgumentParser(description="Train the FaceGuard anti-spoofing baseline on a labelled manifest.")
    ap.add_argument("--config")
    ap.add_argument("--manifest")
    ap.add_argument("--root", default="")
    ap.add_argument("--out", default="runs/baseline")
    ap.add_argument("--epochs", type=int)
    ap.add_argument("--device", choices=["auto", "cpu", "cuda"])
    a = ap.parse_args()
    cfg = TrainConfig.from_json(a.config) if a.config else TrainConfig()
    cfg.manifest = a.manifest or cfg.manifest
    cfg.root, cfg.out_dir = a.root or cfg.root, a.out
    cfg.epochs = a.epochs or cfg.epochs
    cfg.device = a.device or cfg.device
    run(cfg)


if __name__ == "__main__":
    main()
