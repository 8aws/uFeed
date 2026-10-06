from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app import llm, translate, tts
from app.embedders import DIM, build_embedder

BACKEND = os.getenv("AI_BACKEND", "hashing")
MODEL = os.getenv("AI_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
DEVICE = os.getenv("OPENVINO_DEVICE", "AUTO")

app = FastAPI(title="uFeed AI", version="0.1.0")

if BACKEND == "openvino" and llm.enabled():
    llm.warm_up_in_background()
if tts.enabled():
    tts.warm_up_in_background()
translate.warm_up_in_background()
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


def _rss_mb() -> float | None:
    """This process's resident memory (all loaded models), for the monitor."""
    try:
        for line in open("/proc/self/status"):
            if line.startswith("VmRSS:"):
                return round(int(line.split()[1]) / 1024, 1)
    except OSError:
        pass
    return None


@app.get("/health")
def health() -> dict:
    return {
        "rss_mb": _rss_mb(),
        "status": "ok",
        "backend": BACKEND,
        "dim": DIM,
        "device": DEVICE,
        **_openvino_devices(),
        "llm": llm.status(),
        "tts": tts.status(),
        "mt": translate.status(),
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
    src_lang: str = ""  # the article's language (headline via the translator)
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
        out = llm.summarize(body.title, plain, body.lang, body.translate_title, body.src_lang)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {exc}"[:200]) from exc
    return LLMSummaryResponse(**out)


class LLMBatchRequest(BaseModel):
    items: list[LLMSummaryRequest] = Field(min_length=1, max_length=8)


class LLMBatchResponse(BaseModel):
    results: list[LLMSummaryResponse]


@app.post("/generate/summaries", response_model=LLMBatchResponse)
def generate_summaries(body: LLMBatchRequest) -> LLMBatchResponse:
    """Several summaries generated together (continuous batching on the iGPU):
    two take ~21 s instead of ~32 s one after the other."""
    if not llm.enabled():
        raise HTTPException(status_code=503, detail="LLM not configured")
    items = [
        {
            "title": it.title,
            "text": _WS_RE.sub(" ", _TAG_RE.sub(" ", it.text or "")).strip(),
            "lang": it.lang,
            "src_lang": it.src_lang,
            "translate_title": it.translate_title,
        }
        for it in body.items
    ]
    try:
        out = llm.summarize_batch(items)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {exc}"[:200]) from exc
    return LLMBatchResponse(results=[LLMSummaryResponse(**o) for o in out])


class TTSRequest(BaseModel):
    text: str
    lang: str = "es"
    gender: str = "f"  # "f" | "m": preferred voice


@app.post("/tts")
def text_to_speech(body: TTSRequest) -> Response:
    """MP3 of the text read aloud by the voice for `lang` (sync: in a thread)."""
    lang = (body.lang or "").split("-")[0].lower()
    if not tts.enabled() or lang not in tts.LANGS:
        raise HTTPException(status_code=422, detail="language not supported")
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="empty text")
    try:
        gender = "m" if body.gender == "m" else "f"
        mp3, seconds, ms = tts.synthesize(body.text, lang, gender)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"TTS unavailable: {exc}"[:200]) from exc
    return Response(
        content=mp3,
        media_type="audio/mpeg",
        headers={"X-Audio-Seconds": f"{seconds:.1f}", "X-Synth-Ms": str(ms)},
    )


class TranslateRequest(BaseModel):
    texts: list[str]  # paragraphs, translated independently (keeps structure)
    src: str
    dst: str


class TranslateResponse(BaseModel):
    texts: list[str]
    ms: int


@app.post("/translate", response_model=TranslateResponse)
def translate_texts(body: TranslateRequest) -> TranslateResponse:
    """Machine translation between configured pairs (sync: runs in a thread)."""
    pair = f"{body.src}-{body.dst}"
    if pair not in translate.available():
        raise HTTPException(status_code=422, detail="language pair not available")
    try:
        texts, ms = translate.translate(body.texts[:400], body.src, body.dst)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"MT unavailable: {exc}"[:200]) from exc
    return TranslateResponse(texts=texts, ms=ms)


@app.post("/tts/stream")
def text_to_speech_stream(body: TTSRequest) -> StreamingResponse:
    """Same as /tts, but the MP3 is sent as it's produced (first bytes after
    the first sentence)."""
    lang = (body.lang or "").split("-")[0].lower()
    if not tts.enabled() or lang not in tts.LANGS:
        raise HTTPException(status_code=422, detail="language not supported")
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="empty text")
    gender = "m" if body.gender == "m" else "f"
    return StreamingResponse(tts.synthesize_stream(body.text, lang, gender), media_type="audio/mpeg")
