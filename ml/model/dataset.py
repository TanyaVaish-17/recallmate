"""Load the .npz tensors written by ml.data.build_dataset as torch tensors."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset

KEYS = ("question", "topic", "prev_correct", "numeric", "target", "mask")


class KTDataset(Dataset):
    def __init__(self, npz_path: str | Path):
        z = np.load(npz_path)
        self.t = {
            "question": torch.from_numpy(z["question"]).long(),
            "topic": torch.from_numpy(z["topic"]).long(),
            "prev_correct": torch.from_numpy(z["prev_correct"]).long(),
            "numeric": torch.from_numpy(z["numeric"]).float(),
            "target": torch.from_numpy(z["target"]).float(),
            "mask": torch.from_numpy(z["mask"]).bool(),
        }

    def __len__(self) -> int:
        return self.t["question"].shape[0]

    def __getitem__(self, i: int) -> dict[str, torch.Tensor]:
        return {k: v[i] for k, v in self.t.items()}