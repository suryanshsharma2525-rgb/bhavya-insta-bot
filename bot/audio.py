"""Music brain + sound effects.

- assets/music/ me koi bhi gaana daalo (naam kuch bhi). Bot har gaane ka BPM, energy, brightness aur
  sabse 'catchy' hissa (chorus/drop) khud nikaal ke data/music_index.json me yaad rakhta hai.
- Reel ke vibe ke hisaab se sahi gaana + sahi start point chunta hai.
- Transitions pe whoosh, price pe pop, bade text pe boom, logo pe shimmer — sab beat ke saath mix.
"""
import glob
import json
import os
import random
import re
import subprocess
import wave

import numpy as np

from . import render as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "data", "music_index.json")
SR = 44100
MOOD_WORDS = {  # order = priority
    "game": ["game", "tension", "countdown", "suspense", "arcade"],
    "desi": ["desi", "indian", "dhol", "bollywood", "sitar", "tabla", "punjabi", "bhangra"],
    "cinematic": ["cinematic", "epic", "luxury", "ambient", "piano", "elegant", "inspiring"],
    "upbeat": ["upbeat", "happy", "pop", "fun", "energetic", "dance", "summer", "funk", "house"],
    "lofi": ["lofi", "lo-fi", "chill", "calm", "relax", "jazz", "acoustic", "cafe", "coffee"],
}


def _decode(path, seconds=None, sr=22050):
    cmd = [R.ffmpeg_bin(), "-v", "error", "-i", path]
    if seconds:
        cmd += ["-t", str(seconds)]
    cmd += ["-ac", "1", "-ar", str(sr), "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def analyze(path):
    x = _decode(path, 120)
    sr = 22050
    if len(x) < sr * 3:
        return None
    hop = 512
    frames = len(x) // hop
    e = np.sqrt(np.array([np.mean(x[i * hop:(i + 1) * hop] ** 2) for i in range(frames)]) + 1e-9)
    on = np.maximum(np.diff(np.log(e + 1e-6)), 0)
    on -= on.mean()
    fps = sr / hop
    m = re.search(r"(\d{2,3})\s*bpm", os.path.basename(path).lower())
    if m:
        bpm = int(m.group(1))
    else:
        best, bpm = -1, 100
        for b in range(70, 171):
            lag = int(round(fps * 60 / b))
            if lag < len(on):
                v = float(np.dot(on[:-lag], on[lag:]))
                if v > best:
                    best, bpm = v, b
    spec = np.abs(np.fft.rfft(x[: sr * 30] * np.hanning(min(len(x), sr * 30))))
    freqs = np.fft.rfftfreq(min(len(x), sr * 30), 1 / sr)
    bright = float((spec * freqs).sum() / (spec.sum() + 1e-9))
    # catchy start: 8-sec window with highest energy after first 4 sec (chorus / drop)
    win = int(8 * fps)
    cs = np.convolve(e, np.ones(win), "valid")
    start_f = int(np.argmax(cs[int(4 * fps):])) + int(4 * fps) if len(cs) > int(4 * fps) else 0
    start = max(0.0, round(start_f / fps - 0.5, 2))
    name = os.path.basename(path).lower()
    mood = next((k for k, ws in MOOD_WORDS.items() if any(w in name for w in ws)), None)
    energy = float(e.mean())
    if not mood:
        mood = "upbeat" if bpm >= 108 and energy > 0.08 else ("desi" if 90 <= bpm < 108 and bright < 1800 else
                                                            ("cinematic" if bright < 1400 and bpm < 90 else "lofi"))
    dur = len(x) / sr
    return {"bpm": bpm, "energy": round(energy, 4), "brightness": round(bright), "mood": mood, "best_start": start,
            "seconds": round(dur, 1)}


def index():
    try:
        idx = json.load(open(INDEX, encoding="utf-8"))
    except Exception:
        idx = {}
    files = sorted(glob.glob(R.A("music", "*.mp3")) + glob.glob(R.A("music", "*.m4a")) + glob.glob(R.A("music", "*.wav")))
    changed = False
    for f in files:
        k = os.path.basename(f)
        sig = f"{os.path.getsize(f)}"
        if k in idx and idx[k].get("sig") == sig:
            continue
        a = analyze(f)
        if a:
            a["sig"] = sig
            idx[k] = a
            changed = True
            print(f"Music: {k} → {a['mood']}, {a['bpm']} BPM, start {a['best_start']}s")
    for k in list(idx):
        if not os.path.exists(R.A("music", k)):
            idx.pop(k)
            changed = True
    if changed:
        os.makedirs(os.path.dirname(INDEX), exist_ok=True)
        json.dump(idx, open(INDEX, "w", encoding="utf-8"), indent=1)
    return idx


VIBE_MOOD = {"calm_luxury": ["cinematic", "lofi"], "cosy": ["lofi", "cinematic"], "energetic": ["upbeat", "game"],
             "festive": ["desi", "upbeat"], "fresh_day": ["upbeat", "lofi"], "playful": ["upbeat", "game"],
             "desi_warm": ["desi", "upbeat"]}


def pick(mood=None, vibe=None, seed="", recent=()):
    idx = index()
    if not idx:
        return None, 100, 0.0, 0
    wants = ([mood] if mood else []) + VIBE_MOOD.get(vibe or "", [])
    cands = []
    for w in wants:
        cands = [k for k, v in idx.items() if v["mood"] == w]
        if cands:
            break
    cands = cands or list(idx)
    fresh = [k for k in cands if k not in recent] or cands
    k = random.Random(f"music-{seed}").choice(fresh)
    v = idx[k]
    return R.A("music", k), v["bpm"], v["best_start"], v.get("seconds", 999)


# ---------------------------------------------------------------- sound effects (synth, copyright-free)
def _t(d):
    return np.arange(int(d * SR)) / SR


def sfx(kind):
    rng = np.random.default_rng(7)
    if kind == "whoosh":
        t = _t(0.5)
        n = rng.standard_normal(len(t))
        env = np.sin(np.pi * t / 0.5) ** 2
        # sweep: moving low-pass via cumulative smoothing
        out = np.zeros_like(n)
        a = 0.0
        for i in range(len(n)):
            k = 0.02 + 0.25 * env[i]
            a += k * (n[i] - a)
            out[i] = a
        return out * env * 0.9
    if kind == "pop":
        t = _t(0.14)
        f = 900 * np.exp(-t * 25) + 300
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 30) * 0.7
    if kind == "boom":
        t = _t(0.9)
        f = 45 + 80 * np.exp(-t * 12)
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4) + 0.25 * rng.standard_normal(len(t)) * np.exp(-t * 20)) * 0.9
    if kind == "shimmer":
        t = _t(1.2)
        y = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * (2 + i)) for i, f in enumerate([1568, 2093, 2637, 3136]))
        return y * 0.18 * np.minimum(1, t * 20)
    if kind == "tick":
        t = _t(0.04)
        return np.sin(2 * np.pi * 2200 * t) * np.exp(-t * 120) * 0.4
    return np.zeros(1)


def mix(total, music, start, events, out_wav, music_vol=0.85, sfx_vol=0.55):
    n = int(total * SR)
    L = np.zeros(n, np.float32)
    if music:
        raw = subprocess.run([R.ffmpeg_bin(), "-v", "error", "-ss", str(start), "-stream_loop", "-1", "-i", music,
                              "-t", str(total), "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"], capture_output=True).stdout
        m = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
        m = m[:n]
        L[:len(m)] += m * music_vol
        fi, fo = int(0.3 * SR), int(1.6 * SR)
        L[:fi] *= np.linspace(0, 1, fi)
        L[-fo:] *= np.linspace(1, 0, fo)
    cache = {}
    for t0, kind in events:
        s = cache.setdefault(kind, sfx(kind))
        i = int(t0 * SR)
        j = min(n, i + len(s))
        if 0 <= i < n:
            L[i:j] += s[:j - i] * sfx_vol
    peak = np.max(np.abs(L)) or 1
    L = np.clip(L / max(1.0, peak / 0.95), -1, 1)
    st = np.stack([L, L], 1)
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())
    return out_wav
