import numpy as np
import pytest
import torch

from ml.data.build_dataset import build_dataset
from ml.data.synthetic import SyntheticConfig, generate_synthetic
from ml.model import KTTransformer, ModelConfig, masked_bce_with_logits
from ml.model.dataset import KTDataset

B, L = 4, 12
CFG = ModelConfig(n_questions=30, n_topics=8, max_len=L, d_model=32, n_heads=4,
                  n_layers=2, d_ff=64, dropout=0.1)


def make_batch(seed=0, b=B, l=L):
    g = torch.Generator().manual_seed(seed)
    return {
        "question": torch.randint(2, CFG.n_questions, (b, l), generator=g),
        "topic": torch.randint(2, CFG.n_topics, (b, l), generator=g),
        "prev_correct": torch.randint(0, 3, (b, l), generator=g),
        "numeric": torch.randn(b, l, CFG.n_numeric, generator=g),
    }


def model(seed=0):
    torch.manual_seed(seed)
    return KTTransformer(CFG).eval()


# ------------------------------ shapes -------------------------------------- #
def test_output_shape_and_probability_range():
    m = model()
    logits = m(make_batch())
    assert logits.shape == (B, L)
    p = m.predict_proba(make_batch())
    assert p.shape == (B, L) and ((p >= 0) & (p <= 1)).all()


def test_attention_shapes_one_per_layer():
    _, attns = model()(make_batch(), return_attn=True)
    assert len(attns) == CFG.n_layers
    assert attns[0].shape == (B, CFG.n_heads, L, L)


def test_rejects_too_long_sequence():
    with pytest.raises(ValueError, match="max_len"):
        model()(make_batch(l=L + 1))


def test_d_model_must_divide_by_heads():
    with pytest.raises(ValueError):
        ModelConfig(n_questions=5, n_topics=5, d_model=30, n_heads=4)


# ------------------------------ CAUSALITY ----------------------------------- #
def test_attention_is_causal_and_rows_sum_to_one():
    _, attns = model()(make_batch(), return_attn=True)
    for a in attns:
        assert torch.allclose(a.sum(-1), torch.ones(B, CFG.n_heads, L), atol=1e-5)
        upper = torch.triu(torch.ones(L, L, dtype=torch.bool), diagonal=1)
        assert (a[:, :, upper] == 0).all()   # exactly zero weight on the future


@pytest.mark.parametrize("t", [0, 3, 8])
def test_future_inputs_never_change_earlier_outputs(t):
    m = model()
    base = make_batch()
    out1 = m(base)

    changed = {k: v.clone() for k, v in base.items()}
    changed["question"][:, t + 1 :] = 2
    changed["prev_correct"][:, t + 1 :] = 1
    changed["numeric"][:, t + 1 :] += 5.0
    out2 = m(changed)

    assert torch.allclose(out1[:, : t + 1], out2[:, : t + 1], atol=1e-6)
    if t + 1 < L:
        assert not torch.allclose(out1[:, t + 1 :], out2[:, t + 1 :])  # model does use inputs


def test_past_inputs_do_influence_later_outputs():
    m = model()
    base = make_batch()
    changed = {k: v.clone() for k, v in base.items()}
    changed["prev_correct"][:, 2] = (changed["prev_correct"][:, 2] + 1) % 3
    assert not torch.allclose(m(base)[:, 5:], m(changed)[:, 5:])


def test_padding_content_cannot_leak_into_real_steps():
    m = model()
    base = make_batch()
    k = 7  # steps >= k are "padding"
    other = {key: v.clone() for key, v in base.items()}
    other["question"][:, k:] = 0
    other["topic"][:, k:] = 0
    other["numeric"][:, k:] = 0.0
    assert torch.allclose(m(base)[:, :k], m(other)[:, :k], atol=1e-6)


# ------------------------------- loss --------------------------------------- #
def test_masked_loss_ignores_padding():
    logits = torch.tensor([[2.0, -1.0, 100.0]])
    target = torch.tensor([[1.0, 0.0, 0.0]])
    mask = torch.tensor([[True, True, False]])   # third step is padding with a huge error
    expected = torch.nn.functional.binary_cross_entropy_with_logits(
        logits[:, :2], target[:, :2])
    assert torch.allclose(masked_bce_with_logits(logits, target, mask), expected)


def test_pos_weight_increases_loss_on_positives():
    logits, target = torch.zeros(1, 2), torch.tensor([[1.0, 0.0]])
    mask = torch.ones(1, 2, dtype=torch.bool)
    assert masked_bce_with_logits(logits, target, mask, pos_weight=3.0) > \
        masked_bce_with_logits(logits, target, mask)


def test_all_padding_batch_gives_zero_not_nan():
    loss = masked_bce_with_logits(torch.zeros(1, 3), torch.zeros(1, 3),
                                  torch.zeros(1, 3, dtype=torch.bool))
    assert loss.item() == 0.0


# ----------------------------- config / params ------------------------------ #
def test_config_roundtrip_and_parameter_count():
    assert ModelConfig.from_dict(CFG.to_dict()) == CFG
    assert model().n_parameters() > 0


def test_state_dict_roundtrip_gives_identical_predictions():
    a = model(seed=1)
    b = KTTransformer(CFG).eval()
    b.load_state_dict(a.state_dict())
    x = make_batch()
    assert torch.allclose(a(x), b(x))


# ------------------------- training sanity (end to end) --------------------- #
def test_model_learns_on_real_pipeline_output(tmp_path):
    cfg = SyntheticConfig(n_students=40, n_topics=4, questions_per_topic=5,
                          min_events=30, max_events=50)
    meta = build_dataset(generate_synthetic(cfg), "synthetic", out_dir=tmp_path,
                         meta_path=tmp_path / "m.json", max_len=24, seed=0)
    ds = KTDataset(tmp_path / "train.npz")
    assert len(ds) > 0
    batch = {k: v[:16] for k, v in ds.t.items()}

    torch.manual_seed(0)
    mcfg = ModelConfig(n_questions=meta["n_questions"], n_topics=meta["n_topics"],
                       max_len=24, d_model=32, n_heads=4, n_layers=2, d_ff=64, dropout=0.0)
    m = KTTransformer(mcfg)
    opt = torch.optim.Adam(m.parameters(), lr=3e-3)

    first = last = None
    for step in range(60):
        loss = masked_bce_with_logits(m(batch), batch["target"], batch["mask"])
        opt.zero_grad(); loss.backward(); opt.step()
        first = loss.item() if first is None else first
        last = loss.item()
    assert last < first * 0.8, f"loss did not fall enough: {first:.3f} -> {last:.3f}"