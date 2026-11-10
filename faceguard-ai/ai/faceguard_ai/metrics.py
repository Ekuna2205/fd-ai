"""Presentation-attack-detection metrics (ISO/IEC 30107-3 style).

Convention: label 1 = bona fide (real face), label 0 = attack (spoof). `score` = P(bona fide).
  APCER = attacks classified as bona fide / all attacks
  BPCER = bona fide classified as attack / all bona fide
  ACER  = (APCER + BPCER) / 2
Values that cannot be computed (a class is absent) are returned as None, never as 0.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def confusion(y_true: Sequence[int], y_pred: Sequence[int]) -> dict[str, int]:
    t, p = np.asarray(y_true, dtype=int), np.asarray(y_pred, dtype=int)
    if t.shape != p.shape:
        raise ValueError("y_true and y_pred must have the same length")
    return {
        "tp": int(((t == 1) & (p == 1)).sum()),  # bona fide accepted
        "tn": int(((t == 0) & (p == 0)).sum()),  # attack rejected
        "fp": int(((t == 0) & (p == 1)).sum()),  # attack accepted  (APCER numerator)
        "fn": int(((t == 1) & (p == 0)).sum()),  # bona fide rejected (BPCER numerator)
    }


def _ratio(n: int, d: int) -> float | None:
    return n / d if d else None


def roc_auc(y_true: Sequence[int], score: Sequence[float]) -> float | None:
    """Rank-based AUC (Mann-Whitney U with tie handling). None unless both classes are present."""
    t, s = np.asarray(y_true, dtype=int), np.asarray(score, dtype=float)
    pos, neg = s[t == 1], s[t == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    allv = np.concatenate([pos, neg])[order]
    ranks = np.empty(len(allv))
    i = 0
    while i < len(allv):  # average ranks over ties
        j = i
        while j + 1 < len(allv) and allv[j + 1] == allv[i]:
            j += 1
        ranks[i : j + 1] = (i + j) / 2 + 1
        i = j + 1
    rank_of = np.empty(len(allv))
    rank_of[order] = ranks
    r_pos = rank_of[: len(pos)].sum()
    return float((r_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def evaluate(y_true: Sequence[int], score: Sequence[float], threshold: float = 0.5) -> dict:
    """Full metric set at a fixed threshold. The threshold must be chosen on validation data, never on test data."""
    t, s = np.asarray(y_true, dtype=int), np.asarray(score, dtype=float)
    if len(t) == 0:
        raise ValueError("Cannot evaluate an empty set")
    pred = (s >= threshold).astype(int)
    c = confusion(t, pred)
    n = len(t)
    precision = _ratio(c["tp"], c["tp"] + c["fp"])
    recall = _ratio(c["tp"], c["tp"] + c["fn"])
    f1 = None if precision is None or recall is None or (precision + recall) == 0 else 2 * precision * recall / (precision + recall)
    apcer = _ratio(c["fp"], c["fp"] + c["tn"])
    bpcer = _ratio(c["fn"], c["fn"] + c["tp"])
    acer = None if apcer is None or bpcer is None else (apcer + bpcer) / 2
    return {
        "n": n, "n_bona_fide": int((t == 1).sum()), "n_attack": int((t == 0).sum()), "threshold": threshold,
        "accuracy": (c["tp"] + c["tn"]) / n, "precision": precision, "recall": recall, "f1": f1,
        "roc_auc": roc_auc(t, s), "apcer": apcer, "bpcer": bpcer, "acer": acer,
        "confusion_matrix": {"labels": ["attack", "bona_fide"], "matrix": [[c["tn"], c["fp"]], [c["fn"], c["tp"]]]},
    }


def choose_threshold_min_acer(y_true: Sequence[int], score: Sequence[float]) -> float:
    """Threshold minimising ACER on the given (validation) data. Falls back to 0.5 if a class is missing."""
    t, s = np.asarray(y_true, dtype=int), np.asarray(score, dtype=float)
    if len(set(t.tolist())) < 2:
        return 0.5
    cands = np.unique(s)
    best_thr, best = 0.5, float("inf")
    for thr in cands:
        acer = evaluate(t, s, float(thr))["acer"]
        if acer is not None and acer < best:
            best, best_thr = acer, float(thr)
    return best_thr
