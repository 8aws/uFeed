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


class SummarizeBatchRequest(BaseModel):
    texts: list[str]
    max_sentences: int = 3


class SummarizeBatchResponse(BaseModel):
    summaries: list[str]


def _openvino_devices() -> dict:
    """Report what the OpenVINO runtime actually sees inside this container.

    `device` is only the *requested* target (AUTO/GPU/NPU/CPU); this shows the
    devices the runtime discovered, so you can tell whether the iGPU/NPU are
    reachable from the container or it silently fell back to CPU. Host drivers
    are not enough — the container needs the Intel user-space runtime and the
    device nodes (/dev/dri for the iGPU, /dev/accel for the NPU).
    """
    if BACKEND != "openvino":
        return {}
    try:
        import openvino as ov  # type: ignore

        core = ov.Core()
        names = list(core.available_devices)
        full = {}
        for name in names:
            try:
                full[name] = core.get_property(name, "FULL_DEVICE_NAME")
            except Exception:
                full[name] = None
        return {"available_devices": names, "device_names": full}
    except Exception as exc:  # pragma: no cover - diagnostic only
        return {"available_devices_error": str(exc)}


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "backend": BACKEND,
        "dim": DIM,
        "device": DEVICE,
        **_openvino_devices(),
    }


@app.post("/embed", response_model=EmbedResponse)
def embed(body: EmbedRequest) -> EmbedResponse:
    vectors = embedder().embed(body.texts)
    return EmbedResponse(dim=DIM, vectors=vectors)


import re

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _summarize(text: str, max_sentences: int) -> str:
    plain = _WS_RE.sub(" ", _TAG_RE.sub(" ", text or "")).strip()
    # Portable extractive summary: the first N sentences. The OpenVINO backend
    # (NAS) can replace this with an abstractive model behind the same API.
    sentences = re.split(r"(?<=[.!?])\s+", plain)
    return " ".join(sentences[: max(1, max_sentences)]).strip()


@app.post("/summarize", response_model=SummarizeResponse)
def summarize(body: SummarizeRequest) -> SummarizeResponse:
    return SummarizeResponse(summary=_summarize(body.text, body.max_sentences))


@app.post("/summarize_batch", response_model=SummarizeBatchResponse)
def summarize_batch(body: SummarizeBatchRequest) -> SummarizeBatchResponse:
    return SummarizeBatchResponse(
        summaries=[_summarize(t, body.max_sentences) for t in body.texts]
    )
