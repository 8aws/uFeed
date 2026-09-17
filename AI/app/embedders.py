"""Embedding backends behind a common interface.

- HashingEmbedder: dependency-free feature-hashing embedding. Deterministic and
  runs anywhere; captures lexical overlap (good enough to exercise the whole
  pipeline in dev/CI).
- OpenVINOEmbedder: sentence-transformer via OpenVINO for the NAS (Intel
  iGPU/NPU). Loaded lazily and only when AI_BACKEND=openvino.

All backends output L2-normalised vectors of DIM dimensions so cosine distance
== dot product and vectors are interchangeable in pgvector.
"""

from __future__ import annotations

import math
import re
from typing import Protocol

DIM = 384
_TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _normalise(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


class HashingEmbedder:
    dim = DIM

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * DIM
            for token in _TOKEN_RE.findall((text or "").lower()):
                h = hash(token)
                idx = h % DIM
                sign = 1.0 if (h >> 20) & 1 else -1.0
                vec[idx] += sign
            out.append(_normalise(vec))
        return out


class OpenVINOEmbedder:
    """Sentence embeddings via OpenVINO (Intel CPU/iGPU/NPU).

    Only imported when selected, so the base image need not carry OpenVINO.
    """

    dim = DIM

    def __init__(self, model: str, device: str) -> None:
        from optimum.intel import OVModelForFeatureExtraction  # type: ignore
        from transformers import AutoTokenizer  # type: ignore

        self._tok = AutoTokenizer.from_pretrained(model)
        self._model = OVModelForFeatureExtraction.from_pretrained(model, device=device)

    def embed(self, texts: list[str]) -> list[list[float]]:
        import numpy as np  # type: ignore

        enc = self._tok(
            texts, padding=True, truncation=True, max_length=256, return_tensors="pt"
        )
        out = self._model(**enc)
        # Mean-pool token embeddings, then L2-normalise.
        last = out.last_hidden_state
        mask = enc["attention_mask"].unsqueeze(-1)
        summed = (last * mask).sum(1)
        counts = mask.sum(1).clamp(min=1)
        pooled = (summed / counts).detach().numpy()
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return (pooled / norms).tolist()


def build_embedder(backend: str, model: str, device: str) -> Embedder:
    if backend == "openvino":
        return OpenVINOEmbedder(model, device)
    return HashingEmbedder()
