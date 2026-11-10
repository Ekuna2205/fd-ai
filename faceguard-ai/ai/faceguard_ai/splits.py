"""Leak-free train/val/test splitting.

Samples that share a group (same identity, or same source clip/session) are never separated, so the
test split measures generalisation to unseen people. Samples with no identity metadata are treated as
their own group; callers must not claim identity-disjointness in that case (see `SplitReport.identity_disjoint`).
"""
from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Sample:
    path: str
    label: int  # 1 bona fide, 0 attack
    sha256: str | None = None
    identity: str | None = None  # person id, if the dataset provides one
    group: str | None = None  # e.g. recording session / source video


@dataclass
class SplitReport:
    counts: dict[str, int]
    class_counts: dict[str, dict[int, int]]
    identity_disjoint: bool  # True only when EVERY sample had identity or group metadata
    warnings: list[str] = field(default_factory=list)


def _group_key(s: Sample) -> str:
    if s.identity:
        return f"id:{s.identity}"
    if s.group:
        return f"grp:{s.group}"
    return f"file:{s.sha256 or s.path}"


def dedupe(samples: list[Sample]) -> tuple[list[Sample], int]:
    """Drops exact duplicate files (same SHA-256) so a copy cannot land in two splits."""
    seen: set[str] = set()
    out: list[Sample] = []
    for s in samples:
        if s.sha256:
            if s.sha256 in seen:
                continue
            seen.add(s.sha256)
        out.append(s)
    return out, len(samples) - len(out)


def split(samples: list[Sample], ratios=(0.7, 0.15, 0.15), seed: int = 42) -> tuple[dict[str, list[Sample]], SplitReport]:
    if abs(sum(ratios) - 1) > 1e-6 or any(r < 0 for r in ratios):
        raise ValueError("ratios must be non-negative and sum to 1")
    samples, _ = dedupe(samples)
    groups: dict[str, list[Sample]] = defaultdict(list)
    for s in samples:
        groups[_group_key(s)].append(s)
    keys = sorted(groups)
    random.Random(seed).shuffle(keys)

    total = len(samples)
    targets = {n: r * total for n, r in zip(("train", "val", "test"), ratios)}
    out: dict[str, list[Sample]] = {"train": [], "val": [], "test": []}
    # Greedy fill in shuffled order: assign each group to the split furthest below its target.
    for k in keys:
        name = max(targets, key=lambda n: (targets[n] - len(out[n])) / (targets[n] or 1e-9) if targets[n] else -1e9)
        out[name].extend(groups[k])

    warnings: list[str] = []
    classes = {n: defaultdict(int) for n in out}
    for n, items in out.items():
        for s in items:
            classes[n][s.label] += 1
        if items and len(classes[n]) < 2:
            warnings.append(f"The {n} split contains only one class; metrics and training on it are not meaningful.")
        if not items and targets[n] > 0:
            warnings.append(f"The {n} split is empty (too few groups for the requested ratios).")
    report = SplitReport(
        counts={n: len(v) for n, v in out.items()},
        class_counts={n: dict(c) for n, c in classes.items()},
        identity_disjoint=all(s.identity or s.group for s in samples) and bool(samples),
        warnings=warnings,
    )
    return out, report


def assert_no_leakage(splits: dict[str, list[Sample]]) -> None:
    """Raises AssertionError if any group or file hash appears in two splits."""
    owner: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for name, items in splits.items():
        for s in items:
            k = _group_key(s)
            if owner.setdefault(k, name) != name:
                raise AssertionError(f"group {k} appears in both {owner[k]} and {name}")
            if s.sha256 and hashes.setdefault(s.sha256, name) != name:
                raise AssertionError(f"file hash {s.sha256[:8]} appears in both {hashes[s.sha256]} and {name}")


def class_weights(labels: list[int]) -> dict[int, float]:
    """Inverse-frequency weights (mean weight 1) for loss balancing. Empty dict if a class is missing."""
    counts = {c: labels.count(c) for c in (0, 1)}
    if min(counts.values()) == 0:
        return {}
    n = len(labels)
    return {c: n / (2 * counts[c]) for c in counts}
