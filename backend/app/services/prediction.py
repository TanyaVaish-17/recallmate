"""Inference service: turns a student's learning history into real Transformer predictions.

How a prediction is made
------------------------
To estimate P(correct) on topic T *now*, we append one hypothetical step (topic T, an
unseen question, current time) to the student's history, build the exact same features
used in training (ml.data.preprocess.user_features), and read the model's output at that
last step. The hypothetical step's own answer is never an input (no leakage).

RecallMate's questions/topics are not in the training vocabulary, so every question and
topic id is mapped to UNK. This is the "ids hidden" setting that ml/artifacts/results.md
evaluates; the model then relies on answer history, gaps, counts and revision flags.

If there is no checkpoint (or torch is missing) we raise ModelUnavailable. We never
return random or heuristic numbers pretending to be the Transformer.
"""
from __future__ import annotations

import sys
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.core.config import ROOT_DIR

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

CHECKPOINT_PATH = ROOT_DIR / "ml" / "artifacts" / "kt_transformer.pt"
RESULTS_PATH = ROOT_DIR / "ml" / "artifacts" / "results.json"
MIN_EVENTS = 5  # same minimum history length used when the model was trained


class ModelUnavailable(Exception):
    """Raised when no trained checkpoint (or no torch) is available."""


@dataclass
class HistoryEvent:
    topic_id: int
    question_id: int
    correct: int
    ts: datetime
    revised: int = 0


@dataclass
class Prediction:
    topic_id: int
    probability: float
    n_events: int
    model_version: str


def aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _hours(dt: datetime) -> float:
    return aware(dt).timestamp() / 3600.0


def attach_revision_flags(
    events: list[HistoryEvent], completions_by_topic: dict[int, list[datetime]]
) -> None:
    """revised=1 if a revision session on the event's topic was completed since the
    previous event on that same topic (mirrors `revised_since_last` in training)."""
    last_seen: dict[int, datetime] = {}
    comps = {t: sorted(aware(c) for c in cs) for t, cs in completions_by_topic.items()}
    for e in events:
        cs = comps.get(e.topic_id, [])
        prev = last_seen.get(e.topic_id)
        lo = bisect_right(cs, aware(prev)) if prev else 0
        hi = bisect_right(cs, aware(e.ts))
        e.revised = int(hi > lo)
        last_seen[e.topic_id] = e.ts


@lru_cache(maxsize=1)
def _load():
    try:
        import torch  # noqa: F401
        from ml.model.io import load_checkpoint
    except ImportError as exc:  # torch / ml package missing
        raise ModelUnavailable(f"PyTorch or the ml package is not installed: {exc}") from exc
    try:
        return load_checkpoint(CHECKPOINT_PATH)
    except FileNotFoundError as exc:
        raise ModelUnavailable(str(exc)) from exc


def reset_model_cache() -> None:
    _load.cache_clear()


def model_status() -> dict:
    try:
        model, ckpt = _load()
    except ModelUnavailable as exc:
        return {
            "trained": False,
            "message": str(exc),
            "how_to_train": "python -m ml.data.build_dataset --source synthetic && python -m ml.training.train",
        }
    return {
        "trained": True,
        "model_version": ckpt["model_version"],
        "dataset_source": ckpt.get("dataset_source"),
        "is_synthetic": ckpt.get("is_synthetic"),
        "n_parameters": model.n_parameters(),
        "best_epoch": ckpt.get("best_epoch"),
        "max_len": model.cfg.max_len,
        "min_events_required": MIN_EVENTS,
        "id_mode": "ids hidden (UNK): RecallMate questions are not in the training vocabulary",
    }


def _build_topic_sequence(
    history: list[HistoryEvent], topic_id: int, now: datetime, hyp_revised: int,
    stats: dict, max_len: int,
):
    from ml.data.preprocess import apply_normalizer, user_features
    from ml.data.schema import PREV_NONE, UNK  # noqa: F401

    n = len(history)
    q = np.array([e.question_id for e in history] + [-1], dtype=np.int64)  # -1 = unseen question
    t = np.array([e.topic_id for e in history] + [topic_id], dtype=np.int64)
    correct = np.array([e.correct for e in history] + [0], dtype=np.int64)  # dummy, never used at index n
    ts = np.array([_hours(e.ts) for e in history] + [_hours(now)], dtype=float)
    rev = np.array([e.revised for e in history] + [hyp_revised], dtype=np.int64)

    prev, numeric = user_features(q, t, correct, ts, rev)
    numeric = apply_normalizer(numeric, stats)

    lo = max(0, n + 1 - max_len)  # keep the most recent max_len steps (features already use full history)
    k = n + 1 - lo
    return (
        np.full(k, UNK, dtype=np.int64),   # question ids hidden
        np.full(k, UNK, dtype=np.int64),   # topic ids hidden
        prev[lo:], numeric[lo:],
    )


def predict_topics(
    history: list[HistoryEvent],
    topic_ids: list[int],
    completions_by_topic: dict[int, list[datetime]] | None = None,
    now: datetime | None = None,
) -> dict[int, Prediction]:
    """Return {topic_id: Prediction}. Topics are skipped if history is too short.

    `history` must be chronologically sorted and contain ONLY events that already happened.
    Raises ModelUnavailable if there is no trained checkpoint.
    """
    model, ckpt = _load()
    import torch

    if len(history) < MIN_EVENTS or not topic_ids:
        return {}
    now = aware(now or datetime.now(timezone.utc))
    completions_by_topic = completions_by_topic or {}
    stats = ckpt["normalization"]
    attach_revision_flags(history, completions_by_topic)

    last_topic_time: dict[int, datetime] = {}
    for e in history:
        last_topic_time[e.topic_id] = e.ts

    seqs = []
    for tid in topic_ids:
        comps = sorted(aware(c) for c in completions_by_topic.get(tid, []))
        prev_t = last_topic_time.get(tid)
        lo = bisect_right(comps, aware(prev_t)) if prev_t else 0
        hyp_rev = int(bisect_right(comps, now) > lo)
        seqs.append(_build_topic_sequence(history, tid, now, hyp_rev, stats, model.cfg.max_len))

    L = max(len(s[0]) for s in seqs)
    B = len(seqs)
    batch = {
        "question": torch.zeros(B, L, dtype=torch.long),
        "topic": torch.zeros(B, L, dtype=torch.long),
        "prev_correct": torch.zeros(B, L, dtype=torch.long),
        "numeric": torch.zeros(B, L, seqs[0][3].shape[1], dtype=torch.float32),
    }
    last_idx = []
    for i, (qs, ts_, pc, num) in enumerate(seqs):
        k = len(qs)
        batch["question"][i, :k] = torch.from_numpy(qs)
        batch["topic"][i, :k] = torch.from_numpy(ts_)
        batch["prev_correct"][i, :k] = torch.from_numpy(pc)
        batch["numeric"][i, :k] = torch.from_numpy(num)
        last_idx.append(k - 1)

    with torch.no_grad():
        probs = model.predict_proba(batch)  # (B, L), causal: step k-1 never sees padding
    version = ckpt["model_version"]
    return {
        tid: Prediction(tid, float(probs[i, last_idx[i]]), len(history), version)
        for i, tid in enumerate(topic_ids)
    }
