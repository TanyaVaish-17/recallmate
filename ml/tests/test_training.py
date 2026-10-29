import json

import numpy as np
import pytest
import torch

from ml.data.build_dataset import build_dataset
from ml.data.synthetic import SyntheticConfig, generate_synthetic
from ml.model.dataset import KTDataset
from ml.model.io import load_checkpoint
from ml.training.baselines import GlobalRate, LogisticBaseline, PreviousAnswer, flatten
from ml.training.metrics import compute_metrics
from ml.training.report import render_markdown
from ml.training.train import TrainConfig, hide_ids, predict, run_training


# ------------------------------- metrics ------------------------------------ #
def test_perfect_predictions():
    m = compute_metrics(np.array([0, 1, 1, 0]), np.array([0.1, 0.9, 0.8, 0.2]))
    assert m["auc"] == 1.0 and m["accuracy"] == 1.0 and m["f1"] == 1.0


def test_known_confusion_matrix():
    y = np.array([1, 1, 0, 0])
    p = np.array([0.9, 0.2, 0.8, 0.1])           # TP=1 FN=1 FP=1 TN=1
    m = compute_metrics(y, p)
    assert m["accuracy"] == 0.5 and m["precision"] == 0.5 and m["recall"] == 0.5
    assert m["f1"] == pytest.approx(0.5)


def test_single_class_auc_is_nan_not_crash():
    m = compute_metrics(np.array([1, 1, 1]), np.array([0.6, 0.7, 0.8]))
    assert np.isnan(m["auc"])


def test_threshold_changes_class_metrics_not_auc():
    y, p = np.array([0, 0, 1, 1]), np.array([0.2, 0.4, 0.6, 0.9])
    a, b = compute_metrics(y, p, 0.5), compute_metrics(y, p, 0.95)
    assert a["auc"] == b["auc"] and a["recall"] > b["recall"]


# ------------------------------- baselines ---------------------------------- #
@pytest.fixture(scope="module")
def built(tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    cfg = SyntheticConfig(n_students=80, n_topics=5, questions_per_topic=6,
                          min_events=30, max_events=60)
    meta = build_dataset(generate_synthetic(cfg), "synthetic", out_dir=d,
                         meta_path=d / "preprocess_meta.json", max_len=32, seed=0)
    return d, meta


def test_baselines_output_valid_probabilities(built):
    d, meta = built
    tr, te = (flatten(dict(np.load(d / f"{s}.npz"))) for s in ("train", "test"))
    for b in (GlobalRate().fit(tr), PreviousAnswer().fit(tr),
              LogisticBaseline(meta["n_topics"]).fit(tr)):
        p = b.predict_proba(te)
        assert p.shape == te["y"].shape and ((p >= 0) & (p <= 1)).all()


def test_previous_answer_rates_come_from_training_data_only():
    flat = {"prev": np.array([0, 2, 2, 1]), "y": np.array([1, 1, 0, 0])}
    b = PreviousAnswer().fit(flat)
    assert b.rates == {0: 1.0, 1: 0.0, 2: 0.5}
    test = {"prev": np.array([2, 1]), "y": np.array([0, 0])}   # test labels are never read
    assert b.predict_proba(test).tolist() == [0.5, 0.0]


def test_previous_answer_handles_unseen_category():
    b = PreviousAnswer().fit({"prev": np.array([2, 2]), "y": np.array([1, 0])})
    assert b.rates[1] == 0.5  # falls back to global rate


# ------------------------------ id hiding ----------------------------------- #
def test_hide_ids_only_touches_selected_windows_and_real_steps(built):
    d, _ = built
    ds = KTDataset(d / "train.npz")
    batch = {k: v[:4] for k, v in ds.t.items()}
    out = hide_ids(batch, torch.tensor([True, False, False, False]))
    sel = batch["mask"][0]
    assert (out["question"][0][sel] == 1).all() and (out["topic"][0][sel] == 1).all()
    assert (out["question"][0][~sel] == 0).all()                 # padding stays PAD
    assert torch.equal(out["question"][1:], batch["question"][1:])
    assert torch.equal(out["numeric"], batch["numeric"])          # numeric features untouched


# --------------------------- end-to-end training ---------------------------- #
def _cfg(built, out, seed=0):
    d, _ = built
    return TrainConfig(data_dir=d, meta_path=d / "preprocess_meta.json", out_dir=out,
                       epochs=4, batch_size=16, d_model=16, n_heads=2, n_layers=1, d_ff=32,
                       patience=3, seed=seed, device="cpu")


def test_training_produces_checkpoint_and_honest_results(built, tmp_path):
    r = run_training(_cfg(built, tmp_path))
    assert (tmp_path / "kt_transformer.pt").exists()
    saved = json.loads((tmp_path / "results.json").read_text())
    for key in ("transformer_val", "transformer_test", "transformer_test_id_free",
                "baseline_logistic", "baseline_previous_answer", "baseline_global_rate"):
        assert 0 <= saved[key]["auc"] <= 1
    assert saved["dataset"]["is_synthetic"] is True
    md = (tmp_path / "results.md").read_text()
    assert "SYNTHETIC DATA" in md and "NOT results on real students" in md
    assert r["training"]["best_epoch"] >= 1


def test_checkpoint_reload_reproduces_reported_test_metrics(built, tmp_path):
    d, _ = built
    r = run_training(_cfg(built, tmp_path))
    model, ckpt = load_checkpoint(tmp_path / "kt_transformer.pt")
    assert ckpt["model_version"] == r["model_version"] and ckpt["is_synthetic"] is True
    from torch.utils.data import DataLoader
    y, p, _ = predict(model, DataLoader(KTDataset(d / "test.npz"), batch_size=64), "cpu")
    assert compute_metrics(y, p)["auc"] == pytest.approx(r["transformer_test"]["auc"], abs=1e-6)


def test_same_seed_gives_same_result(built, tmp_path):
    a = run_training(_cfg(built, tmp_path / "a", seed=3))
    b = run_training(_cfg(built, tmp_path / "b", seed=3))
    assert a["transformer_test"]["auc"] == pytest.approx(b["transformer_test"]["auc"], abs=1e-5)


def test_missing_checkpoint_gives_not_trained_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="Train one first"):
        load_checkpoint(tmp_path / "nope.pt")


def test_missing_preprocess_meta_gives_helpful_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="build_dataset"):
        run_training(TrainConfig(meta_path=tmp_path / "x.json", out_dir=tmp_path))