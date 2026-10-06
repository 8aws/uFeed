"""On-device LLM (OpenVINO GenAI) for abstractive summaries and translation.

Only active when AI_LLM_MODEL is set (OpenVINO backend on the NAS). The model
is downloaded once into AI_MODELS_DIR (a persistent volume), compiled for the
iGPU in the background at startup, and runs one batch at a time.
Benchmark on the Beelink (Wildcat Lake iGPU, ~1.9k-token articles, Qwen3-4B
int4): one summary ~15-17 s; with continuous batching (paged attention) two
summaries together take ~21 s (~10 s each) and four ~39 s, so the backend's
queue sends up to two at once. Speculative decoding with Qwen3-0.6B as draft
was slower on the iGPU and didn't compile on the NPU in reasonable time.
Smaller main models were faster but wrote in the wrong language or got facts
wrong.
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
KV_CACHE_GB = max(1, int(os.getenv("AI_LLM_KV_GB", "1")))  # ~0.3 GB per 2k-token article

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
            # Paged attention + continuous batching: several prompts per call.
            sched = ov_genai.SchedulerConfig()
            sched.cache_size = KV_CACHE_GB
            sched.enable_prefix_caching = True  # the instructions repeat
            _pipe = ov_genai.LLMPipeline(
                path, LLM_DEVICE, scheduler_config=sched, ATTENTION_BACKEND="PA"
            )
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


def _title_by_mt(titles: list[str], src: str, dst: str) -> list[str] | None:
    """Headlines through the CPU translator (instant) instead of the iGPU."""
    from app import translate

    if not src or f"{src}-{dst}" not in translate.available():
        return None
    try:
        return translate.translate(titles, src, dst)[0]
    except Exception:  # noqa: BLE001 - fall back to the LLM
        return None


def summarize_batch(items: list[dict]) -> list[dict]:
    """Abstractive summaries, generated together in one batch. Each item:
    title, text, lang (summary language), src_lang (article language) and
    translate_title (also give the headline in `lang`)."""
    import openvino_genai as ov_genai  # type: ignore

    pipe = _load()
    tok = pipe.get_tokenizer()
    no_think = " /no_think" if "qwen3" in LLM_MODEL.lower() else ""

    def prompt(lang: str, user: str) -> str:
        p = PROMPTS.get(lang, PROMPTS["en"])
        return tok.apply_chat_template(
            [{"role": "system", "content": p["system"]}, {"role": "user", "content": user + no_think}],
            add_generation_prompt=True,
        )

    def cfg(max_new: int):
        c = ov_genai.GenerationConfig()
        c.max_new_tokens = max_new
        c.do_sample = False
        c.repetition_penalty = 1.05
        c.apply_chat_template = False
        return c

    t0 = time.time()
    prompts = [
        prompt(
            it["lang"],
            f"{PROMPTS.get(it['lang'], PROMPTS['en'])['summary']}\n\n"
            f"Title: {it.get('title') or ''}\n\n{(it.get('text') or '')[:MAX_INPUT_CHARS]}",
        )
        for it in items
    ]
    titles: list[str | None] = [None] * len(items)
    with _gen_lock:
        res = pipe.generate(prompts, cfg(220))
        summaries = [_clean(t) for t in res.texts]
        # Headlines: CPU translator when the pair exists, else the LLM.
        llm_titles = []
        for i, it in enumerate(items):
            if not (it.get("translate_title") and it.get("title")):
                continue
            mt = _title_by_mt([it["title"]], it.get("src_lang") or "", it["lang"])
            if mt:
                titles[i] = mt[0]
            else:
                llm_titles.append(i)
        if llm_titles:
            tp = [
                prompt(items[i]["lang"], f"{PROMPTS.get(items[i]['lang'], PROMPTS['en'])['title']}\n\n{items[i]['title']}")
                for i in llm_titles
            ]
            out = pipe.generate(tp, cfg(60))
            for i, t in zip(llm_titles, out.texts, strict=True):
                titles[i] = _clean(t)
    ms = int((time.time() - t0) * 1000)
    model = LLM_MODEL.split("/")[-1]
    return [
        {"summary": summaries[i], "title": titles[i], "model": model, "ms": ms}
        for i in range(len(items))
    ]


def summarize(title: str, text: str, lang: str, translate_title: bool, src_lang: str = "") -> dict:
    """One summary in `lang` (and the headline translated if asked)."""
    item = {"title": title, "text": text, "lang": lang, "src_lang": src_lang}
    return summarize_batch([{**item, "translate_title": translate_title}])[0]
