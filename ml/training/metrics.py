"""Evaluation metrics for binary next-answer prediction."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)


def compute_metrics(y_true: np.ndarray, y_prob: np.ndarray, threshold: float = 0.5) -> dict:
    """AUC is threshold-free; accuracy/precision/recall/F1 use `threshold`.

    AUC is NaN when only one class is present (it is undefined there).
    """
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.clip(np.asarray(y_prob, dtype=float), 1e-7, 1 - 1e-7)
    y_pred = (y_prob >= threshold).astype(int)
    both = len(np.unique(y_true)) == 2
    return {
        "n": int(len(y_true)),
        "positive_rate": float(y_true.mean()) if len(y_true) else float("nan"),
        "auc": float(roc_auc_score(y_true, y_prob)) if both else float("nan"),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "log_loss": float(log_loss(y_true, y_prob, labels=[0, 1])),
        "brier": float(brier_score_loss(y_true, y_prob)),
        "threshold": threshold,
    }