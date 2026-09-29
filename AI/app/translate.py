"""Machine translation for "read in my language" (Helsinki-NLP opus-mt, MarianMT).

Models are OpenVINO IR with 8-bit weights, exported once into
AI_MODELS_DIR/mt/opus-mt-<src>-<dst> by scripts/export_mt.sh (the exporter
needs an older transformers than this image runs; inference doesn't).
Runs on the CPU so it never competes with the LLM on the iGPU.
Benchmark on the Beelink (Core 3 304): ~750-word article in 3-4 s either way
(EN<->ES), ~240 MB per direction on disk. Qwen3-4B would take ~2 min.
"""

from __future__ import annotations

import os
import re
import threading
import time

PAIRS = [p.strip() for p in os.getenv("AI_MT_PAIRS", "").split(",") if p.strip()]  # "en-es,es-en"
DEVICE = os.getenv("AI_MT_DEVICE", "CPU")
PRELOAD = os.getenv("AI_MT_PRELOAD", "0") == "1"  # keep every pair loaded from startup
MODELS_DIR = os.path.join(os.getenv("AI_MODELS_DIR", "/models"), "mt")
BATCH = 8
MAX_SENTENCES = 800  # ~15k words; longer articles are cut

_models: dict = {}
_error: str | None = None
_load_lock = threading.Lock()
_gen_lock = threading.Lock()
_SENT = re.compile(r"(?<=[.!?…])\s+")


def model_dir(pair: str) -> str:
    return os.path.join(MODELS_DIR, f"opus-mt-{pair}")


def available() -> list[str]:
    """Configured pairs whose model has been exported."""
    return [p for p in PAIRS if os.path.exists(os.path.join(model_dir(p), "config.json"))]


def status() -> dict:
    return {"pairs": PAIRS, "available": available(), "loaded": sorted(_models), "error": _error}


def _load(pair: str):
    global _error
    with _load_lock:
        if pair in _models:
            return _models[pair]
        from optimum.intel import OVModelForSeq2SeqLM  # type: ignore
        from transformers import AutoTokenizer  # type: ignore

        try:
            path = model_dir(pair)
            _models[pair] = (
                AutoTokenizer.from_pretrained(path),
                OVModelForSeq2SeqLM.from_pretrained(path, device=DEVICE),
            )
            _error = None
        except Exception as exc:  # noqa: BLE001 - reported via /health
            _error = f"{type(exc).__name__}: {exc}"[:300]
            raise
        return _models[pair]


def translate(texts: list[str], src: str, dst: str) -> tuple[list[str], int]:
    """Translate each text (paragraphs), sentence by sentence in batches.
    Returns (translations, ms)."""
    pair = f"{src}-{dst}"
    tok, model = _load(pair)
    # Flatten paragraphs into sentences, remembering where each one goes.
    flat: list[tuple[int, str]] = []
    for i, t in enumerate(texts):
        for s in _SENT.split(t or ""):
            if s.strip() and len(flat) < MAX_SENTENCES:
                flat.append((i, s.strip()))
    out: list[list[str]] = [[] for _ in texts]
    t0 = time.time()
    with _gen_lock:
        for b in range(0, len(flat), BATCH):
            chunk = flat[b : b + BATCH]
            enc = tok([s for _, s in chunk], return_tensors="pt", padding=True, truncation=True, max_length=400)
            gen = model.generate(**enc, num_beams=1, max_new_tokens=400)
            for (i, _), res in zip(chunk, tok.batch_decode(gen, skip_special_tokens=True), strict=True):
                out[i].append(res)
    return [" ".join(parts) for parts in out], int((time.time() - t0) * 1000)


def warm_up_in_background() -> None:
    """Load (and run once) every available pair at startup if AI_MT_PRELOAD=1,
    so the first translation doesn't pay for loading the model."""
    if not PRELOAD:
        return

    def _run() -> None:
        global _error
        for pair in available():
            src, dst = pair.split("-")
            try:
                translate(["Hola." if src == "es" else "Hello."], src, dst)
            except Exception as exc:  # noqa: BLE001 - reported via /health
                _error = f"preload {pair}: {exc}"[:300]

    threading.Thread(target=_run, name="mt-warmup", daemon=True).start()
