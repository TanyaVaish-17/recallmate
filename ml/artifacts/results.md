# RecallMate experiment results

> **SYNTHETIC DATA.** These numbers come from simulated students and are a
> development check only. They are NOT results on real students.

## Dataset
- Source: `synthetic`
- Students (train/val/test): 700 / 150 / 150
- Interactions (train/val/test): 83,488 / 17,921 / 18,041
- Real timestamps available: True
- Train positive rate: 0.695
- Split is by student; vocabularies and normalisation fitted on train only.

## Test-set results (threshold 0.5 for accuracy/precision/recall/F1; AUC is threshold-free)

| Model | AUC | Accuracy | Precision | Recall | F1 | Log loss | Brier |
|---|---|---|---|---|---|---|---|
| Transformer (test) | 0.7478 | 0.7294 | 0.7467 | 0.9217 | 0.8250 | 0.5336 | 0.1792 |
| Transformer, ids hidden (test) | 0.7031 | 0.7028 | 0.7117 | 0.9592 | 0.8171 | 0.5612 | 0.1911 |
| Logistic regression (test) | 0.6791 | 0.7003 | 0.7237 | 0.9169 | 0.8090 | 0.5752 | 0.1956 |
| Previous-answer rate (test) | 0.5789 | 0.6921 | 0.6921 | 1.0000 | 0.8180 | 0.6055 | 0.2079 |
| Global rate (test) | 0.5000 | 0.6921 | 0.6921 | 1.0000 | 0.8180 | 0.6174 | 0.2131 |

"ids hidden" replaces every question/topic id with UNK at test time. It simulates
applying the model to a question bank it has never seen (as RecallMate does).

## Training
- Model version: `kt-transformer-synthetic-20261029-185717`  (99,009 parameters)
- Device: cpu, torch 2.15.0+cpu, seed 42
- Epochs run: 14 (best epoch 9, best val AUC 0.7587); wall time 175.4s
- Validation AUC at best epoch: 0.7587 (used for model selection; test set was evaluated once, afterwards)

## Hyperparameters
```json
{
  "epochs": 30,
  "batch_size": 32,
  "lr": 0.001,
  "weight_decay": 0.01,
  "d_model": 64,
  "n_heads": 4,
  "n_layers": 2,
  "d_ff": 128,
  "dropout": 0.1,
  "patience": 5,
  "grad_clip": 1.0,
  "use_pos_weight": false,
  "id_dropout": 0.25,
  "threshold": 0.5,
  "seed": 42,
  "device": "auto"
}
```

## Reproduce
```bash
python -m ml.data.build_dataset --source synthetic
python -m ml.training.train --seed 42
```

## Limitations
- Single train/val/test split and a single seed: no confidence intervals yet.
- Predicting correctness is not the same as measuring memory or forgetting.
- Synthetic data follows a simple generator; real students are messier.
