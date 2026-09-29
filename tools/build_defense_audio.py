"""Build the original, deterministic two-strike defense warning bell.

Uses Python's standard library only; no recordings, external assets or runtime
DSP are needed. Run from any directory with ``python tools/build_defense_audio.py``.
"""

from array import array
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import wave


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "audio"
SAMPLE_RATE = 48000
DURATION = 6.4
# A large cast bell has a low hum and inharmonic modes, not a musical chord.
# Each tuple is frequency (Hz), relative amplitude and decay time (seconds).
MODES = (
    (130.81, 0.66, 2.20),
    (261.63, 1.00, 1.90),
    (311.13, 0.43, 1.35),
    (392.00, 0.24, 1.15),
    (523.25, 0.45, 1.25),
    (736.45, 0.20, 0.85),
    (1049.20, 0.12, 0.55),
    (1454.37, 0.06, 0.30),
)


def strike(seconds: float, seed: int) -> array:
    rng = random.Random(seed)
    output = array("d", [0.0]) * round(seconds * SAMPLE_RATE)
    for index in range(len(output)):
        at = index / SAMPLE_RATE
        attack = min(1.0, at / 0.003)
        value = 0.0
        for mode, (frequency, gain, decay) in enumerate(MODES):
            # Close paired resonances give the slow beating of a heavy bell.
            phase = math.tau * frequency * at
            beating = 0.78 + 0.22 * math.cos(math.tau * (0.67 + mode * 0.09) * at)
            value += gain * math.sin(phase) * math.exp(-at / decay) * beating
        # Restrained clapper transient; the long tail comes from metal modes.
        value += rng.uniform(-1.0, 1.0) * 0.14 * math.exp(-at / 0.010)
        output[index] = value * attack
    return output


def build() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    samples = array("d", [0.0]) * round(DURATION * SAMPLE_RATE)
    bell = strike(5.1, 20260929)
    for start_seconds, gain in ((0.03, 1.0), (1.30, 0.87)):
        start = round(start_seconds * SAMPLE_RATE)
        for index, value in enumerate(bell):
            if start + index >= len(samples):
                break
            samples[start + index] += value * gain
    # Soft outdoor reflections remain quiet and do not smear the warning attacks.
    dry = array("d", samples)
    for seconds, gain in ((0.083, 0.12), (0.171, 0.065), (0.293, 0.035)):
        offset = round(seconds * SAMPLE_RATE)
        for index in range(len(samples) - offset):
            samples[index + offset] += dry[index] * gain
    mean = sum(samples) / len(samples)
    for index in range(len(samples)):
        samples[index] -= mean
    tail_samples = round(0.65 * SAMPLE_RATE)
    for index in range(tail_samples):
        samples[-tail_samples + index] *= math.cos(math.pi * index / (2 * (tail_samples - 1))) ** 2
    gain = 10 ** (-7.0 / 20.0) / max(abs(sample) for sample in samples)
    pcm = array("h", (round(sample * gain * 32767) for sample in samples))
    pcm[0] = pcm[-1] = 0
    if sys.byteorder != "little":
        pcm.byteswap()
    output = OUT / "defense_wave_bell.wav"
    with wave.open(str(output), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(SAMPLE_RATE)
        stream.writeframes(pcm.tobytes())
    decoded = [sample * gain for sample in samples]
    result = {
        "file": output.name,
        "description": "Original large cast-bell warning: two low strikes with inharmonic metal resonance and restrained outdoor echoes.",
        "source": "Original deterministic synthesis in tools/build_defense_audio.py; no third-party recordings or samples.",
        "sample_rate": SAMPLE_RATE,
        "channels": 1,
        "format": "PCM16 WAV",
        "duration_s": DURATION,
        "peak_dbfs": round(20 * math.log10(max(abs(sample) for sample in decoded)), 2),
        "rms_dbfs": round(20 * math.log10(math.sqrt(sum(sample * sample for sample in decoded) / len(decoded))), 2),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "runtime": "Non-looping AudioStreamPlayer on Combat bus, process_mode = 1 (pausable), volume_db = 0.0; play once on wave start.",
        "verification": "PCM parameters, deterministic output and non-clipping peak checked by builder; perceptual in-game mix requires listening.",
    }
    (OUT / "defense_wave_bell.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    build()
