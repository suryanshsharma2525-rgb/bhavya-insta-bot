"""Gemini (free) — free-tier limits ke hisaab se: gap, model fallback, cooldown."""
import json
import os
import re

import requests

_MODEL_CACHE = {}


def _pick_model(key, wanted):
    """Config wala model na mile (Google naam badalta rehta hai) to available 'flash' text model khud dhundo."""
    if "model" in _MODEL_CACHE:
        return _MODEL_CACHE["model"]
    try:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", params={"key": key, "pageSize": 200},
                         timeout=30)
        r.raise_for_status()
        models = [m["name"].split("/", 1)[1] for m in r.json().get("models", [])
                  if "generateContent" in m.get("supportedGenerationMethods", [])]
    except Exception as e:
        print("Model list failed:", e)
        models = []
    if wanted in models:
        choice = wanted
    else:
        def score(n):
            bad = any(x in n for x in ("image", "tts", "audio", "live", "embedding", "vision", "thinking", "exp"))
            return (bad, "flash" not in n, "lite" in n, "preview" in n, "latest" not in n, [-ord(c) for c in n])
        cands = sorted(models, key=score)
        choice = cands[0] if cands else "gemini-flash-latest"
        print(f"Model '{wanted}' nahi mila → '{choice}' use kar rahe hain")
    _MODEL_CACHE["model"] = choice
    return choice


_LAST = {"t": 0.0, "fails": 0, "down_until": 0.0}
_COOL = {}  # model → is time tak use mat karo (limit lagi thi)
FALLBACK_MODELS = ["gemini-flash-lite-latest", "gemini-2.5-flash-lite", "gemini-2.5-flash"]


def call(parts, cfg, temperature=1.0, timeout=120, json_out=True, quality=False):
    """Gemini ko ek request — free tier ke hisaab se:
    - har call ke beech thoda gap
    - kisi model pe limit (429) / busy (503) → us model ko 90 sec side me rakho, turant agla model
    - sab models thake hon tab hi wait; lagatar fail → 5 min AI band, bot bina AI ke aage chalta hai"""
    import time
    key = os.environ.get("GEMINI_API_KEY")
    if not key or _MODEL_CACHE.get("dead") or time.time() < _LAST["down_until"]:
        return None
    gap = float(cfg.get("ai", {}).get("min_interval_s", 4.0))
    wanted = cfg.get("ai", {}).get("model", "gemini-flash-latest")
    first = _MODEL_CACHE.get("model", wanted)
    fb = ["gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-2.5-flash-lite"] if quality else FALLBACK_MODELS
    chain = [first] + [m for m in fb if m != first]  # quality=True: design padhne ke liye pehle bade models
    body = {"contents": [{"parts": parts}], "generationConfig": {"temperature": temperature}}
    if json_out:
        body["generationConfig"]["responseMimeType"] = "application/json"
    for attempt in range(6):
        now = time.time()
        ready = [m for m in chain if _COOL.get(m, 0) <= now]
        if not ready:  # sab models pe limit → sabse jaldi khulne wale ka wait (max 45s)
            m = min(chain, key=lambda x: _COOL.get(x, 0))
            time.sleep(min(45, max(1, _COOL[m] - now)))
            ready = [m]
        model = ready[0]
        wait = _LAST["t"] + gap - time.time()
        if wait > 0:
            time.sleep(wait)
        _LAST["t"] = time.time()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            r = requests.post(url, params={"key": key}, json=body, timeout=timeout)
            if r.status_code == 404:  # ye model nahi hai
                if model == first and model == _MODEL_CACHE.get("model", wanted):
                    _MODEL_CACHE.pop("model", None)
                    new = _pick_model(key, "__none__" if model == wanted else wanted)
                    chain[0] = first = new
                _COOL[model] = time.time() + 3600
                continue
            if r.status_code in (429, 500, 503):
                _COOL[model] = time.time() + (90 if r.status_code == 429 else 30)
                print(f"Gemini {model}: {r.status_code} ({'limit' if r.status_code == 429 else 'busy'}) → doosra model")
                continue
            r.raise_for_status()
            txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            _LAST["fails"] = 0
            return json.loads(txt) if json_out else txt
        except requests.exceptions.Timeout:
            _COOL[model] = time.time() + 60
            print(f"Gemini {model}: timeout → doosra model")
        except Exception as e:
            safe = re.sub(r"key=[^&\s]+", "key=***", str(e))
            print(f"Gemini {model} failed: {safe[:160]}")
            if attempt >= 2:
                break
    _LAST["fails"] += 1
    if _LAST["fails"] >= 3:
        _LAST["down_until"] = time.time() + 300
        print("Gemini abhi lagatar busy hai — agle 5 minute AI ke bina chal rahe hain.")
    return None


def text(prompt, cfg, temperature=0.9):
    return call([{"text": prompt}], cfg, temperature=temperature, timeout=90)


def image_part(im, maxside=1280, q=90):
    import base64
    import io
    im = im.convert("RGB").copy()
    im.thumbnail((maxside, maxside))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=q)
    return {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(b.getvalue()).decode()}}
