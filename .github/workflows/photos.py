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


def is_dark(path):
    """Kaale studio-background wali photo (reel frame jaisi) — ye sirf cutout ke liye achhi hai, poori photo ke liye nahi."""
    try:
        im = Image.open(path)
        im.draft("RGB", (400, 400))
        return _dark_bg(im.convert("RGB"))
    except Exception:
        return False


def pick(item, menu, plain=False):
    """Item ki wo photo jo sabse purani baar use hui (taaki repeat na lage).
    plain=True → design me poori photo dikhti hai, to kaale-background wali photos chhodo (agar doosri hain)."""
    ps = items_with_photos(menu).get(item) or []
    if not ps:
        return None
    if plain:
        ps = [p for p in ps if not is_dark(p)] or ps
    u = _usage()

    def key(p):  # sabse purana istemaal pehle; "_web" (chhoti internet photos) ko kam baari milti hai
        t = u.get(os.path.basename(p), "")
        if "_web" in os.path.basename(p).lower() and t:
            try:
                t = (dt.datetime.fromisoformat(t) + dt.timedelta(days=4)).isoformat()
            except Exception:
                pass
        return (t, "_web" in os.path.basename(p).lower())
    return sorted(ps, key=key)[0]


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


def _dark_bg(im):
    """Photo ka background kaala/gehra hai? (studio / reel style)"""
    import numpy as np
    a = np.asarray(im.convert("L").resize((200, 200)), np.float32)
    border = np.concatenate([a[:8].ravel(), a[-8:].ravel(), a[:, :8].ravel(), a[:, -8:].ravel()])
    return border.mean() < 40 and float(np.percentile(border, 90)) < 75


def _dark_cut(im, session):
    """Gehre background wali photo: patli gold ring/letters mitao → background removal → sirf roshan khana rakho."""
    import numpy as np
    from scipy import ndimage as nd
    from rembg import remove
    a = np.asarray(im).copy()
    lum = a.astype(np.float32).mean(2)
    m = lum > 42
    thin = nd.binary_dilation(m & ~nd.binary_opening(m, iterations=4), iterations=2)
    med = np.stack([nd.median_filter(a[..., k], size=15) for k in range(3)], -1)
    clean = np.where(thin[..., None], np.minimum(med, 30), a).astype("uint8")  # ring ki jagah gehra rang
    al = np.asarray(remove(Image.fromarray(clean), session=session).getchannel("A")).astype(np.float32) / 255
    food = nd.binary_dilation(nd.binary_fill_holes(nd.binary_opening(lum > 26, iterations=3)), iterations=8)
    al = al * food
    core = al > 0.4
    lab, n = nd.label(core)
    if n:
        sizes = nd.sum(core, lab, range(1, n + 1))
        core = np.isin(lab, [i + 1 for i, sz in enumerate(sizes) if sz >= 0.06 * max(sizes)])
    keep = nd.binary_fill_holes(nd.binary_closing(core, iterations=10))
    al = np.where(nd.binary_erosion(keep, iterations=3), 1.0, np.where(keep, np.maximum(al, 0.8), 0))
    out = Image.fromarray(a).convert("RGBA")
    out.putalpha(Image.fromarray((nd.gaussian_filter(al, 1.0) * 255).astype("uint8")))
    return out


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
        if _dark_bg(im):
            cut = _dark_cut(im, _S["s"])
        else:
            cut = _clean_alpha(remove(im, session=_S["s"]))
    except Exception as e:
        print("cutout failed:", str(e)[:150])
        return None
    bb = cut.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()
    if not bb:
        return None
    cut = cut.crop(bb)
    os.makedirs(CUT_DIR, exist_ok=True)
    cut.save(out)
    return cut
