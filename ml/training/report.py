"""Render results.json into a human-readable markdown report (measured values only)."""
from __future__ import annotations

import json
from pathlib import Path

ROWS = [
    ("Transformer (test)", "transformer_test"),
    ("Transformer, ids hidden (test)", "transformer_test_id_free"),
    ("Logistic regression (test)", "baseline_logistic"),
    ("Previous-answer rate (test)", "baseline_previous_answer"),
    ("Global rate (test)", "baseline_global_rate"),
]


def _f(x) -> str:
    return "n/a" if x is None or x != x else f"{x:.4f}"


def render_markdown(r: dict) -> str:
    d = r["dataset"]
    out = ["# RecallMate experiment results", ""]
    if d["is_synthetic"]:
        out += ["> **SYNTHETIC DATA.** These numbers come from simulated students and are a",
                "> development check only. They are NOT results on real students.", ""]
    out += [
        "## Dataset",
        f"- Source: `{d['source']}`",
        f"- Students (train/val/test): {d['splits']['train']['students']} / "
        f"{d['splits']['val']['students']} / {d['splits']['test']['students']}",
        f"- Interactions (train/val/test): {d['splits']['train']['interactions']:,} / "
        f"{d['splits']['val']['interactions']:,} / {d['splits']['test']['interactions']:,}",
        f"- Real timestamps available: {d['has_real_time']}",
        f"- Train positive rate: {d['splits']['train']['positive_rate']:.3f}",
        "- Split is by student; vocabularies and normalisation fitted on train only.",
        "",
        "## Test-set results (threshold "
        f"{r['threshold']} for accuracy/precision/recall/F1; AUC is threshold-free)",
        "",
        "| Model | AUC | Accuracy | Precision | Recall | F1 | Log loss | Brier |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for label, key in ROWS:
        m = r.get(key)
        if m:
            out.append(f"| {label} | {_f(m['auc'])} | {_f(m['accuracy'])} | {_f(m['precision'])} | "
                       f"{_f(m['recall'])} | {_f(m['f1'])} | {_f(m['log_loss'])} | {_f(m['brier'])} |")
    t = r["training"]
    out += [
        "",
        '"ids hidden" replaces every question/topic id with UNK at test time. It simulates',
        "applying the model to a question bank it has never seen (as RecallMate does).",
        "",
        "## Training",
        f"- Model version: `{r['model_version']}`  ({r['n_parameters']:,} parameters)",
        f"- Device: {r['device']}, torch {r['torch_version']}, seed {r['config']['seed']}",
        f"- Epochs run: {t['epochs_run']} (best epoch {t['best_epoch']}, "
        f"best val AUC {_f(t['best_val_auc'])}); wall time {t['seconds']:.1f}s",
        f"- Validation AUC at best epoch: {_f(r['transformer_val']['auc'])} "
        "(used for model selection; test set was evaluated once, afterwards)",
        "",
        "## Hyperparameters",
        "```json",
        json.dumps(r["config"], indent=2),
        "```",
        "",
        "## Reproduce",
        "```bash",
        "python -m ml.data.build_dataset --source " + d["source"],
        "python -m ml.training.train --seed " + str(r["config"]["seed"]),
        "```",
        "",
        "## Limitations",
        "- Single train/val/test split and a single seed: no confidence intervals yet.",
        "- Predicting correctness is not the same as measuring memory or forgetting.",
    ]
    if not d["has_real_time"]:
        out.append("- This dataset has no timestamps, so time-gap features are constant zero.")
    if d["is_synthetic"]:
        out.append("- Synthetic data follows a simple generator; real students are messier.")
    return "\n".join(out) + "\n"


def write_report(results: dict, md_path: Path) -> None:
    md_path.write_text(render_markdown(results), encoding="utf-8")