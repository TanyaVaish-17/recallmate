import json

import numpy as np

from ml.data.schema import CANONICAL_COLUMNS, validate_canonical
from ml.data.synthetic import SyntheticConfig, generate_synthetic, save_synthetic

SMALL = SyntheticConfig(n_students=30, n_topics=5, questions_per_topic=6, min_events=20, max_events=40)


def test_schema_valid_and_sorted():
    df = generate_synthetic(SMALL)
    assert list(df.columns) == CANONICAL_COLUMNS
    validate_canonical(df)
    for _, g in df.groupby("user_id"):
        assert g["timestamp_h"].is_monotonic_increasing


def test_reproducible_with_seed():
    a, b = generate_synthetic(SMALL), generate_synthetic(SMALL)
    assert a.equals(b)


def test_different_seed_differs():
    other = SyntheticConfig(**{**SMALL.__dict__, "seed": 7})
    assert not generate_synthetic(SMALL).equals(generate_synthetic(other))


def test_correct_rate_is_plausible():
    rate = generate_synthetic(SMALL)["correct"].mean()
    assert 0.3 < rate < 0.9


def test_revision_flags_present():
    df = generate_synthetic(SyntheticConfig(n_students=100, n_topics=5, questions_per_topic=6))
    assert df["revised_since_last"].sum() > 0


def test_sidecar_marks_data_as_synthetic(tmp_path):
    df = generate_synthetic(SMALL)
    csv = save_synthetic(df, SMALL, tmp_path / "s.csv")
    meta = json.loads(csv.with_suffix(".meta.json").read_text())
    assert meta["source"] == "synthetic"
    assert "SIMULATED" in meta["WARNING"]