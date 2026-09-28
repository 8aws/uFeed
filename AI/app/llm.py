"""On-device LLM (OpenVINO GenAI) for abstractive summaries and translation.

Only active when AI_LLM_MODEL is set (OpenVINO backend on the NAS). The model
is downloaded once into AI_MODELS_DIR (a persistent volume), compiled for the
iGPU in the background at startup, and used one request at a time.
Benchmark on the Beelink (Wildcat Lake iGPU, 1.5k-token article): Qwen3-4B
int4 ~10 tok/s, ~16 s per summary; smaller models were faster but wrote in the
wrong language or got facts wrong.
"""

from __future__ import annotations

import os
import re
import threading
import time

LLM_MODEL = os.getenv("AI_LLM_MODEL", "")  # e.g. OpenVINO/Qwen3-4B-int4-ov
LLM_DEVICE = os.getenv("AI_LLM_DEVICE", "GPU")
MODELS_DIR = os.getenv("AI_MODELS_DIR", "/models")
MAX_INPUT_CHARS = 6000

_pipe = None
_error: str | None = None
_load_lock = threading.Lock()
_gen_lock = threading.Lock()  # one generation at a time on the iGPU

_THINK = re.compile(r"<think>.*?</think>", re.S)

PROMPTS = {
    "es": {
        "system": "Eres un asistente que resume noticias con precisión. Nunca inventas datos.",
        "summary": (
            "Resume en español, en 3 o 4 frases claras y neutrales, el siguiente artículo. "
            "Responde solo con el resumen."
        ),
        "title": "Traduce al español este titular. Responde solo con la traducción.",
    },
    "en": {
        "system": "You summarise news accurately. You never invent facts.",
        "summary": (
            "Summarise the following article in English in 3 or 4 clear, neutral sentences. "
            "Reply with the summary only."
        ),
        "title": "Translate this headline into English. Reply with the translation only.",
    },
}


def enabled() -> bool:
    return bool(LLM_MODEL)


def status() -> dict:
    return {
        "model": LLM_MODEL or None,
        "device": LLM_DEVICE,
        "loaded": _pipe is not None,
        "error": _error,
    }


def _load():
    global _pipe, _error
    with _load_lock:
        if _pipe is not None:
            return _pipe
        import openvino_genai as ov_genai  # type: ignore
        from huggingface_hub import snapshot_download  # type: ignore

        try:
            local = os.path.join(MODELS_DIR, LLM_MODEL.split("/")[-1])
            path = snapshot_download(LLM_MODEL, local_dir=local)
            _pipe = ov_genai.LLMPipeline(path, LLM_DEVICE)
            _error = None
        except Exception as exc:  # noqa: BLE001 - reported via /health
            _error = f"{type(exc).__name__}: {exc}"[:300]
            raise
        return _pipe


def warm_up_in_background() -> None:
    """Download/compile at startup so the first request doesn't pay for it."""

    def _run() -> None:
        try:
            _load()
        except Exception:  # noqa: BLE001 - kept in _error
            pass

    threading.Thread(target=_run, name="llm-warmup", daemon=True).start()


def _clean(text: str) -> str:
    text = _THINK.sub("", text).replace("<think>", "").replace("</think>", "")
    return text.strip().strip('"“”').strip()


def summarize(title: str, text: str, lang: str, translate_title: bool) -> dict:
    """Abstractive summary in `lang` (and the headline translated if asked)."""
    import openvino_genai as ov_genai  # type: ignore

    pipe = _load()
    tok = pipe.get_tokenizer()
    p = PROMPTS.get(lang, PROMPTS["en"])
    no_think = " /no_think" if "qwen3" in LLM_MODEL.lower() else ""

    def run(user: str, max_new: int) -> str:
        prompt = tok.apply_chat_template(
            [{"role": "system", "content": p["system"]}, {"role": "user", "content": user + no_think}],
            add_generation_prompt=True,
        )
        cfg = ov_genai.GenerationConfig()
        cfg.max_new_tokens = max_new
        cfg.do_sample = False
        cfg.repetition_penalty = 1.05
        cfg.apply_chat_template = False
        return _clean(pipe.generate([prompt], cfg).texts[0])

    t0 = time.time()
    with _gen_lock:
        body = (text or "")[:MAX_INPUT_CHARS]
        summary = run(f"{p['summary']}\n\nTitle: {title}\n\n{body}", 220)
        new_title = run(f"{p['title']}\n\n{title}", 60) if translate_title and title else None
    return {
        "summary": summary,
        "title": new_title,
        "model": LLM_MODEL.split("/")[-1],
        "ms": int((time.time() - t0) * 1000),
    }
