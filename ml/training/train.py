"""Train the Transformer, compare with baselines, write checkpoint + results.

    python -m ml.training.train                       # defaults
    python -m ml.training.train --epochs 40 --d-model 96 --seed 1

Outputs (in ml/artifacts/):
    kt_transformer.pt      best checkpoint by validation AUC (git-ignored)
    results.json           every measured number (commit this)
    results.md             readable report generated from results.json (commit this)
"""
from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from ml.config import ARTIFACTS_DIR, PROCESSED_DIR
from ml.data.schema import UNK
from ml.model.dataset import KTDataset
from ml.model.io import load_checkpoint, save_checkpoint
from ml.model.loss import masked_bce_with_logits
from ml.model.transformer import KTTransformer, ModelConfig
from ml.training.baselines import GlobalRate, LogisticBaseline, PreviousAnswer, flatten
from ml.training.metrics import compute_metrics
from ml.training.report import write_report


@dataclass
class TrainConfig:
    data_dir: Path = PROCESSED_DIR
    meta_path: Path = ARTIFACTS_DIR / "preprocess_meta.json"
    out_dir: Path = ARTIFACTS_DIR
    epochs: int = 30
    batch_size: int = 32
    lr: float = 1e-3
    weight_decay: float = 1e-2
    d_model: int = 64
    n_heads: int = 4
    n_layers: int = 2
    d_ff: int = 128
    dropout: float = 0.1
    patience: int = 5
    grad_clip: float = 1.0
    use_pos_weight: bool = False   # re-weighting distorts probabilities; off by default
    id_dropout: float = 0.25       # fraction of windows whose question/topic ids are hidden
    threshold: float = 0.5
    seed: int = 42
    device: str = "auto"

    def public(self) -> dict:
        d = asdict(self)
        for k in ("data_dir", "meta_path", "out_dir"):
            d.pop(k)
        return d


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def to_device(batch: dict, device) -> dict:
    return {k: v.to(device) for k, v in batch.items()}


def hide_ids(batch: dict, which: torch.Tensor) -> dict:
    """Replace question/topic ids with UNK for the windows selected by boolean `which` (B,)."""
    if not which.any():
        return batch
    sel = which[:, None] & batch["mask"]
    out = dict(batch)
    out["question"] = torch.where(sel, torch.full_like(batch["question"], UNK), batch["question"])
    out["topic"] = torch.where(sel, torch.full_like(batch["topic"], UNK), batch["topic"])
    return out


@torch.no_grad()
def predict(model, loader, device, id_free: bool = False):
    """Return (y_true, y_prob, mean_bce) over real steps."""
    model.eval()
    ys, ps, total, n = [], [], 0.0, 0
    for batch in loader:
        batch = to_device(batch, device)
        if id_free:
            batch = hide_ids(batch, torch.ones(len(batch["mask"]), dtype=torch.bool, device=device))
        logits = model(batch)
        m = batch["mask"]
        k = int(m.sum())
        total += masked_bce_with_logits(logits, batch["target"], m).item() * k
        n += k
        ys.append(batch["target"][m].cpu().numpy())
        ps.append(torch.sigmoid(logits)[m].cpu().numpy())
    return np.concatenate(ys), np.concatenate(ps), total / max(n, 1)


def run_training(cfg: TrainConfig) -> dict:
    t0 = time.time()
    set_seed(cfg.seed)
    device = torch.device("cuda" if cfg.device == "auto" and torch.cuda.is_available()
                          else "cpu" if cfg.device == "auto" else cfg.device)

    meta_path = Path(cfg.meta_path)
    if not meta_path.exists():
        raise FileNotFoundError(f"{meta_path} missing. Run `python -m ml.data.build_dataset` first.")
    meta = json.loads(meta_path.read_text())

    gen = torch.Generator().manual_seed(cfg.seed)
    ds = {s: KTDataset(Path(cfg.data_dir) / f"{s}.npz") for s in ("train", "val", "test")}
    train_loader = DataLoader(ds["train"], batch_size=cfg.batch_size, shuffle=True, generator=gen)
    val_loader = DataLoader(ds["val"], batch_size=128)
    test_loader = DataLoader(ds["test"], batch_size=128)

    mcfg = ModelConfig(
        n_questions=meta["n_questions"], n_topics=meta["n_topics"], max_len=meta["max_len"],
        d_model=cfg.d_model, n_heads=cfg.n_heads, n_layers=cfg.n_layers,
        d_ff=cfg.d_ff, dropout=cfg.dropout,
    )
    model = KTTransformer(mcfg).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    pos_weight = meta["pos_weight"] if cfg.use_pos_weight else None

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    version = f"kt-transformer-{meta['source']}-{stamp}"
    ckpt_path = Path(cfg.out_dir) / "kt_transformer.pt"
    ckpt_extra = {
        "dataset_source": meta["source"],
        "is_synthetic": meta["is_synthetic"],
        "max_len": meta["max_len"],
        "numeric_features": meta["numeric_features"],
        "normalization": meta["normalization"],
        "seed": cfg.seed,
    }

    history, best_score, best_epoch, bad = [], -float("inf"), 0, 0
    for epoch in range(1, cfg.epochs + 1):
        model.train()
        tot, cnt = 0.0, 0
        for batch in train_loader:
            batch = to_device(batch, device)
            if cfg.id_dropout > 0:
                batch = hide_ids(batch, torch.rand(len(batch["mask"]), device=device) < cfg.id_dropout)
            loss = masked_bce_with_logits(model(batch), batch["target"], batch["mask"], pos_weight)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
            opt.step()
            k = int(batch["mask"].sum())
            tot, cnt = tot + loss.item() * k, cnt + k

        y, p, val_loss = predict(model, val_loader, device)
        val = compute_metrics(y, p, cfg.threshold)
        history.append({"epoch": epoch, "train_loss": tot / max(cnt, 1),
                        "val_loss": val_loss, "val_auc": val["auc"]})
        score = val["auc"] if np.isfinite(val["auc"]) else -val_loss
        print(f"epoch {epoch:3d}  train_loss {tot / max(cnt, 1):.4f}  "
              f"val_loss {val_loss:.4f}  val_auc {val['auc']:.4f}")
        if score > best_score + 1e-4:
            best_score, best_epoch, bad = score, epoch, 0
            save_checkpoint(ckpt_path, model, version, {**ckpt_extra, "best_epoch": epoch,
                                                        "val_auc": val["auc"]})
        else:
            bad += 1
            if bad >= cfg.patience:
                print(f"early stopping at epoch {epoch}")
                break

    # ---- final evaluation with the BEST checkpoint; test set touched only here ----
    best, _ = load_checkpoint(ckpt_path, str(device))
    yv, pv, _ = predict(best, val_loader, device)
    yt, pt, _ = predict(best, test_loader, device)
    yf, pf, _ = predict(best, test_loader, device, id_free=True)

    flat = {s: flatten(dict(np.load(Path(cfg.data_dir) / f"{s}.npz"))) for s in ("train", "test")}
    base = {
        "baseline_global_rate": GlobalRate().fit(flat["train"]),
        "baseline_previous_answer": PreviousAnswer().fit(flat["train"]),
        "baseline_logistic": LogisticBaseline(meta["n_topics"]).fit(flat["train"]),
    }
    results = {
        "model_version": version,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": {k: meta[k] for k in ("source", "is_synthetic", "has_real_time", "splits",
                                          "max_len", "n_questions", "n_topics")},
        "config": cfg.public(),
        "threshold": cfg.threshold,
        "device": str(device),
        "torch_version": torch.__version__,
        "n_parameters": best.n_parameters(),
        "model_config": mcfg.to_dict(),
        "training": {
            "epochs_run": len(history), "best_epoch": best_epoch,
            "best_val_auc": history[best_epoch - 1]["val_auc"],
            "seconds": time.time() - t0, "history": history,
        },
        "transformer_val": compute_metrics(yv, pv, cfg.threshold),
        "transformer_test": compute_metrics(yt, pt, cfg.threshold),
        "transformer_test_id_free": compute_metrics(yf, pf, cfg.threshold),
    }
    for name, b in base.items():
        results[name] = compute_metrics(flat["test"]["y"], b.predict_proba(flat["test"]), cfg.threshold)

    out = Path(cfg.out_dir)
    (out / "results.json").write_text(json.dumps(results, indent=2))
    write_report(results, out / "results.md")
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    d = TrainConfig()
    ap.add_argument("--epochs", type=int, default=d.epochs)
    ap.add_argument("--batch-size", type=int, default=d.batch_size)
    ap.add_argument("--lr", type=float, default=d.lr)
    ap.add_argument("--weight-decay", type=float, default=d.weight_decay)
    ap.add_argument("--d-model", type=int, default=d.d_model)
    ap.add_argument("--n-heads", type=int, default=d.n_heads)
    ap.add_argument("--n-layers", type=int, default=d.n_layers)
    ap.add_argument("--d-ff", type=int, default=d.d_ff)
    ap.add_argument("--dropout", type=float, default=d.dropout)
    ap.add_argument("--patience", type=int, default=d.patience)
    ap.add_argument("--id-dropout", type=float, default=d.id_dropout)
    ap.add_argument("--use-pos-weight", action="store_true")
    ap.add_argument("--seed", type=int, default=d.seed)
    ap.add_argument("--device", default=d.device, help="auto | cpu | cuda")
    a = vars(ap.parse_args())
    r = run_training(TrainConfig(**a))
    print("\n=== TEST RESULTS ===  (dataset: %s%s)" % (
        r["dataset"]["source"], ", SIMULATED" if r["dataset"]["is_synthetic"] else ""))
    for k in ("transformer_test", "transformer_test_id_free", "baseline_logistic",
              "baseline_previous_answer", "baseline_global_rate"):
        m = r[k]
        print(f"{k:28s} AUC {m['auc']:.4f}  acc {m['accuracy']:.4f}  F1 {m['f1']:.4f}")
    print(f"Saved checkpoint, results.json and results.md to {ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()