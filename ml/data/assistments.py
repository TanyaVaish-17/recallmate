"""Loader for the ASSISTments 2009-2010 *skill builder* dataset.

Download it yourself (see ml/README.md) and place the CSV at
ml/data/raw/skill_builder_data.csv. We do not redistribute it.

Columns we rely on (verified against the dataset's published schema):
    order_id, user_id, problem_id, skill_id, correct, original

Handling decisions (all deliberate, all reported in the preprocessing metadata):
* `original == 1` keeps main problems only; scaffolding sub-questions are dropped.
* Rows with a missing `skill_id` are dropped (about 15% of rows have no skill tag).
* In the skill-builder file a record is DUPLICATED once per skill tag, so we keep the
  first row per `order_id` to get one row per answered question.
* There is NO wall-clock timestamp in this file. `order_id` gives the chronological
  order, but time gaps are unavailable, so `timestamp_h` is NaN. The model's time-gap
  features are then constant zero for this dataset. This is a real limitation and the
  report must say so.
* `correct` is 1 only when the first attempt was right without hints.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ml.data.schema import CANONICAL_COLUMNS, validate_canonical

REQUIRED = ["order_id", "user_id", "problem_id", "skill_id", "correct"]


def load_assistments(csv_path: str | Path) -> pd.DataFrame:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Download the ASSISTments 2009-2010 skill builder CSV "
            "and place it there (instructions: ml/README.md), or run with --source synthetic."
        )

    # The published file is not valid UTF-8; latin-1 never fails.
    raw = pd.read_csv(path, encoding="latin-1", low_memory=False)
    missing = [c for c in REQUIRED if c not in raw.columns]
    if missing:
        raise ValueError(f"{path.name} is missing expected columns: {missing}")

    if "original" in raw.columns:
        raw = raw[raw["original"] == 1]

    raw = raw.dropna(subset=REQUIRED)
    raw = raw[raw["correct"].isin([0, 1])]
    raw = raw.drop_duplicates(subset="order_id", keep="first")

    df = pd.DataFrame(
        {
            "user_id": raw["user_id"].astype("int64"),
            "order": raw["order_id"].astype("int64"),
            "question_id": raw["problem_id"].astype("int64"),
            "topic_id": raw["skill_id"].astype("int64"),
            "correct": raw["correct"].astype("int64"),
            "timestamp_h": np.nan,
            "revised_since_last": 0,
        }
    )[CANONICAL_COLUMNS]

    df = df.sort_values(["user_id", "order"], kind="stable").reset_index(drop=True)
    validate_canonical(df)
    return df