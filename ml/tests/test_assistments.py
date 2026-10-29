import numpy as np
import pandas as pd
import pytest

from ml.data.assistments import load_assistments


def _write(tmp_path, rows, encoding="latin-1"):
    cols = ["order_id", "user_id", "problem_id", "skill_id", "correct", "original", "skill_name"]
    p = tmp_path / "skill_builder_data.csv"
    pd.DataFrame(rows, columns=cols).to_csv(p, index=False, encoding=encoding)
    return p


def test_filters_and_dedups(tmp_path):
    rows = [
        # order, user, problem, skill, correct, original, name
        (3, 1, 10, 5, 1, 1, "Café"),      # non-ascii skill name (latin-1)
        (1, 1, 11, 5, 0, 1, "a"),
        (1, 1, 11, 6, 0, 1, "b"),         # duplicate order_id (second skill tag) -> dropped
        (2, 1, 12, 5, 1, 0, "scaffold"),  # scaffolding -> dropped
        (4, 1, 13, np.nan, 1, 1, "x"),    # no skill -> dropped
        (5, 2, 14, 7, 1, 1, "y"),
    ]
    df = load_assistments(_write(tmp_path, rows))
    assert df["order"].tolist() == [1, 3, 5]          # sorted per user, filtered
    assert df["user_id"].tolist() == [1, 1, 2]
    assert df["timestamp_h"].isna().all()             # dataset has no clock
    assert (df["revised_since_last"] == 0).all()


def test_missing_file_gives_helpful_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="Download"):
        load_assistments(tmp_path / "nope.csv")


def test_missing_columns_rejected(tmp_path):
    p = tmp_path / "bad.csv"
    pd.DataFrame({"foo": [1]}).to_csv(p, index=False)
    with pytest.raises(ValueError, match="missing expected columns"):
        load_assistments(p)