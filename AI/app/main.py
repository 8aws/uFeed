from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import llm
from app.embedders import DIM, build_embedder

BACKEND = os.getenv("AI_BACKEND", "hashing")
MODEL = os.getenv("AI_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
DEVICE = os.getenv("OPENVINO_DEVICE", "AUTO")

app = FastAPI(title="uFeed AI", version="0.1.0")

if BACKEND == "openvino" and llm.enabled():
    llm.warm_up_in_background()
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
        "llm": llm.status(),
    }


@app.post("/embed", response_model=EmbedResponse)
def embed(body: EmbedRequest) -> EmbedResponse:
    vectors = embedder().embed(body.texts)
    return EmbedResponse(dim=DIM, vectors=vectors)


import re

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
_SENT_RE = re.compile(r"(?<=[.!?])\s+")

# Small EN+ES stopword set so scoring favours content words, not glue words.
_STOPWORDS = frozenset(
    """
    the a an and or but if then else of to in on for with at by from as is are was were be been being it its
    this that these those we you they he she i me my our your their them his her not no nor so than too very
    el la los las un una unos unas y o u pero si de del al a en con sin por para como que se su sus lo le les
    es son era eran ser sido estar este esta estos estas ese esa eso esos esas mas más muy ya también sobre entre
    """.split()
)


def _summarize(text: str, max_sentences: int) -> str:
    """Whole-document extractive summary.

    Reads the entire text (not just the opening): scores every sentence by the
    normalised frequency of its content words across the whole article and
    returns the highest-scoring ones in their original order. Portable and
    dependency-free; the OpenVINO backend can swap in an abstractive model
    behind the same API.
    """
    plain = _WS_RE.sub(" ", _TAG_RE.sub(" ", text or "")).strip()
    if not plain:
        return ""
    sentences = [s.strip() for s in _SENT_RE.split(plain) if s.strip()]
    n = max(1, max_sentences)
    if len(sentences) <= n:
        return " ".join(sentences)

    freq: dict[str, float] = {}
    for w in _WORD_RE.findall(plain.lower()):
        if len(w) <= 2 or w in _STOPWORDS:
            continue
        freq[w] = freq.get(w, 0.0) + 1.0
    if not freq:
        return " ".join(sentences[:n])
    peak = max(freq.values())
    for w in freq:
        freq[w] /= peak

    scored: list[tuple[float, int, str]] = []
    for idx, sent in enumerate(sentences):
        words = [w for w in _WORD_RE.findall(sent.lower()) if len(w) > 2 and w not in _STOPWORDS]
        if not words:
            continue
        # Sum of term weights, length-normalised so long sentences don't win by
        # default, plus a small fading bonus for early sentences (context).
        score = sum(freq.get(w, 0.0) for w in words) / (len(words) ** 0.5)
        score *= 1.0 + max(0.0, 0.15 - idx * 0.01)
        scored.append((score, idx, sent))

    if not scored:
        return " ".join(sentences[:n])
    picked = sorted(scored, key=lambda x: x[0], reverse=True)[:n]
    picked.sort(key=lambda x: x[1])  # restore original reading order
    return " ".join(s for _, _, s in picked)


@app.post("/summarize", response_model=SummarizeResponse)
def summarize(body: SummarizeRequest) -> SummarizeResponse:
    return SummarizeResponse(summary=_summarize(body.text, body.max_sentences))


@app.post("/summarize_batch", response_model=SummarizeBatchResponse)
def summarize_batch(body: SummarizeBatchRequest) -> SummarizeBatchResponse:
    return SummarizeBatchResponse(
        summaries=[_summarize(t, body.max_sentences) for t in body.texts]
    )


class LLMSummaryRequest(BaseModel):
    title: str = ""
    text: str
    lang: str = "es"
    translate_title: bool = False


class LLMSummaryResponse(BaseModel):
    summary: str
    title: str | None = None
    model: str
    ms: int


@app.post("/generate/summary", response_model=LLMSummaryResponse)
def generate_summary(body: LLMSummaryRequest) -> LLMSummaryResponse:
    """Abstractive summary in the reader's language (sync: runs in a thread)."""
    if not llm.enabled():
        raise HTTPException(status_code=503, detail="LLM not configured")
    plain = _WS_RE.sub(" ", _TAG_RE.sub(" ", body.text or "")).strip()
    try:
        out = llm.summarize(body.title, plain, body.lang, body.translate_title)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {exc}"[:200]) from exc
    return LLMSummaryResponse(**out)
