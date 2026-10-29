"""Turn canonical interaction rows into leakage-free Transformer training tensors.

KEY IDEA (target construction, no future leakage)
-------------------------------------------------
The model predicts, at each step t, whether the student answers question t correctly.
The input at step t contains ONLY information that exists *before* the student answers:

    question_t, topic_t                     what is being asked
    prev_correct_t   (from answer t-1)      the PREVIOUS answer, never answer t
    gaps, attempt counts, revision flag     computed from events < t (and timestamp_t)

and the target is correct_t. A causal attention mask (Step 2) additionally stops step t
from looking at inputs of steps > t. The two safeguards are independent, and
ml/tests/test_preprocess.py verifies the first one directly.

Splitting: BY STUDENT, so test metrics measure generalisation to unseen students.
Vocabularies and normalisation statistics are fitted on TRAIN students only; questions
unseen in training map to UNK.

Tensor shapes per split (N = number of windows, L = max_len):
    question      (N, L)    int64    0 = PAD, 1 = UNK, >=2 real questions
    topic         (N, L)    int64
    prev_correct  (N, L)    int64    0 = none, 1 = wrong, 2 = right
    numeric       (N, L, 5) float32  see schema.NUMERIC_FEATURES
    target        (N, L)    float32  correct_t
    mask          (N, L)    bool     True on real (non-padding) steps
    user_ids      (N,)      int64    for grouping / debugging only
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ml.data.schema import (
    N_STANDARDIZED,
    NUMERIC_FEATURES,
    PAD,
    PREV_NONE,
    PREV_RIGHT,
    PREV_WRONG,
    UNK,
    validate_canonical,
)


# --------------------------------------------------------------------------- #
# Cleaning and splitting
# --------------------------------------------------------------------------- #
def clean(df: pd.DataFrame, min_events: int = 5) -> pd.DataFrame:
    """Validate, sort chronologically per student, drop students with too little history."""
    validate_canonical(df)
    df = df.sort_values(["user_id", "order"], kind="stable").reset_index(drop=True)
    counts = df.groupby("user_id")["order"].transform("size")
    return df[counts >= min_events].reset_index(drop=True)


def split_users(
    user_ids: np.ndarray, seed: int = 42, val_frac: float = 0.15, test_frac: float = 0.15
) -> dict[str, np.ndarray]:
    """Disjoint train/val/test partition of students (seeded shuffle)."""
    users = np.array(sorted(set(int(u) for u in user_ids)))
    if len(users) < 3:
        raise ValueError("Need at least 3 students to make train/val/test splits")
    rng = np.random.default_rng(seed)
    rng.shuffle(users)
    n_test = max(1, int(round(len(users) * test_frac)))
    n_val = max(1, int(round(len(users) * val_frac)))
    return {
        "test": users[:n_test],
        "val": users[n_test : n_test + n_val],
        "train": users[n_test + n_val :],
    }


# --------------------------------------------------------------------------- #
# Vocabulary (fitted on train only)
# --------------------------------------------------------------------------- #
@dataclass
class Vocab:
    question: dict[int, int]
    topic: dict[int, int]

    @property
    def n_questions(self) -> int:  # embedding table size (PAD + UNK + real)
        return len(self.question) + 2

    @property
    def n_topics(self) -> int:
        return len(self.topic) + 2

    def encode_questions(self, raw: np.ndarray) -> np.ndarray:
        return np.array([self.question.get(int(x), UNK) for x in raw], dtype=np.int64)

    def encode_topics(self, raw: np.ndarray) -> np.ndarray:
        return np.array([self.topic.get(int(x), UNK) for x in raw], dtype=np.int64)


def fit_vocab(train_df: pd.DataFrame) -> Vocab:
    qs = sorted(train_df["question_id"].unique())
    ts = sorted(train_df["topic_id"].unique())
    return Vocab(
        question={int(q): i + 2 for i, q in enumerate(qs)},
        topic={int(t): i + 2 for i, t in enumerate(ts)},
    )


# --------------------------------------------------------------------------- #
# Per-student feature construction
# --------------------------------------------------------------------------- #
def user_features(
    question: np.ndarray,
    topic: np.ndarray,
    correct: np.ndarray,
    timestamp_h: np.ndarray,
    revised: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Features for ONE student's chronologically sorted events.

    Returns (prev_correct[n], numeric[n, 5]). Every value at index t depends only on
    events < t, plus the *question/topic/timestamp/revision flag of event t itself*
    (all known before the student answers). `correct[t]` is never used at index t.
    """
    n = len(question)
    prev_correct = np.full(n, PREV_NONE, dtype=np.int64)
    if n > 1:
        prev_correct[1:] = np.where(correct[:-1] == 1, PREV_RIGHT, PREV_WRONG)

    numeric = np.zeros((n, len(NUMERIC_FEATURES)), dtype=np.float64)
    last_topic_time: dict[int, float] = {}
    topic_count: dict[int, int] = {}
    question_count: dict[int, int] = {}

    for t in range(n):
        q, tp, now = int(question[t]), int(topic[t]), float(timestamp_h[t])

        if t > 0 and np.isfinite(now) and np.isfinite(timestamp_h[t - 1]):
            numeric[t, 0] = np.log1p(max(now - float(timestamp_h[t - 1]), 0.0))
        if tp in last_topic_time and np.isfinite(now) and np.isfinite(last_topic_time[tp]):
            numeric[t, 1] = np.log1p(max(now - last_topic_time[tp], 0.0))
        numeric[t, 2] = np.log1p(question_count.get(q, 0))
        numeric[t, 3] = np.log1p(topic_count.get(tp, 0))
        numeric[t, 4] = float(revised[t])

        # Update state AFTER computing features for step t.
        last_topic_time[tp] = now
        topic_count[tp] = topic_count.get(tp, 0) + 1
        question_count[q] = question_count.get(q, 0) + 1

    return prev_correct, numeric


@dataclass
class UserSequence:
    user_id: int
    question: np.ndarray       # encoded
    topic: np.ndarray          # encoded
    prev_correct: np.ndarray
    numeric: np.ndarray        # raw (un-standardised)
    target: np.ndarray


def build_sequences(df: pd.DataFrame, vocab: Vocab) -> list[UserSequence]:
    seqs: list[UserSequence] = []
    for user_id, g in df.groupby("user_id", sort=True):
        q_raw = g["question_id"].to_numpy()
        t_raw = g["topic_id"].to_numpy()
        correct = g["correct"].to_numpy()
        prev, numeric = user_features(
            q_raw,
            t_raw,
            correct,
            g["timestamp_h"].to_numpy(dtype=float),
            g["revised_since_last"].to_numpy(),
        )
        seqs.append(
            UserSequence(
                user_id=int(user_id),
                question=vocab.encode_questions(q_raw),
                topic=vocab.encode_topics(t_raw),
                prev_correct=prev,
                numeric=numeric,
                target=correct.astype(np.float32),
            )
        )
    return seqs


# --------------------------------------------------------------------------- #
# Normalisation (train statistics only)
# --------------------------------------------------------------------------- #
def fit_normalizer(train_seqs: list[UserSequence]) -> dict[str, list[float]]:
    allnum = np.concatenate([s.numeric for s in train_seqs], axis=0)[:, :N_STANDARDIZED]
    mean = allnum.mean(axis=0)
    std = allnum.std(axis=0)
    std = np.where(std < 1e-8, 1.0, std)  # constant column (e.g. no clock) -> leave at 0
    return {"mean": mean.tolist(), "std": std.tolist()}


def apply_normalizer(numeric: np.ndarray, stats: dict[str, list[float]]) -> np.ndarray:
    out = numeric.astype(np.float32).copy()
    mean = np.asarray(stats["mean"], dtype=np.float32)
    std = np.asarray(stats["std"], dtype=np.float32)
    out[..., :N_STANDARDIZED] = (out[..., :N_STANDARDIZED] - mean) / std
    return out


# --------------------------------------------------------------------------- #
# Windowing and padding
# --------------------------------------------------------------------------- #
def make_windows(
    seqs: list[UserSequence], stats: dict[str, list[float]], max_len: int
) -> dict[str, np.ndarray]:
    """Chunk long students into windows of at most `max_len` and right-pad.

    Features were computed on the FULL sequence first, so a window that starts mid-history
    still carries the true previous answer, gaps and counts (information that really was
    available at that moment). Windows with a single step are discarded.
    """
    chunks = []
    for s in seqs:
        num = apply_normalizer(s.numeric, stats)
        for start in range(0, len(s.target), max_len):
            end = min(start + max_len, len(s.target))
            if end - start >= 2:
                chunks.append((s, num, start, end))

    n = len(chunks)
    L = max_len
    out = {
        "question": np.full((n, L), PAD, dtype=np.int64),
        "topic": np.full((n, L), PAD, dtype=np.int64),
        "prev_correct": np.full((n, L), PREV_NONE, dtype=np.int64),
        "numeric": np.zeros((n, L, len(NUMERIC_FEATURES)), dtype=np.float32),
        "target": np.zeros((n, L), dtype=np.float32),
        "mask": np.zeros((n, L), dtype=bool),
        "user_ids": np.zeros(n, dtype=np.int64),
    }
    for i, (s, num, start, end) in enumerate(chunks):
        k = end - start
        out["question"][i, :k] = s.question[start:end]
        out["topic"][i, :k] = s.topic[start:end]
        out["prev_correct"][i, :k] = s.prev_correct[start:end]
        out["numeric"][i, :k] = num[start:end]
        out["target"][i, :k] = s.target[start:end]
        out["mask"][i, :k] = True
        out["user_ids"][i] = s.user_id
    return out


def positive_rate(arrays: dict[str, np.ndarray]) -> float:
    m = arrays["mask"]
    return float(arrays["target"][m].mean()) if m.any() else float("nan")