"""Build train/val/test tensors + preprocessing metadata.

Examples (run from the repository root):
    python -m ml.data.build_dataset --source synthetic
    python -m ml.data.build_dataset --source assistments --csv ml/data/raw/skill_builder_data.csv
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ml.config import ARTIFACTS_DIR, PROCESSED_DIR, RAW_DIR
from ml.data import preprocess as pp
from ml.data.assistments import load_assistments
from ml.data.schema import NUMERIC_FEATURES, has_real_time
from ml.data.synthetic import SyntheticConfig, generate_synthetic, save_synthetic


def build_dataset(
    df: pd.DataFrame,
    source: str,
    out_dir: Path = PROCESSED_DIR,
    meta_path: Path = ARTIFACTS_DIR / "preprocess_meta.json",
    max_len: int = 100,
    min_events: int = 5,
    seed: int = 42,
) -> dict:
    n_rows_in = len(df)
    df = pp.clean(df, min_events=min_events)
    splits = pp.split_users(df["user_id"].unique(), seed=seed)

    train_df = df[df["user_id"].isin(splits["train"])]
    vocab = pp.fit_vocab(train_df)                       # train only
    seqs = {
        name: pp.build_sequences(df[df["user_id"].isin(users)], vocab)
        for name, users in splits.items()
    }
    stats = pp.fit_normalizer(seqs["train"])             # train only

    out_dir.mkdir(parents=True, exist_ok=True)
    meta_splits, arrays_by_split = {}, {}
    for name, s in seqs.items():
        arrays = pp.make_windows(s, stats, max_len)
        arrays_by_split[name] = arrays
        np.savez_compressed(out_dir / f"{name}.npz", **arrays)
        sub = df[df["user_id"].isin(splits[name])]
        meta_splits[name] = {
            "students": int(len(splits[name])),
            "windows": int(arrays["mask"].shape[0]),
            "interactions": int(len(sub)),
            "positive_rate": pp.positive_rate(arrays),
            "unseen_question_rate": float(
                (arrays["question"][arrays["mask"]] == 1).mean()
            ),
        }

    pos = meta_splits["train"]["positive_rate"]
    meta = {
        "source": source,
        "is_synthetic": source == "synthetic",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": seed,
        "max_len": max_len,
        "min_events": min_events,
        "rows_before_cleaning": int(n_rows_in),
        "rows_after_cleaning": int(len(df)),
        "has_real_time": has_real_time(df),
        "numeric_features": NUMERIC_FEATURES,
        "normalization": stats,
        "n_questions": vocab.n_questions,
        "n_topics": vocab.n_topics,
        "splits": meta_splits,
        "pos_weight": float((1 - pos) / pos) if 0 < pos < 1 else 1.0,
        "split_users": {k: [int(u) for u in v] for k, v in splits.items()},
        "vocab": {
            "question": {str(k): v for k, v in vocab.question.items()},
            "topic": {str(k): v for k, v in vocab.topic.items()},
        },
        "notes": [
            "Split is by student; vocab and normalisation fitted on train students only.",
            "Input at step t uses the previous answer, never answer t (no target leakage).",
        ],
    }
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2))
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--source", choices=["synthetic", "assistments"], required=True)
    ap.add_argument("--csv", type=Path, default=RAW_DIR / "skill_builder_data.csv")
    ap.add_argument("--max-len", type=int, default=100)
    ap.add_argument("--min-events", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-students", type=int, default=1000, help="synthetic only")
    args = ap.parse_args()

    if args.source == "synthetic":
        cfg = SyntheticConfig(n_students=args.n_students, seed=args.seed)
        df = generate_synthetic(cfg)
        save_synthetic(df, cfg, RAW_DIR / "synthetic_interactions.csv")
        print("NOTE: using SIMULATED data. Do not report results as real-student results.")
    else:
        df = load_assistments(args.csv)

    meta = build_dataset(df, args.source, max_len=args.max_len,
                         min_events=args.min_events, seed=args.seed)
    print(f"source={meta['source']}  rows={meta['rows_after_cleaning']:,}  "
          f"questions={meta['n_questions']}  topics={meta['n_topics']}  "
          f"real_time={meta['has_real_time']}")
    for name, s in meta["splits"].items():
        print(f"  {name:5s} students={s['students']:5d} windows={s['windows']:6d} "
              f"interactions={s['interactions']:8d} pos_rate={s['positive_rate']:.3f} "
              f"unseen_q={s['unseen_question_rate']:.3f}")
    print(f"pos_weight (train) = {meta['pos_weight']:.3f}")
    print(f"Wrote tensors to {PROCESSED_DIR} and metadata to {ARTIFACTS_DIR / 'preprocess_meta.json'}")


if __name__ == "__main__":
    main()