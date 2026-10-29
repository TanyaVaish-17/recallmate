"""Checkpoint save/load. The checkpoint is self-describing so inference needs no guessing."""
from __future__ import annotations

from pathlib import Path

import torch

from ml.model.transformer import KTTransformer, ModelConfig

NOT_TRAINED_MSG = (
    "No trained model checkpoint found at {path}. Train one first: "
    "`python -m ml.training.train` (see ml/README.md)."
)


def save_checkpoint(path: Path, model: KTTransformer, model_version: str, extra: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_version": model_version,
            "model_config": model.cfg.to_dict(),
            "state_dict": model.state_dict(),
            **extra,
        },
        path,
    )


def load_checkpoint(path: Path, device: str = "cpu") -> tuple[KTTransformer, dict]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(NOT_TRAINED_MSG.format(path=path))
    ckpt = torch.load(path, map_location=device, weights_only=True)
    model = KTTransformer(ModelConfig.from_dict(ckpt["model_config"]))
    model.load_state_dict(ckpt["state_dict"])
    model.to(device).eval()
    return model, ckpt