"""Compact causal Transformer encoder for knowledge tracing.

Task: at every step t, output P(student answers question t correctly) using only
information available before answering (see ml/data/preprocess.py).

Architecture (pre-LayerNorm, d = d_model)
-----------------------------------------
Input embedding at step t  (all summed, shape (B, L, d)):
    question_emb[question_t] + topic_emb[topic_t] + prev_emb[prev_correct_t]
    + Linear(numeric_t: 5 -> d) + pos_emb[t]
        |
   N x EncoderBlock:
        x = x + Dropout(MultiHeadCausalSelfAttention(LayerNorm(x)))
        x = x + Dropout(FeedForward(LayerNorm(x)))          # d -> d_ff -> d, GELU
        |
   LayerNorm -> Linear(d, d) -> GELU -> Dropout -> Linear(d, 1)  => logits (B, L)

Probability = sigmoid(logits). Training uses BCE-with-logits (ml/model/loss.py).

Causality: attention scores above the diagonal are set to -inf before softmax, so step t
attends only to steps <= t. Padding is on the right, so real steps never attend to
padding. Both properties are unit-tested (ml/tests/test_model.py).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

from ml.data.schema import NUMERIC_FEATURES, PAD


@dataclass
class ModelConfig:
    n_questions: int
    n_topics: int
    max_len: int = 100
    d_model: int = 64
    n_heads: int = 4
    n_layers: int = 2
    d_ff: int = 128
    dropout: float = 0.1
    n_numeric: int = len(NUMERIC_FEATURES)

    def __post_init__(self) -> None:
        if self.d_model % self.n_heads != 0:
            raise ValueError("d_model must be divisible by n_heads")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ModelConfig":
        return cls(**d)


class CausalSelfAttention(nn.Module):
    """Multi-head scaled dot-product self-attention with a causal mask."""

    def __init__(self, d_model: int, n_heads: int, dropout: float):
        super().__init__()
        self.n_heads = n_heads
        self.d_head = d_model // n_heads
        self.qkv = nn.Linear(d_model, 3 * d_model)
        self.out = nn.Linear(d_model, d_model)
        self.attn_drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, return_attn: bool = False):
        B, L, D = x.shape
        q, k, v = self.qkv(x).chunk(3, dim=-1)

        def split(t: torch.Tensor) -> torch.Tensor:  # (B, L, D) -> (B, H, L, d_head)
            return t.view(B, L, self.n_heads, self.d_head).transpose(1, 2)

        q, k, v = split(q), split(k), split(v)
        scores = q @ k.transpose(-2, -1) / math.sqrt(self.d_head)       # (B, H, L, L)
        causal = torch.triu(torch.ones(L, L, dtype=torch.bool, device=x.device), diagonal=1)
        scores = scores.masked_fill(causal, float("-inf"))              # no peeking ahead
        attn = F.softmax(scores, dim=-1)
        ctx = self.attn_drop(attn) @ v                                   # (B, H, L, d_head)
        ctx = ctx.transpose(1, 2).contiguous().view(B, L, D)
        out = self.out(ctx)
        return (out, attn) if return_attn else out


class EncoderBlock(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.norm1 = nn.LayerNorm(cfg.d_model)
        self.attn = CausalSelfAttention(cfg.d_model, cfg.n_heads, cfg.dropout)
        self.norm2 = nn.LayerNorm(cfg.d_model)
        self.ff = nn.Sequential(
            nn.Linear(cfg.d_model, cfg.d_ff),
            nn.GELU(),
            nn.Dropout(cfg.dropout),
            nn.Linear(cfg.d_ff, cfg.d_model),
        )
        self.drop = nn.Dropout(cfg.dropout)

    def forward(self, x: torch.Tensor, return_attn: bool = False):
        h = self.attn(self.norm1(x), return_attn=return_attn)
        attn = None
        if return_attn:
            h, attn = h
        x = x + self.drop(h)                       # residual 1
        x = x + self.drop(self.ff(self.norm2(x)))  # residual 2
        return (x, attn) if return_attn else x


class KTTransformer(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.cfg = cfg
        d = cfg.d_model
        self.question_emb = nn.Embedding(cfg.n_questions, d, padding_idx=PAD)
        self.topic_emb = nn.Embedding(cfg.n_topics, d, padding_idx=PAD)
        self.prev_emb = nn.Embedding(3, d)  # none / wrong / right
        self.numeric_proj = nn.Linear(cfg.n_numeric, d)
        self.pos_emb = nn.Embedding(cfg.max_len, d)
        self.in_drop = nn.Dropout(cfg.dropout)
        self.blocks = nn.ModuleList([EncoderBlock(cfg) for _ in range(cfg.n_layers)])
        self.final_norm = nn.LayerNorm(d)
        self.head = nn.Sequential(
            nn.Linear(d, d), nn.GELU(), nn.Dropout(cfg.dropout), nn.Linear(d, 1)
        )
        self._init_weights()

    def _init_weights(self) -> None:
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Embedding):
                nn.init.normal_(m.weight, std=0.02)
                if m.padding_idx is not None:
                    with torch.no_grad():
                        m.weight[m.padding_idx].zero_()

    def forward(self, batch: dict[str, torch.Tensor], return_attn: bool = False):
        """batch keys: question, topic, prev_correct (B, L) long; numeric (B, L, 5) float.

        Returns logits (B, L). With return_attn=True also returns a list of per-layer
        attention tensors (B, H, L, L) for visualisation in the viva.
        """
        question = batch["question"]
        B, L = question.shape
        if L > self.cfg.max_len:
            raise ValueError(f"Sequence length {L} exceeds max_len {self.cfg.max_len}")

        positions = torch.arange(L, device=question.device)
        x = (
            self.question_emb(question)
            + self.topic_emb(batch["topic"])
            + self.prev_emb(batch["prev_correct"])
            + self.numeric_proj(batch["numeric"])
            + self.pos_emb(positions)[None, :, :]
        )
        x = self.in_drop(x)

        attns = []
        for block in self.blocks:
            if return_attn:
                x, a = block(x, return_attn=True)
                attns.append(a)
            else:
                x = block(x)

        logits = self.head(self.final_norm(x)).squeeze(-1)
        return (logits, attns) if return_attn else logits

    @torch.no_grad()
    def predict_proba(self, batch: dict[str, torch.Tensor]) -> torch.Tensor:
        was_training = self.training
        self.eval()
        probs = torch.sigmoid(self(batch))
        if was_training:
            self.train()
        return probs

    def n_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)