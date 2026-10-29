import json

import numpy as np
import pandas as pd
import pytest

from ml.data import preprocess as pp
from ml.data.build_dataset import build_dataset
from ml.data.schema import PAD, PREV_NONE, PREV_RIGHT, PREV_WRONG, UNK
from ml.data.synthetic import SyntheticConfig, generate_synthetic

SMALL = SyntheticConfig(n_students=60, n_topics=5, questions_per_topic=6, min_events=20, max_events=60)


@pytest.fixture(scope="module")
def df():
    return generate_synthetic(SMALL)


# ---------------------------- splitting / vocab ---------------------------- #
def test_split_is_disjoint_and_complete(df):
    s = pp.split_users(df["user_id"].unique(), seed=1)
    train, val, test = set(s["train"]), set(s["val"]), set(s["test"])
    assert not (train & val) and not (train & test) and not (val & test)
    assert train | val | test == set(df["user_id"].unique())


def test_split_is_reproducible(df):
    a = pp.split_users(df["user_id"].unique(), seed=3)
    b = pp.split_users(df["user_id"].unique(), seed=3)
    assert all((a[k] == b[k]).all() for k in a)


def test_vocab_fitted_on_train_only_unseen_maps_to_unk():
    train = pd.DataFrame({"question_id": [100, 101], "topic_id": [1, 1]})
    vocab = pp.fit_vocab(train)
    assert vocab.encode_questions(np.array([100, 999])).tolist() == [2, UNK]
    assert vocab.n_questions == 4  # PAD, UNK, 100, 101


def test_short_students_are_dropped(df):
    short = df[df["user_id"] == 0].head(3)
    out = pp.clean(pd.concat([df, short.assign(user_id=9999)]), min_events=5)
    assert 9999 not in set(out["user_id"])


# ----------------------------- feature maths ------------------------------- #
def _features(correct, topic=(1, 1, 1, 1), question=(10, 10, 11, 10), ts=(0.0, 1.0, 3.0, 4.0),
              revised=(0, 0, 0, 1)):
    return pp.user_features(np.array(question), np.array(topic), np.array(correct),
                            np.array(ts, dtype=float), np.array(revised))


def test_prev_correct_is_shifted():
    prev, _ = _features([1, 0, 1, 1])
    assert prev.tolist() == [PREV_NONE, PREV_RIGHT, PREV_WRONG, PREV_RIGHT]


def test_gap_attempt_and_count_features():
    _, num = _features([1, 0, 1, 1])
    log1p = np.log1p
    np.testing.assert_allclose(num[:, 0], [0, log1p(1), log1p(2), log1p(1)])   # gap to previous
    np.testing.assert_allclose(num[:, 1], [0, log1p(1), log1p(2), log1p(1)])   # same topic here
    np.testing.assert_allclose(num[:, 2], [0, log1p(1), 0, log1p(2)])          # prior tries of question
    np.testing.assert_allclose(num[:, 3], [0, log1p(1), log1p(2), log1p(3)])   # prior tries of topic
    assert num[:, 4].tolist() == [0, 0, 0, 1]


def test_same_topic_gap_skips_other_topics():
    _, num = _features([1, 1, 1, 1], topic=(1, 2, 1, 2), ts=(0.0, 1.0, 10.0, 11.0))
    np.testing.assert_allclose(num[2, 1], np.log1p(10.0))   # topic 1 last seen at t=0
    np.testing.assert_allclose(num[3, 1], np.log1p(10.0))   # topic 2 last seen at t=1


def test_no_clock_gives_zero_gaps():
    _, num = _features([1, 0, 1, 1], ts=(np.nan,) * 4)
    assert (num[:, :2] == 0).all()


# ------------------------- TEMPORAL LEAKAGE CHECK -------------------------- #
@pytest.mark.parametrize("t", [0, 2, 5])
def test_changing_answer_t_never_changes_features_up_to_t(t):
    n = 8
    rng = np.random.default_rng(0)
    q, tp = rng.integers(0, 4, n), rng.integers(0, 2, n)
    ts, rev = np.cumsum(rng.random(n)), rng.integers(0, 2, n)
    correct = rng.integers(0, 2, n)

    flipped = correct.copy()
    flipped[t] = 1 - flipped[t]

    p1, n1 = pp.user_features(q, tp, correct, ts, rev)
    p2, n2 = pp.user_features(q, tp, flipped, ts, rev)

    # Inputs at steps 0..t are identical: the answer at t is never an input at t.
    assert (p1[: t + 1] == p2[: t + 1]).all()
    np.testing.assert_array_equal(n1[: t + 1], n2[: t + 1])
    # ...and the answer does legitimately influence the NEXT step.
    if t + 1 < n:
        assert p1[t + 1] != p2[t + 1]


def test_features_use_only_past_not_future():
    rng = np.random.default_rng(1)
    n = 8
    q, tp = rng.integers(0, 4, n), rng.integers(0, 2, n)
    ts, rev, correct = np.cumsum(rng.random(n)), rng.integers(0, 2, n), rng.integers(0, 2, n)
    full_p, full_n = pp.user_features(q, tp, correct, ts, rev)
    k = 5  # truncating the future must not alter any earlier feature
    cut_p, cut_n = pp.user_features(q[:k], tp[:k], correct[:k], ts[:k], rev[:k])
    assert (full_p[:k] == cut_p).all()
    np.testing.assert_array_equal(full_n[:k], cut_n)


# ------------------------------ tensors ------------------------------------ #
def _arrays(df, max_len=16):
    s = pp.split_users(df["user_id"].unique())
    train_df = df[df["user_id"].isin(s["train"])]
    vocab = pp.fit_vocab(train_df)
    seqs = pp.build_sequences(train_df, vocab)
    stats = pp.fit_normalizer(seqs)
    return pp.make_windows(seqs, stats, max_len), seqs, stats, vocab


def test_shapes_dtypes_and_padding(df):
    a, *_ = _arrays(df, max_len=16)
    n = a["mask"].shape[0]
    assert a["question"].shape == a["topic"].shape == a["target"].shape == (n, 16)
    assert a["numeric"].shape == (n, 16, 5)
    assert a["question"].dtype == np.int64 and a["numeric"].dtype == np.float32
    pad = ~a["mask"]
    assert (a["question"][pad] == PAD).all() and (a["target"][pad] == 0).all()
    assert (a["question"][a["mask"]] != PAD).all()
    # right-padding only: mask is True then False
    assert all((np.diff(m.astype(int)) <= 0).all() for m in a["mask"])


def test_target_alignment_and_window_continuity(df):
    a, seqs, _, _ = _arrays(df, max_len=16)
    s = next(x for x in seqs if len(x.target) > 16)
    rows = np.where(a["user_ids"] == s.user_id)[0]
    assert len(rows) >= 2
    first, second = rows[0], rows[1]
    np.testing.assert_array_equal(a["target"][first, :16], s.target[:16])
    # 2nd window starts mid-history: its first prev_correct is the REAL previous answer.
    expected = PREV_RIGHT if s.target[15] == 1 else PREV_WRONG
    assert a["prev_correct"][second, 0] == expected


def test_normalisation_uses_train_statistics(df):
    a, seqs, stats, _ = _arrays(df)
    m = a["mask"]
    standardized = a["numeric"][m][:, :4]
    np.testing.assert_allclose(standardized.mean(axis=0), 0, atol=0.05)
    np.testing.assert_allclose(standardized.std(axis=0), 1, atol=0.05)


def test_constant_feature_does_not_divide_by_zero():
    d = generate_synthetic(SMALL).assign(timestamp_h=np.nan)  # like ASSISTments
    a, *_ = _arrays(d)
    assert np.isfinite(a["numeric"]).all()


# ------------------------------ end to end --------------------------------- #
def test_build_dataset_end_to_end(df, tmp_path):
    meta = build_dataset(df, "synthetic", out_dir=tmp_path / "p",
                         meta_path=tmp_path / "meta.json", max_len=16, seed=5)
    for name in ("train", "val", "test"):
        z = np.load(tmp_path / "p" / f"{name}.npz")
        assert {"question", "topic", "prev_correct", "numeric", "target", "mask"} <= set(z.files)
    saved = json.loads((tmp_path / "meta.json").read_text())
    assert saved["is_synthetic"] is True
    assert saved["has_real_time"] is True
    train_users = set(saved["split_users"]["train"])
    assert not train_users & set(saved["split_users"]["test"])
    assert 0 < saved["pos_weight"] < 10
    assert meta["n_questions"] >= 3