"""Design style cards (aapke Pinterest references se) + naye references ka auto-analysis.

- data/reference_styles.json : style cards (colours, fonts, template, vibe)
- assets/references/images/  : yahan naya design screenshot daalo → Gemini dekh ke style card banata hai
- assets/references/videos/  : yahan pasand ki reel daalo → Gemini pacing/transitions samajh ke motion preset banata hai
Originals analysis ke baad hata diye jaate hain (repo public hai, dusre brands ki files nahi rakhte).
"""
import base64
import glob
import json
import os
import random
import time

import requests

from . import ai
from .templates import TEMPLATES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS = os.path.join(ROOT, "data", "reference_styles.json")
MOTION = os.path.join(ROOT, "data", "reference_motion.json")
REF_IMG = os.path.join(ROOT, "assets", "references", "images")
REF_VID = os.path.join(ROOT, "assets", "references", "videos")
FONT_CHOICES = {
    "display": ["Anton.ttf", "BebasNeue.ttf", "ArchivoBlack.ttf", "AbrilFatface.ttf", "RubikDirt.ttf", "Oswald.ttf",
                "Unbounded.ttf", "Shrikhand.ttf", "Fraunces.ttf", "RozhaOne.ttf", "Righteous.ttf"],
    "serif": ["DMSerifDisplay.ttf", "PlayfairDisplay.ttf", "Cormorant.ttf", "AbrilFatface.ttf", "Fraunces.ttf",
              "YesevaOne.ttf", "Marcellus.ttf"],
    "script": ["GreatVibes.ttf", "Pacifico.ttf", "DancingScript.ttf", "Caveat.ttf", "Sacramento.ttf", "Lobster.ttf"],
    "sans": ["Montserrat.ttf", "Poppins-Medium.ttf", "Syne.ttf", "Oswald.ttf", "Outfit.ttf", "SpaceGrotesk.ttf",
             "JosefinSans.ttf", "Bricolage.ttf", "Baloo2.ttf"],
}


def load_cards():
    try:
        with open(CARDS, encoding="utf-8") as fh:
            return [c for c in json.load(fh) if c.get("template") in TEMPLATES]
    except Exception:
        return []


def choose(history, seed, vibe=None, perf=None, prefer=None):
    """Recent 4 posts wale designs avoid; jo design zyada chala uska chance badhta hai.
    prefer = winner din pe recipe wala design (agar pichhle 2 posts me nahi aaya)."""
    cards = load_cards()
    if not cards:
        return None
    if prefer and prefer not in [h.get("design") for h in history[-2:]]:
        hit = [c for c in cards if c["id"] == prefer]
        if hit:
            return hit[0]
    recent = [h.get("design") for h in history[-4:]]
    pool = [c for c in cards if c["id"] not in recent] or cards
    if vibe:
        pool = [c for c in pool if c.get("vibe") == vibe] or pool
    rng = random.Random(f"design-{seed}")
    weights = [max(0.2, 1.0 + 2.0 * (perf or {}).get(c["id"], 0)) for c in pool]
    return rng.choices(pool, weights=weights, k=1)[0]


def describe(card):
    return f"{card['id']} (template {card['template']}, inspired by '{card.get('ref', '')}', vibe {card.get('vibe')})"


# ---------------------------------------------------------------- reference analysis (Gemini vision)
def _gemini_media(parts, cfg):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    model = ai._MODEL_CACHE.get("model") or ai._pick_model(key, cfg.get("ai", {}).get("model", "gemini-flash-latest"))
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"contents": [{"parts": parts}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0.4}}
    try:
        r = requests.post(url, params={"key": key}, json=body, timeout=180)
        r.raise_for_status()
        return json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
    except Exception as e:
        print("Gemini reference analysis failed:", str(e)[:200])
        return None


def _palette_from_image(path):
    """Mashine se image ke main colours nikaalo (k-means jaisa, PIL quantize)."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im.thumbnail((200, 200))
    q = im.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[:18]
    counts = sorted(q.getcolors(), reverse=True)
    cols = [tuple(pal[i * 3:i * 3 + 3]) for _, i in counts]
    return ["#%02x%02x%02x" % c for c in cols]


def analyze_new_references(cfg):
    os.makedirs(REF_IMG, exist_ok=True)
    os.makedirs(REF_VID, exist_ok=True)
    cards = load_cards()
    added = 0
    for path in sorted(glob.glob(os.path.join(REF_IMG, "*"))):
        if not path.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        colours = _palette_from_image(path)
        mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
        with open(path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode()
        prompt = (
            "You are a senior graphic designer. Study this social-media food poster and describe its DESIGN SYSTEM so we can "
            "make an ORIGINAL post for our own cafe in the same style (we will not copy its text, logo or photos).\n"
            f"Dominant colours detected: {colours}\n"
            f"Pick the closest layout template from: {list(TEMPLATES)}\n"
            "Return JSON: {\"template\": ..., \"vibe\": one of [calm_luxury, energetic, cosy, festive, fresh_day, playful, desi_warm], "
            "\"mood\": one of [lofi, upbeat, desi, cinematic], \"light\": true/false, "
            "\"palette\": {\"bg\": hex, \"panel\": hex, \"panel2\": hex, \"word\": hex (big display text colour), "
            "\"text\": hex (main text), \"text2\": hex}, "
            f"\"fonts\": {{\"display\": one of {FONT_CHOICES['display']}, \"serif\": one of {FONT_CHOICES['serif']}, "
            f"\"script\": one of {FONT_CHOICES['script']}, \"sans\": one of {FONT_CHOICES['sans']}}}, "
            "\"params\": {}, \"name\": short name for this style}"
        )
        d = _gemini_media([{"text": prompt}, {"inline_data": {"mime_type": mime, "data": b64}}], cfg)
        if not isinstance(d, dict) or d.get("template") not in TEMPLATES:
            print("Reference skip (analysis nahi hua, agli baar try hoga):", os.path.basename(path))
            continue
        fonts = {}
        for role, f in (d.get("fonts") or {}).items():
            if role in FONT_CHOICES and f in FONT_CHOICES[role]:
                var = {"Montserrat.ttf": "SemiBold", "PlayfairDisplay.ttf": "Bold", "Cormorant.ttf": "Bold",
                       "Oswald.ttf": "Bold", "Syne.ttf": "Bold", "Caveat.ttf": "Bold", "DancingScript.ttf": "Bold",
                       "Unbounded.ttf": "Black", "Fraunces.ttf": "Bold", "Outfit.ttf": "SemiBold", "SpaceGrotesk.ttf": "Bold",
                       "JosefinSans.ttf": "SemiBold", "Bricolage.ttf": "Bold", "Baloo2.ttf": "Bold"}.get(f)
                fonts[role] = [f, var]
        pal = {k: v for k, v in (d.get("palette") or {}).items() if isinstance(v, str) and v.startswith("#")}
        for k, fallback in (("bg", colours[0]), ("panel", colours[1 % len(colours)]), ("word", colours[-1]), ("text", "#ffffff")):
            pal.setdefault(k, fallback)
        card = {"id": f"ref_{int(time.time())}_{added}", "ref": d.get("name") or os.path.basename(path),
                "template": d["template"], "vibe": d.get("vibe", "cosy"), "mood": d.get("mood", "lofi"),
                "light": bool(d.get("light")), "palette": pal, "fonts": fonts, "params": d.get("params") or {}}
        cards.append(card)
        os.remove(path)  # original hata do (public repo)
        added += 1
        print("Naya style card:", card["id"], card["template"], card["ref"])
    if added:
        with open(CARDS, "w", encoding="utf-8") as fh:
            json.dump(cards, fh, indent=1, ensure_ascii=False)
    added += analyze_reference_videos(cfg)
    return added


def analyze_reference_videos(cfg):
    """Reference reel → pacing (cuts/sec), transitions, text animation → data/reference_motion.json"""
    key = os.environ.get("GEMINI_API_KEY")
    vids = [p for p in glob.glob(os.path.join(REF_VID, "*")) if p.lower().endswith((".mp4", ".mov", ".webm"))]
    if not key or not vids:
        return 0
    try:
        presets = json.load(open(MOTION, encoding="utf-8"))
    except Exception:
        presets = []
    n = 0
    for path in vids:
        size = os.path.getsize(path)
        if size > 19 * 1024 * 1024:
            print("Reference video 19MB se bada hai, chhota karke daalo:", os.path.basename(path))
            continue
        with open(path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode()
        prompt = (
            "Analyse this Instagram food reel's EDITING STYLE (not its content). Return JSON: "
            "{\"avg_scene_seconds\": number, \"total_seconds\": number, \"energy\": one of [calm, medium, high], "
            "\"transitions\": 2-4 of [cut, flash, push, zoom, sweep, fade, circle, blinds, whip, leak, slide_up], "
            "\"text_anims\": 2-3 of [rise, scale, blur, words, split, typewriter, mask, letters, bounce, track], "
            "\"backgrounds\": 1-2 of [rays, bokeh, blobs, grid, stripes, spotlight, grain, rings], "
            "\"structure\": short list of scene types in order (hook, product, price, list, cta, logo), \"name\": short name}"
        )
        d = _gemini_media([{"text": prompt}, {"inline_data": {"mime_type": "video/mp4", "data": b64}}], cfg)
        if isinstance(d, dict) and d.get("transitions"):
            d["id"] = f"motion_{int(time.time())}_{n}"
            presets.append(d)
            os.remove(path)
            n += 1
            print("Naya motion preset:", d.get("name"))
    if n:
        with open(MOTION, "w", encoding="utf-8") as fh:
            json.dump(presets, fh, indent=1, ensure_ascii=False)
    return n


def motion_preset(seed):
    try:
        presets = json.load(open(MOTION, encoding="utf-8"))
    except Exception:
        return None
    return random.Random(f"mp-{seed}").choice(presets) if presets else None
