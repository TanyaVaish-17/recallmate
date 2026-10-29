"""Canonical interaction schema shared by every data source.

Any source (ASSISTments, synthetic, or RecallMate's own `learning_events` table)
is converted to this one-row-per-answered-question format before preprocessing.
That is what keeps training and inference compatible.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CANONICAL_COLUMNS = [
    "user_id",             # int, student identifier (used ONLY for splitting, never as a feature)
    "order",               # int, chronological order of the event within the dataset
    "question_id",         # int, raw question/problem identifier
    "topic_id",            # int, raw topic / skill identifier
    "correct",             # 0 or 1
    "timestamp_h",         # float hours since an arbitrary origin; NaN if the source has no clock
    "revised_since_last",  # 0/1, a revision session on this topic happened since its previous event
]

# Order matters: this is the column order of the numeric tensor fed to the model.
NUMERIC_FEATURES = [
    "log_gap_prev",     # log1p(hours since the previous event of any topic)
    "log_gap_topic",    # log1p(hours since the previous event on the SAME topic)
    "log_attempt",      # log1p(prior attempts at this exact question)
    "log_topic_count",  # log1p(prior attempts at this topic)
    "revised_since_last",
]
N_STANDARDIZED = 4  # the first 4 are standardized with train statistics; the flag stays 0/1

# Categorical "previous answer" feature.
PREV_NONE, PREV_WRONG, PREV_RIGHT = 0, 1, 2

# Embedding index reserved values.
PAD, UNK = 0, 1


def validate_canonical(df: pd.DataFrame) -> None:
    missing = [c for c in CANONICAL_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing canonical columns: {missing}")
    if df[["user_id", "order", "question_id", "topic_id", "correct"]].isna().any().any():
        raise ValueError("Canonical frame contains nulls in required columns")
    if not df["correct"].isin([0, 1]).all():
        raise ValueError("`correct` must be 0 or 1")
    if not df["revised_since_last"].isin([0, 1]).all():
        raise ValueError("`revised_since_last` must be 0 or 1")
    if df.duplicated(["user_id", "order"]).any():
        raise ValueError("Duplicate (user_id, order) pairs")


def empty_canonical() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=float) for c in CANONICAL_COLUMNS})


def has_real_time(df: pd.DataFrame) -> bool:
    return bool(np.isfinite(df["timestamp_h"].to_numpy(dtype=float)).any())