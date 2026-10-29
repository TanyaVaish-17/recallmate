"""Simple baselines the Transformer must beat to justify its complexity.

All baselines are fitted on TRAIN windows only and scored on the same masked steps as the
Transformer.

1. GlobalRate          predicts the training correct-rate for everyone (AUC = 0.5 floor)
2. PreviousAnswer      P(correct | previous answer was none / wrong / right), from train
3. LogisticRegression  same engineered inputs as the Transformer (previous answer, 5 numeric
                       features, topic one-hot) but NO sequence modelling / attention
"""
from __future__ import annotations

import numpy as np
from scipy import sparse
from sklearn.linear_model import LogisticRegression


def flatten(arrays: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Select real (masked) steps -> flat 1-D / 2-D arrays."""
    m = arrays["mask"]
    return {
        "prev": arrays["prev_correct"][m],
        "topic": arrays["topic"][m],
        "question": arrays["question"][m],
        "numeric": arrays["numeric"][m],
        "y": arrays["target"][m].astype(int),
    }


class GlobalRate:
    def fit(self, flat):
        self.rate = float(flat["y"].mean())
        return self

    def predict_proba(self, flat):
        return np.full(len(flat["y"]), self.rate)


class PreviousAnswer:
    def fit(self, flat):
        self.global_rate = float(flat["y"].mean())
        self.rates = {}
        for k in (0, 1, 2):
            sel = flat["prev"] == k
            self.rates[k] = float(flat["y"][sel].mean()) if sel.any() else self.global_rate
        return self

    def predict_proba(self, flat):
        return np.array([self.rates[int(k)] for k in flat["prev"]])


class LogisticBaseline:
    def __init__(self, n_topics: int):
        self.n_topics = n_topics
        self.clf = LogisticRegression(max_iter=2000)

    def _x(self, flat):
        n = len(flat["y"])
        rows = np.arange(n)
        prev = sparse.csr_matrix((np.ones(n), (rows, flat["prev"])), shape=(n, 3))
        topic = sparse.csr_matrix((np.ones(n), (rows, flat["topic"])), shape=(n, self.n_topics))
        return sparse.hstack([prev, topic, sparse.csr_matrix(flat["numeric"])]).tocsr()

    def fit(self, flat):
        self.clf.fit(self._x(flat), flat["y"])
        return self

    def predict_proba(self, flat):
        return self.clf.predict_proba(self._x(flat))[:, 1]