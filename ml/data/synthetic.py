"""Synthetic student-interaction generator (DEVELOPMENT / TESTING ONLY).

!! This data is simulated. Results measured on it must never be described as
!! results on real students. Use ml.data.assistments for real data.

Simulation model (deliberately simple and documented so it can be defended in a viva):

    P(correct) = sigmoid( ability + effective_mastery(topic, t) - question_difficulty )

* ability                 per-student constant ~ N(0.3, 0.8)
* question_difficulty     topic offset + per-question noise
* mastery (per topic)     grows after each attempt (more when the answer was correct)
* forgetting              effective_mastery = mastery * exp(-hours_since_last_touch / stability)
* stability               grows with practice, so well-practised topics decay slower
* revision sessions       randomly inserted; they add mastery and reset the decay clock

Because forgetting and revision are baked in, a model that uses time gaps and the
revision flag *should* beat one that only sees the previous answer. That is the
property we want the dev dataset to exercise.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ml.data.schema import CANONICAL_COLUMNS


@dataclass
class SyntheticConfig:
    n_students: int = 1000
    n_topics: int = 20
    questions_per_topic: int = 15
    min_events: int = 40
    max_events: int = 200
    seed: int = 42


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


def generate_synthetic(cfg: SyntheticConfig | None = None) -> pd.DataFrame:
    cfg = cfg or SyntheticConfig()
    rng = np.random.default_rng(cfg.seed)

    n_q = cfg.n_topics * cfg.questions_per_topic
    q_topic = np.repeat(np.arange(cfg.n_topics), cfg.questions_per_topic)
    topic_difficulty = rng.normal(0.0, 0.6, cfg.n_topics)
    q_difficulty = topic_difficulty[q_topic] + rng.normal(0.0, 0.5, n_q)

    rows: list[tuple] = []
    for user in range(cfg.n_students):
        ability = rng.normal(0.3, 0.8)
        learn_rate = rng.uniform(0.08, 0.30)
        base_stability = rng.uniform(20.0, 120.0)  # hours

        mastery = np.zeros(cfg.n_topics)
        practice = np.zeros(cfg.n_topics)
        last_touch = np.full(cfg.n_topics, np.nan)
        revised_flag = np.zeros(cfg.n_topics, dtype=bool)

        def effective(topic: int, now: float) -> float:
            if np.isnan(last_touch[topic]):
                return 0.0
            stability = base_stability * (1.0 + 0.3 * practice[topic])
            return float(mastery[topic] * np.exp(-(now - last_touch[topic]) / stability))

        n_events = int(rng.integers(cfg.min_events, cfg.max_events + 1))
        now = 0.0
        topic = int(rng.integers(cfg.n_topics))

        for k in range(n_events):
            if k > 0:
                if rng.random() < 0.12:  # a new study session after a break
                    now += float(rng.exponential(48.0))
                    if rng.random() < 0.30:  # a revision session on a random topic
                        rt = int(rng.integers(cfg.n_topics))
                        mastery[rt] = min(effective(rt, now) + 0.6, 4.0)
                        last_touch[rt] = now
                        revised_flag[rt] = True
                    if rng.random() < 0.5:
                        topic = int(rng.integers(cfg.n_topics))
                else:
                    now += float(rng.exponential(0.05))  # a few minutes between questions
                    if rng.random() < 0.3:
                        topic = int(rng.integers(cfg.n_topics))

            q = int(topic * cfg.questions_per_topic + rng.integers(cfg.questions_per_topic))
            eff = effective(topic, now)
            p = _sigmoid(ability + eff - q_difficulty[q])
            correct = int(rng.random() < p)

            gain = learn_rate * (1.5 if correct else 1.0)
            mastery[topic] = min(eff + gain, 4.0)
            practice[topic] += 1
            last_touch[topic] = now

            rows.append((user, k, q, topic, correct, now, int(revised_flag[topic])))
            revised_flag[topic] = False

    return pd.DataFrame(rows, columns=CANONICAL_COLUMNS)


def save_synthetic(df: pd.DataFrame, cfg: SyntheticConfig, out_csv: Path) -> Path:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    meta = {
        "source": "synthetic",
        "WARNING": "SIMULATED DATA. Not real students. Do not report as real-data results.",
        "config": asdict(cfg),
        "rows": int(len(df)),
    }
    out_csv.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))
    return out_csv