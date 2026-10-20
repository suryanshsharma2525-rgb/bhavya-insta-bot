"""Aapki asli photos: assets/photos/ folder.

Naam item ke naam se: cold_coffee_1.jpg, kulhad_pizza_2.jpg, veg_momos.jpg ...
Bot har post me photo ka background hata ke (cut-out) design me lagata hai.
Ek hi photo baar-baar na aaye, iska record data/photo_usage.json me rehta hai.
"""
import datetime as dt
import glob
import hashlib
import json
import os
import re

from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHOTO_DIR = os.path.join(ROOT, "assets", "photos")
CUT_DIR = os.path.join(ROOT, "assets", "cutouts")
USAGE = os.path.join(ROOT, "data", "pin_photo_usage.json")
_S = {}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")


def all_photos():
    return sorted(p for p in glob.glob(os.path.join(PHOTO_DIR, "*"))
                  if p.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".heic")))


def item_of(path, menu):
    f = slug(os.path.splitext(os.path.basename(path))[0])
    best = None
    for m in menu:
        s = slug(m["name"])
        if f.startswith(s) and (not best or len(s) > len(slug(best))):
            best = m["name"]
    return best


def items_with_photos(menu):
    have = {}
    for p in all_photos():
        it = item_of(p, menu)
        if it:
            have.setdefault(it, []).append(p)
    return have


def _usage():
    try:
        return json.load(open(USAGE, encoding="utf-8"))
    except Exception:
        return {}


def pick(item, menu):
    """Item ki wo photo jo sabse purani baar use hui (taaki repeat na lage)."""
    ps = items_with_photos(menu).get(item) or []
    if not ps:
        return None
    u = _usage()
    return sorted(ps, key=lambda p: u.get(os.path.basename(p), ""))[0]


def mark_used(path):
    u = _usage()
    u[os.path.basename(path)] = dt.datetime.utcnow().isoformat()
    os.makedirs(os.path.dirname(USAGE), exist_ok=True)
    json.dump(u, open(USAGE, "w", encoding="utf-8"), indent=1)


def load(path):
    if path.lower().endswith(".heic"):  # iPhone photos
        try:
            from pillow_heif import register_heif_opener
            register_heif_opener()
        except Exception:
            pass
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)  # phone ki photo ulti/tedhi na aaye
    return im.convert("RGB")


def _clean_alpha(cut):
    """Background removal ki galtiyan theek: andar ke chhed bharo (glass), bikhre tukde hatao, kinare soft."""
    try:
        import numpy as np
        from scipy import ndimage as nd
    except Exception:
        return cut
    a = np.asarray(cut.getchannel("A")).astype(np.float32)
    core = a > 110
    lab, n = nd.label(core)
    if n == 0:
        return cut
    sizes = nd.sum(core, lab, range(1, n + 1))
    keep = np.isin(lab, [i + 1 for i, sz in enumerate(sizes) if sz >= 0.04 * sizes.max()])
    filled = nd.binary_fill_holes(nd.binary_closing(keep, iterations=6))
    inner = nd.binary_erosion(filled, iterations=4)
    soft = np.where(filled, a, 0)
    near = nd.binary_dilation(filled, iterations=3)
    soft = np.where(near & ~filled, a * 0.6, soft)
    out = np.where(inner, 255, np.maximum(soft, np.where(filled, 200, 0)))
    res = cut.copy()
    res.putalpha(Image.fromarray(np.clip(out, 0, 255).astype("uint8")))
    return res


def cutout(path):
    """Photo se sirf khana (background hata ke). Cache data/cutouts me. Fail → None."""
    key = hashlib.md5((os.path.basename(path) + str(os.path.getsize(path))).encode()).hexdigest()[:10]
    out = os.path.join(CUT_DIR, f"{slug(os.path.basename(path))}_{key}.png")
    if os.path.exists(out):
        return Image.open(out).convert("RGBA")
    try:
        from rembg import new_session, remove
        if "s" not in _S:
            _S["s"] = new_session("isnet-general-use")  # u2netp se zyada saaf kinare
        im = load(path)
        im.thumbnail((1600, 1600), Image.LANCZOS)
        cut = remove(im, session=_S["s"])
    except Exception as e:
        print("cutout failed:", str(e)[:150])
        return None
    cut = _clean_alpha(cut)
    bb = cut.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()
    if not bb:
        return None
    cut = cut.crop(bb)
    os.makedirs(CUT_DIR, exist_ok=True)
    cut.save(out)
    return cut
