from __future__ import annotations

import os

from fastapi import FastAPI
from pydantic import BaseModel

from app.embedders import DIM, build_embedder

BACKEND = os.getenv("AI_BACKEND", "hashing")
MODEL = os.getenv("AI_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
DEVICE = os.getenv("OPENVINO_DEVICE", "AUTO")

app = FastAPI(title="uFeed AI", version="0.1.0")
_embedder = None


def embedder():
    global _embedder
    if _embedder is None:
        _embedder = build_embedder(BACKEND, MODEL, DEVICE)
    return _embedder


class EmbedRequest(BaseModel):
    texts: list[str]


class EmbedResponse(BaseModel):
    dim: int
    vectors: list[list[float]]


class SummarizeRequest(BaseModel):
    text: str
    max_sentences: int = 3


class SummarizeResponse(BaseModel):
    summary: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "backend": BACKEND, "dim": DIM, "device": DEVICE}


@app.post("/embed", response_model=EmbedResponse)
def embed(body: EmbedRequest) -> EmbedResponse:
    vectors = embedder().embed(body.texts)
    return EmbedResponse(dim=DIM, vectors=vectors)


@app.post("/summarize", response_model=SummarizeResponse)
def summarize(body: SummarizeRequest) -> SummarizeResponse:
    # Phase 2 will use OpenVINO; for now a simple lead-sentences extract.
    import re

    sentences = re.split(r"(?<=[.!?])\s+", (body.text or "").strip())
    summary = " ".join(sentences[: max(1, body.max_sentences)]).strip()
    return SummarizeResponse(summary=summary)
