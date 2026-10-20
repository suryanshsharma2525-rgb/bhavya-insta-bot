"""Font matcher: reference me jo font dikh raha hai, wahi (ya sabse kareeb) Google Font laao.

1. Gemini font ka naam guess karta hai (jaise "Bebas Neue", "Playfair Display").
2. Bot google/fonts repo se wo font download karke fonts/ me rakh leta hai (agli baar ke liye bhi).
3. Na mile to category ke hisaab se sabse kareeb local font.
"""
import os
import re
from functools import lru_cache

import requests
from PIL import ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "assets", "fonts")
RAW = "https://raw.githubusercontent.com/google/fonts/main"

# category → (file, variation) jab naam wala font na mile
LOCAL = {
    "display_condensed": ("BebasNeue.ttf", None),
    "display_heavy": ("Anton.ttf", None),
    "display_wide": ("Unbounded.ttf", "Black"),
    "sans": ("Montserrat.ttf", "SemiBold"),
    "sans_bold": ("Montserrat.ttf", "ExtraBold"),
    "geometric": ("Outfit.ttf", "Medium"),
    "serif": ("PlayfairDisplay.ttf", "Bold"),
    "serif_display": ("DMSerifDisplay.ttf", None),
    "serif_fat": ("AbrilFatface.ttf", None),
    "serif_italic": ("PlayfairItalic.ttf", "Italic"),
    "script": ("GreatVibes.ttf", None),
    "script_bold": ("Lobster.ttf", None),
    "brush": ("Pacifico.ttf", None),
    "handwritten": ("Caveat.ttf", "Bold"),
    "retro": ("Shrikhand.ttf", None),
    "devanagari": ("Baloo2.ttf", "Bold"),
}
WEIGHT_NAMES = {"thin": "Thin", "light": "Light", "regular": "Regular", "medium": "Medium", "semibold": "SemiBold",
                "bold": "Bold", "extrabold": "ExtraBold", "black": "Black"}


def _slug(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _meta(slug):
    for lic in ("ofl", "apache", "ufl"):
        try:
            r = requests.get(f"{RAW}/{lic}/{slug}/METADATA.pb", timeout=20)
            if r.status_code == 200:
                return lic, r.text
        except Exception:
            pass
    return None, None


WNUM = {"thin": 100, "light": 300, "regular": 400, "medium": 500, "semibold": 600, "bold": 700, "extrabold": 800,
        "black": 900}


@lru_cache(None)
def fetch(name, italic=False, weight="bold"):
    """Google Font download karo → local file ka naam (ya None)."""
    slug = _slug(name)
    if not slug:
        return None
    os.makedirs(FONT_DIR, exist_ok=True)
    want_w = WNUM.get((weight or "bold").lower().replace("-", "").replace(" ", ""), 700)
    local = []
    for f in os.listdir(FONT_DIR):  # pehle se hai?
        base = _slug(f.split("[")[0].split("-")[0].replace(".ttf", ""))
        if base == slug and (("italic" in f.lower()) == italic):
            local.append(f)

    def lw(f):
        n = _slug(f.split("-", 1)[1].replace(".ttf", "") if "-" in f else "regular").replace("italic", "") or "regular"
        return abs(WNUM.get(n, 400) - want_w)
    if local:
        var = [f for f in local if "[" in f]
        if var:
            return var[0]
        best = min(local, key=lw)
        if lw(best) <= 100:
            return best
    lic, meta = _meta(slug)
    if not meta:
        print(f"Font '{name}' Google Fonts me nahi mila → kareeb wala use hoga")
        return None
    files = re.findall(r'style: "(\w+)"\s+weight: (\d+)\s+filename: "([^"]+)"', meta)
    want = "italic" if italic else "normal"
    cands = [(int(w), f) for st, w, f in files if st == want] or [(int(w), f) for st, w, f in files]
    if not cands:
        return None
    # variable font (saare weights ek file me) sabse achha; warna sabse kareeb weight
    pick = next((f for w, f in cands if "[" in f), None) or min(cands, key=lambda x: abs(x[0] - want_w))[1]
    try:
        r = requests.get(f"{RAW}/{lic}/{slug}/{requests.utils.quote(pick)}", timeout=60)
        r.raise_for_status()
        with open(os.path.join(FONT_DIR, pick), "wb") as fh:
            fh.write(r.content)
        print(f"Font download: {name} → {pick}")
        return pick
    except Exception as e:
        print("Font download failed:", name, str(e)[:120])
        return None


def has_glyph(path, ch):
    try:
        from fontTools.ttLib import TTFont
        return ord(ch) in TTFont(path, lazy=True).getBestCmap()
    except Exception:
        return True


@lru_cache(None)
def _load(file, size, var):
    f = ImageFont.truetype(os.path.join(FONT_DIR, file), size)
    if var:
        try:
            f.set_variation_by_name(var)
        except Exception:
            try:  # kuch variable fonts me naam alag hote hain → axis se weight set
                axes = f.get_variation_axes()
                w = {"Thin": 100, "Light": 300, "Regular": 400, "Medium": 500, "SemiBold": 600, "Bold": 700,
                     "ExtraBold": 800, "Black": 900}.get(var.replace(" Italic", ""), 400)
                f.set_variation_by_axes([max(a["minimum"], min(a["maximum"], w)) if a.get("name") in (b"Weight", "Weight")
                                         else a["default"] for a in axes])
            except Exception:
                pass
    return f


def resolve(name=None, category="sans", weight="bold", italic=False):
    """→ (file, variation)."""
    file = fetch(name, italic, weight or "bold") if name else None
    var = WEIGHT_NAMES.get((weight or "").lower().replace("-", "").replace(" ", ""))
    if file:
        if "[" not in file:  # static font → variation nahi lagta
            var = None
        elif italic and var:
            var = (var + " Italic") if var != "Regular" else "Italic"
        return file, var
    return LOCAL.get(category, LOCAL["sans"])


def font(spec, size):
    f, v = spec
    return _load(f, max(6, int(size)), v)
