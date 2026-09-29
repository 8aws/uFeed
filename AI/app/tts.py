"""Server-side text-to-speech (Piper neural voices on the CPU).

Only active when AI_TTS_VOICES is set: "<lang>:<m|f>=<piper voice>[@speaker]", e.g.
"es:m=es_ES-davefx-medium,es:f=es_ES-sharvard-medium@F,en:f=en_US-lessac-medium,en:m=en_US-ryan-medium"
(a plain "es=<voice>" serves both genders).
Voices are downloaded once into AI_MODELS_DIR/piper (a persistent volume) and
loaded in the background at startup. Runs on the CPU so it never competes with
the LLM on the iGPU; one synthesis at a time, capped at AI_TTS_THREADS threads
so the rest of the box stays responsive.
Benchmark on the Beelink (Core 3 304, 5 cores): ~25x real time, i.e. a
6-minute article in ~14 s, first sentence in ~0.4 s; ~500 MB RAM per loaded
voice; MP3 at 40 kbps mono is ~300 KB per minute.
"""

from __future__ import annotations

import os
import re
import threading
import time
import urllib.request

VOICES = {
    k.strip(): v.strip()
    for k, v in (
        pair.split("=", 1) for pair in os.getenv("AI_TTS_VOICES", "").split(",") if "=" in pair
    )
}
LANGS = sorted({k.split(":")[0] for k in VOICES})
THREADS = int(os.getenv("AI_TTS_THREADS", "3"))
# Voices kept loaded from startup (the default one), e.g. "es:f"; others load
# on first use (~0.6 s + a slower first inference).
PRELOAD = [k.strip() for k in os.getenv("AI_TTS_PRELOAD", "").split(",") if k.strip()]
BITRATE = int(os.getenv("AI_TTS_KBPS", "40"))
MODELS_DIR = os.path.join(os.getenv("AI_MODELS_DIR", "/models"), "piper")
HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
MAX_CHARS = 60000  # ~1 h of speech; longer texts are cut (the caller caps too)

_voices: dict = {}
_error: str | None = None
_load_lock = threading.Lock()
_gen_lock = threading.Lock()
_SENT = re.compile(r"(?<=[.!?…;:])\s+")


def enabled() -> bool:
    return bool(VOICES)


def status() -> dict:
    return {
        "voices": VOICES or None,
        "loaded": sorted(_voices),
        "threads": THREADS,
        "preload": PRELOAD,
        "error": _error,
    }


def _voice_path(name: str) -> str:
    """Download <name>.onnx(+.json) once, e.g. es_ES-davefx-medium."""
    lang_region, speaker, quality = name.split("-", 2)
    lang = lang_region.split("_")[0]
    os.makedirs(MODELS_DIR, exist_ok=True)
    onnx = os.path.join(MODELS_DIR, f"{name}.onnx")
    for suffix in (".onnx.json", ".onnx"):
        dest = os.path.join(MODELS_DIR, name + suffix)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            continue
        url = f"{HF}/{lang}/{lang_region}/{speaker}/{quality}/{name}{suffix}"
        tmp = dest + ".part"
        urllib.request.urlretrieve(url, tmp)  # fixed https host (Hugging Face)
        os.replace(tmp, dest)
    return onnx


def _resolve(lang: str, gender: str) -> tuple[str, str | None]:
    """(model name, speaker) for a language and preferred gender."""
    spec = VOICES.get(f"{lang}:{gender}") or VOICES.get(lang)
    if spec is None:
        spec = next(v for k, v in VOICES.items() if k.split(":")[0] == lang)
    model, _, speaker = spec.partition("@")
    return model, speaker or None


def _load(model: str):
    global _error
    with _load_lock:
        if model in _voices:
            return _voices[model]
        import onnxruntime as ort  # type: ignore
        from piper import PiperVoice  # type: ignore

        try:
            path = _voice_path(model)
            voice = PiperVoice.load(path)
            # Re-create the session with a thread cap (Piper uses every core).
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = THREADS
            opts.inter_op_num_threads = 1
            voice.session = ort.InferenceSession(
                path, sess_options=opts, providers=["CPUExecutionProvider"]
            )
            _voices[model] = voice
            _error = None
        except Exception as exc:  # noqa: BLE001 - reported via /health
            _error = f"{type(exc).__name__}: {exc}"[:300]
            raise
        return _voices[model]


def warm_up_in_background() -> None:
    """Download the voices at startup and load the preloaded ones (plus a
    throwaway synthesis to warm the runtime); the rest load on first use, so
    voices nobody picks cost disk only."""

    def _run() -> None:
        global _error
        for model in dict.fromkeys(v.partition("@")[0] for v in VOICES.values()):
            try:
                _voice_path(model)
            except Exception as exc:  # noqa: BLE001 - reported via /health
                _error = f"download {model}: {exc}"[:300]
        for key in PRELOAD:
            lang, _, gender = key.partition(":")
            try:
                synthesize("Hola." if lang == "es" else "Hello.", lang, gender or "f")
            except Exception as exc:  # noqa: BLE001 - reported via /health
                _error = f"preload {key}: {exc}"[:300]

    threading.Thread(target=_run, name="tts-warmup", daemon=True).start()


def synthesize(text: str, lang: str, gender: str = "f") -> tuple[bytes, float, int]:
    """(mp3, seconds of audio, ms spent). Sentence by sentence, so a long
    article never becomes one huge inference."""
    import lameenc  # type: ignore
    from piper.config import SynthesisConfig  # type: ignore

    model, speaker = _resolve(lang, gender)
    voice = _load(model)
    syn = None
    if speaker is not None:
        ids = voice.config.speaker_id_map or {}
        syn = SynthesisConfig(speaker_id=ids.get(speaker, int(speaker) if speaker.isdigit() else 0))
    text = text[:MAX_CHARS]
    t0 = time.time()
    pcm = bytearray()
    with _gen_lock:
        for sentence in _SENT.split(text):
            if sentence.strip():
                for chunk in voice.synthesize(sentence.strip(), syn_config=syn):
                    pcm += chunk.audio_int16_bytes
    rate = voice.config.sample_rate
    enc = lameenc.Encoder()
    enc.set_bit_rate(BITRATE)
    enc.set_in_sample_rate(rate)
    enc.set_channels(1)
    enc.set_quality(5)
    mp3 = enc.encode(bytes(pcm)) + enc.flush()
    return bytes(mp3), len(pcm) / 2 / rate, int((time.time() - t0) * 1000)


def synthesize_stream(text: str, lang: str, gender: str = "f"):
    """Yield MP3 bytes sentence by sentence, so playback can start after the
    first sentence (~0.4 s) instead of after the whole article. Holds the
    synthesis lock while iterating (one article at a time)."""
    import lameenc  # type: ignore
    from piper.config import SynthesisConfig  # type: ignore

    model, speaker = _resolve(lang, gender)
    voice = _load(model)
    syn = None
    if speaker is not None:
        ids = voice.config.speaker_id_map or {}
        syn = SynthesisConfig(speaker_id=ids.get(speaker, int(speaker) if speaker.isdigit() else 0))
    enc = lameenc.Encoder()
    enc.set_bit_rate(BITRATE)
    enc.set_in_sample_rate(voice.config.sample_rate)
    enc.set_channels(1)
    enc.set_quality(5)
    with _gen_lock:
        for sentence in _SENT.split(text[:MAX_CHARS]):
            if not sentence.strip():
                continue
            pcm = bytearray()
            for chunk in voice.synthesize(sentence.strip(), syn_config=syn):
                pcm += chunk.audio_int16_bytes
            out = enc.encode(bytes(pcm))
            if out:
                yield bytes(out)
        tail = enc.flush()
        if tail:
            yield bytes(tail)
