"""Do automatic folders:

1. assets/photos/  — khane ki photo KISI BHI naam se daalo. Bot (Gemini) dekh ke:
     • kaunsa menu item hai → naam theek karta hai (cold_coffee_3.jpg), photo seedhi + size theek
     • galti se Pinterest design/poster aa gaya → designs/ me bhej deta hai
     • samajh na aaye → assets/photos/_unsorted/ (bot use nahi karta, aap dekh lena)
2. designs/        — Pinterest designs daalo (jitne chaho). Bot har run me kuch padh ke design-library
                     (data/styles) me save karta hai — turant post NAHI hota. Grid (6/9 posts ek image me)
                     ho to har post alag design ban jaata hai.
"""
import glob
import json
import os
import shutil

from PIL import Image

from . import ai, photos, vision

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESIGNS = os.path.join(ROOT, "designs")
STYLES = os.path.join(ROOT, "data", "styles")
IMG = (".jpg", ".jpeg", ".png", ".webp", ".heic")


def sort_photos(cfg, max_n=12):
    """assets/photos me jinka naam menu item se match nahi karta, unhe pehchaan ke sahi naam do."""
    menu = cfg["menu"]
    todo = [p for p in photos.all_photos() if not photos.item_of(p, menu)][:max_n]
    if not todo:
        return 0
    names = [m["name"] for m in menu]
    done = 0
    for p in todo:
        try:
            im = photos.load(p)
        except Exception as e:
            print("Photo khul nahi paayi:", os.path.basename(p), e)
            continue
        d = ai.call([{"text": (
            "Look at this image for a cafe's Instagram bot. Return JSON: {\"kind\": \"food_photo\" (a real photo of food/"
            "drink) | \"design\" (a designed poster/social post with layout and text) | \"other\", \"item\": the closest "
            f"item from this menu or null: {names}, \"confidence\": 0-1}}")}, ai.image_part(im, 768)],
            cfg, temperature=0.1, timeout=90)
        if not isinstance(d, dict):
            print("AI busy — photo agle run me sort hogi:", os.path.basename(p))
            break
        kind, item = d.get("kind"), d.get("item")
        low = os.path.basename(p).lower()
        if kind != "food_photo" and any(w in low for w in ("design", "template", "post", "poster", "instagram", "social", "banner", "menu", "moodboard")):
            kind = "design"  # naam se hi Pinterest design lagta hai
        if kind == "design":
            os.makedirs(DESIGNS, exist_ok=True)
            shutil.move(p, os.path.join(DESIGNS, os.path.basename(p)))
            print("Design tha → designs/ me bheja:", os.path.basename(p))
        elif kind == "food_photo" and item in names and float(d.get("confidence") or 0) >= 0.5:
            s = photos.slug(item)
            n = 1
            while glob.glob(os.path.join(photos.PHOTO_DIR, f"{s}_{n}.*")):
                n += 1
            im.thumbnail((2000, 2000), Image.LANCZOS)
            im.save(os.path.join(photos.PHOTO_DIR, f"{s}_{n}.jpg"), quality=93)
            os.remove(p)
            print(f"Photo: {os.path.basename(p)} → {s}_{n}.jpg ({item})")
        else:
            un = os.path.join(photos.PHOTO_DIR, "_unsorted")
            os.makedirs(un, exist_ok=True)
            shutil.move(p, os.path.join(un, os.path.basename(p)))
            print("Samajh nahi aayi → assets/photos/_unsorted:", os.path.basename(p))
        done += 1
    return done


def _panels(im, cfg):
    """Ek image me kai posts (grid) hain? → har post ka box."""
    d = ai.call([{"text": (
        "Is this image a GRID/collage of several separate social-media posts? If yes, give the box of EACH separate "
        "post. Return JSON: {\"grid\": true/false, \"panels\": [[ymin,xmin,ymax,xmax], ...] (0-1000)}")},
        ai.image_part(im, 1024)], cfg, temperature=0.1, timeout=120)
    if not isinstance(d, dict) or not d.get("grid"):
        return [im] if isinstance(d, dict) else None
    out = []
    w, h = im.size
    for b in d.get("panels") or []:
        try:
            y0, x0, y1, x1 = [float(v) / 1000 for v in b]
            c = im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
            if c.width > 120 and c.height > 120:
                out.append(c)
        except Exception:
            pass
    return out or [im]


TRIES = os.path.join(ROOT, "data", "pin_design_tries.json")


def _good(spec):
    els = (spec or {}).get("elements") or []
    return any(e.get("type") == "text" for e in els) and any(e.get("type") == "photo" for e in els)


def learn_designs(cfg, max_n=6):
    """designs/ ki images → data/styles (design library). Post nahi hota.
    Koi design 3 baar me bhi samajh na aaye to chhod diya jaata hai (baaki designs nahi rukte)."""
    files = sorted(p for p in glob.glob(os.path.join(DESIGNS, "*")) if p.lower().endswith(IMG))
    if not files:
        return 0
    os.makedirs(STYLES, exist_ok=True)
    try:
        tries = json.load(open(TRIES, encoding="utf-8"))
    except Exception:
        tries = {}
    from .main import _strip
    made = 0
    for p in files:
        if made >= max_n:
            break
        name = os.path.basename(p)
        try:
            ref = photos.load(p)
        except Exception as e:
            print("Design khul nahi paaya, hata diya:", name, e)
            os.remove(p)
            continue
        panels = _panels(ref, cfg)
        if panels is None:
            print("AI busy — design agle run me padha jayega:", name)
            break
        saved, failed = 0, False
        base = photos.slug(os.path.splitext(name)[0][:30]) or "design"
        for i, pan in enumerate(panels[:9]):
            try:
                spec = vision.analyze(pan, cfg)
                if not _good(spec):
                    failed = True
                    continue
                spec = vision.sample_colors(spec, pan)
                spec = vision.reframe(spec, pan.size)
                out = f"lib_{base}_{i + 1}.json"
                json.dump(_strip(spec), open(os.path.join(STYLES, out), "w", encoding="utf-8"), indent=1)
                saved += 1
                made += 1
                print(f"Design library me juda: {out} ({(spec.get('mood') or '')[:70]})")
            except Exception as e:
                print("Design ka ek hissa skip:", name, e)
                failed = True
        tries[name] = tries.get(name, 0) + 1
        if not failed or saved or tries[name] >= 3:
            if failed and not saved:
                print("Ye design 3 baar me samajh nahi aaya — chhod diya:", name)
            os.remove(p)  # public repo — dusre brand ki image nahi rakhni
            tries.pop(name, None)
        else:
            print(f"Design agle run me dobara padha jayega ({tries[name]}/3):", name)
    os.makedirs(os.path.dirname(TRIES), exist_ok=True)
    json.dump(tries, open(TRIES, "w", encoding="utf-8"), indent=1)
    return made


def housekeeping(cfg):
    """Har run ki shuruaat me: nayi photos sort + naye designs padho."""
    try:
        sort_photos(cfg)
    except Exception as e:
        print("photo sort skip:", e)
    try:
        learn_designs(cfg, int((cfg.get("pin") or {}).get("designs_per_run", 6)))
    except Exception as e:
        print("design library skip:", e)
