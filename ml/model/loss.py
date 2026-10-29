"""Masked binary cross-entropy for padded sequences."""
from __future__ import annotations

import torch
import torch.nn.functional as F


def masked_bce_with_logits(
    logits: torch.Tensor,
    target: torch.Tensor,
    mask: torch.Tensor,
    pos_weight: float | None = None,
) -> torch.Tensor:
    """Mean BCE over REAL (mask == True) steps only; padding never contributes.

    pos_weight multiplies the loss of positive examples (use (neg/pos) from the train
    split to counter class imbalance; ~1.0 means no re-weighting).
    """
    pw = None if pos_weight is None else torch.tensor(pos_weight, device=logits.device)
    per_step = F.binary_cross_entropy_with_logits(
        logits, target, pos_weight=pw, reduction="none"
    )
    m = mask.to(per_step.dtype)
    return (per_step * m).sum() / m.sum().clamp(min=1.0)