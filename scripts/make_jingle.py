"""Generate Frontend/static/jingle.wav: the short chime Post radio plays
between posts (two soft notes, E5 -> A5, ~0.8 s, mono 22.05 kHz)."""

import math
import struct
import wave

RATE = 22050
NOTES = [(659.25, 0.0, 0.55), (880.0, 0.22, 0.6)]  # (Hz, start s, length s)
LENGTH = 0.85
VOLUME = 0.28

samples = [0.0] * int(RATE * LENGTH)
for freq, start, dur in NOTES:
    s0 = int(start * RATE)
    for i in range(int(dur * RATE)):
        t = i / RATE
        # Soft attack, exponential decay, a touch of the octave for a bell tone.
        env = min(1.0, t / 0.012) * math.exp(-t * 5.5)
        v = math.sin(2 * math.pi * freq * t) + 0.25 * math.sin(4 * math.pi * freq * t)
        if s0 + i < len(samples):
            samples[s0 + i] += VOLUME * env * v / 1.25

with wave.open("Frontend/static/jingle.wav", "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(RATE)
    w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, x)) * 32767)) for x in samples))
print("wrote Frontend/static/jingle.wav")
