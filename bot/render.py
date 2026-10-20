"""Draws every post in the Bhavya black-gold theme. Output: 1080x1350 JPEGs (and a 1080x1920 reel)."""
import glob
import math
import os
import random
import re
import shutil
import subprocess
import tempfile
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = lambda *p: os.path.join(ROOT, "assets", *p)

W, H = 1080, 1350

# ---------------------------------------------------------------- colour themes
# Har post alag theme me ban sakta hai (config.yaml → themes). Logo hamesha gold rehta hai.
GOLDS = [(0, (247, 222, 146)), (0.45, (219, 170, 82)), (0.8, (178, 124, 44)), (1, (236, 196, 112))]
THEMES = {
    "classic_gold": dict(bg=(14, 13, 11), card=(24, 22, 18), panel=(20, 18, 15), line=(120, 92, 44), alt=(40, 30, 14),
                         gold=(212, 162, 76), stops=GOLDS, cream=(246, 236, 214), muted=(150, 138, 115)),
    "emerald": dict(bg=(8, 34, 25), card=(14, 48, 36), panel=(11, 41, 31), line=(122, 140, 80), alt=(18, 62, 45),
                    gold=(214, 170, 84), stops=GOLDS, cream=(246, 240, 220), muted=(150, 175, 150)),
    "maroon": dict(bg=(40, 9, 15), card=(58, 16, 24), panel=(50, 13, 19), line=(150, 96, 60), alt=(74, 20, 30),
                   gold=(222, 172, 86), stops=GOLDS, cream=(250, 236, 222), muted=(196, 150, 140)),
    "midnight": dict(bg=(9, 14, 32), card=(18, 27, 54), panel=(14, 21, 44), line=(110, 116, 150), alt=(26, 36, 74),
                     gold=(230, 182, 92), stops=GOLDS, cream=(240, 240, 250), muted=(150, 160, 192)),
    "kulhad": dict(bg=(44, 21, 11), card=(66, 33, 18), panel=(56, 27, 14), line=(176, 112, 60), alt=(92, 44, 20),
                   gold=(240, 168, 88),
                   stops=[(0, (255, 218, 160)), (0.45, (242, 166, 82)), (0.8, (204, 108, 44)), (1, (252, 192, 112))],
                   cream=(255, 242, 224), muted=(214, 172, 140)),
}
THEME = "classic_gold"


LIGHT = False


def set_theme_dict(name, t):
    THEMES[name] = t
    return set_theme(name)


def set_theme(name):
    global THEME, BG, CARD, PANEL, LINE, ALT, GOLD, GOLD_STOPS, CREAM, MUTED, LIGHT, FONTPACK, ACCENT2
    name = name if name in THEMES else "classic_gold"
    t = THEMES[name]
    THEME = name
    LIGHT = bool(t.get("light"))
    BG, CARD, PANEL, LINE, ALT = t["bg"], t["card"], t["panel"], t["line"], t["alt"]
    GOLD, GOLD_STOPS, CREAM, MUTED = t["gold"], t["stops"], t["cream"], t["muted"]
    ACCENT2 = tuple(t.get("accent2") or t["alt"])
    _gradient.cache_clear()
    return name


# ---------------------------------------------------------------- basics
@lru_cache(None)
def font(name, size, var=None):
    f = ImageFont.truetype(A("fonts", name), size)
    if var:
        try:
            f.set_variation_by_name(var)
        except Exception:
            pass
    return f


FONTPACK = None  # style.py set karta hai (AI Art Director)
_ROLE = {"impact": "display", "bold": "head", "serif": "serif", "script": "italic", "med": "body", "reg": "body2"}


@lru_cache(None)
def has_rupee(f):
    try:
        from fontTools.ttLib import TTFont
        return 0x20B9 in TTFont(A("fonts", f), lazy=True).getBestCmap()
    except Exception:
        return True


def F(kind, size):
    if FONTPACK:
        f, v = FONTPACK[_ROLE[kind]]
        if kind in ("bold", "med", "reg") and not has_rupee(f):  # price (₹) kabhi dabba na bane
            return font("Montserrat.ttf", size, {"bold": "ExtraBold", "med": "SemiBold", "reg": "Regular"}[kind])
        return font(f, size, v)
    return {"serif": lambda: font("PlayfairDisplay.ttf", size, "Bold"),
            "bold": lambda: font("Poppins-Bold.ttf", size),
            "med": lambda: font("Poppins-Medium.ttf", size),
            "reg": lambda: font("Poppins-Regular.ttf", size),
            "script": lambda: font("DancingScript.ttf", size, "Bold"),
            "impact": lambda: font("Anton.ttf", size)}[kind]()


@lru_cache(None)
def _gradient(w, h, _theme=None):
    import numpy as np
    xs = np.linspace(0, 1, w)[None, :]
    ys = np.linspace(0, 1, h)[:, None]
    t = np.clip(xs * 0.7 + ys * 0.3, 0, 1)
    pos = [s[0] for s in GOLD_STOPS]
    rgb = np.dstack([np.interp(t, pos, [s[1][j] for s in GOLD_STOPS]) for j in range(3)])
    return Image.fromarray(rgb.astype("uint8"), "RGB")


def gold_text(img, xy, text, f, anchor="mm", shadow=True):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=f, fill=255, anchor=anchor)
    bbox = mask.getbbox()
    if not bbox:
        return
    if shadow:
        sh = mask.filter(ImageFilter.GaussianBlur(6))
        img.paste((0, 0, 0), (0, 0), sh.point(lambda v: int(v * 0.8)))
    grad = _gradient(max(1, bbox[2] - bbox[0]), max(1, bbox[3] - bbox[1]), THEME)
    layer = Image.new("RGB", img.size)
    layer.paste(grad, bbox[:2])
    img.paste(layer, (0, 0), mask)


def text(img, xy, s, f, fill=None, anchor="mm"):
    fill = fill or CREAM
    ImageDraw.Draw(img).text(xy, s, font=f, fill=fill, anchor=anchor)


def wrap(s, f, maxw):
    words, lines, cur = s.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if f.getlength(t) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


def fit(s, kind, maxw, maxh, start=90, minimum=34, spacing=1.18):
    size = start
    while size >= minimum:
        f = F(kind, size)
        lines = wrap(s, f, maxw)
        if len(lines) * size * spacing <= maxh and all(f.getlength(l) <= maxw for l in lines):
            return f, lines, size
        size -= 3
    f = F(kind, minimum)
    return f, wrap(s, f, maxw), minimum


def block(img, s, kind, box, gold=False, fill=None, start=90, minimum=34, spacing=1.18):
    fill = fill or CREAM
    x0, y0, x1, y1 = box
    f, lines, size = fit(s, kind, x1 - x0, y1 - y0, start, minimum, spacing)
    lh = size * spacing
    y = (y0 + y1) / 2 - lh * (len(lines) - 1) / 2
    for l in lines:
        if gold:
            gold_text(img, ((x0 + x1) / 2, y), l, f)
        else:
            text(img, ((x0 + x1) / 2, y), l, f, fill)
        y += lh


def ffmpeg_bin():
    """System ffmpeg, warna pip wala (imageio-ffmpeg) — GitHub ke naye server pe ffmpeg pehle se nahi hota."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raise SystemExit("ffmpeg nahi mila. requirements.txt me 'imageio-ffmpeg' hona chahiye.")


def _emoji_name(ch):
    cps = [f"{ord(c):x}" for c in ch]
    if "200d" not in cps:
        cps = [c for c in cps if c != "fe0f"]
    return "-".join(cps)


@lru_cache(None)
def _emoji_raw(ch):
    import io
    import zipfile
    try:  # sharp Twemoji (CC-BY 4.0), sab ek zip me packed
        with zipfile.ZipFile(A("emoji.zip")) as z:
            im = Image.open(io.BytesIO(z.read(_emoji_name(ch) + ".png"))).convert("RGBA")
        return im.crop(im.getbbox())
    except (KeyError, FileNotFoundError):
        pass
    f = font("NotoColorEmoji.ttf", 109)
    im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((80, 80), ch, font=f, embedded_color=True, anchor="mm")
    return im.crop(im.getbbox() or (0, 0, 160, 160))


def emoji(ch, size, angle=0):
    im = _emoji_raw(ch)
    k = size / max(im.size)
    im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    if angle:
        im = im.rotate(angle, expand=True, resample=Image.BICUBIC)
    return im


def paste_c(img, im, cx, cy):
    img.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)


def glow(img, cx, cy, r, alpha=70):
    g = Image.new("L", img.size, 0)
    ImageDraw.Draw(g).ellipse((cx - r, cy - r, cx + r, cy + r), fill=alpha)
    g = g.filter(ImageFilter.GaussianBlur(r / 2.5))
    img.paste(GOLD, (0, 0), g)


def rrect(img, box, r=36, fill=None, outline=None, width=3):
    ImageDraw.Draw(img).rounded_rectangle(box, r, fill=fill or CARD, outline=outline or GOLD, width=width)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def menu_emoji(cfg, name):
    for m in cfg["menu"] + cfg.get("weekly_offer", {}).get("free_items", []):
        if m["name"].lower() == str(name).lower():
            return m.get("emoji", "🍽️")
    return "🍽️"


def item_visual(img, cfg, name, cx, cy, size, rng=random):
    """Real photo (assets/photos) → AI photo (assets/photos_ai) → emoji fallback."""
    from .photos import photos_for
    files, kind = photos_for(name)
    if files:
        ph = Image.open(rng.choice(files)).convert("RGB")
        s = min(ph.size)
        ph = ph.crop(((ph.width - s) // 2, (ph.height - s) // 2, (ph.width + s) // 2, (ph.height + s) // 2))
        if kind == "ai":
            # AI photos have a black background → soft feathered edge so the dish "floats" on the poster
            big = int(size * 1.25)
            ph = ph.resize((big, big), Image.LANCZOS)
            m = Image.new("L", (big, big), 0)
            ImageDraw.Draw(m).ellipse((big * 0.1, big * 0.1, big * 0.9, big * 0.9), fill=255)
            m = m.filter(ImageFilter.GaussianBlur(big * 0.07))
            # black background → transparent (so no dark halo on the poster), dish stays solid
            import numpy as np
            lum = np.asarray(ph).max(axis=2).astype(float)
            a = np.clip((lum - 10) / 40, 0, 1)
            a = np.asarray(Image.fromarray((a * 255).astype("uint8")).filter(ImageFilter.MaxFilter(9))
                           .filter(ImageFilter.GaussianBlur(3))).astype(float) / 255
            m = Image.fromarray((np.asarray(m).astype(float) * a).astype("uint8"))
            glow(img, cx, cy, size * 0.55, 45)
            img.paste(ph, (int(cx - big / 2), int(cy - big / 2)), m)
        else:
            ph = ph.resize((size, size), Image.LANCZOS)
            m = Image.new("L", (size, size), 0)
            ImageDraw.Draw(m).ellipse((0, 0, size - 1, size - 1), fill=255)
            img.paste(ph, (int(cx - size / 2), int(cy - size / 2)), m)
            ImageDraw.Draw(img).ellipse((cx - size / 2 - 6, cy - size / 2 - 6, cx + size / 2 + 6, cy + size / 2 + 6),
                                        outline=GOLD, width=7)
    else:
        # Photo nahi mili → emoji nahi, Bhavya ka gold logo (premium look)
        glow(img, cx, cy, size * 0.62, 55)
        lg = _brand("logo.png").copy()
        lg.thumbnail((int(size * 0.8), int(size * 0.8)), Image.LANCZOS)
        img.paste(lg, (int(cx - lg.width / 2), int(cy - lg.height / 2)), lg)


# ---------------------------------------------------------------- frame
@lru_cache(None)
def _brand(name):
    return Image.open(A("brand", name)).convert("RGBA")


def canvas(w=W, h=H, footer="Near IIT Roorkee", header=True):
    img = Image.new("RGB", (w, h), BG)
    glow(img, w * 0.5, h * 0.42, w * 0.55, 26)
    d = ImageDraw.Draw(img)
    d.rectangle((26, 26, w - 27, h - 27), outline=LINE, width=2)
    leaf = _brand("leaf.png").copy()
    leaf.thumbnail((130, 190))
    leaf.putalpha(leaf.split()[3].point(lambda v: int(v * 0.55)))
    img.paste(leaf, (w - leaf.width - 40, h - leaf.height - 40), leaf)
    fl = leaf.transpose(Image.FLIP_LEFT_RIGHT)
    img.paste(fl, (40, h - fl.height - 40), fl)
    if header:
        wm = _brand("wordmark.png").copy()
        wm.thumbnail((210, 120), Image.LANCZOS)
        img.paste(wm, (int(w / 2 - wm.width / 2), 46), wm)
    if footer:
        pin = emoji("📍", 30)
        f = F("med", 27)
        tw = f.getlength(footer)
        x = w / 2 - (tw + 40) / 2
        img.paste(pin, (int(x), int(h - 74 - pin.height / 2)), pin)
        text(img, (x + 40, h - 74), footer, f, MUTED, anchor="lm")
    return img


def pill(img, cx, cy, s, f, fill=None, color=None, pad=(34, 16)):
    fill, color = fill or GOLD, color or BG
    tw = f.getlength(s)
    box = (cx - tw / 2 - pad[0], cy - f.size / 2 - pad[1], cx + tw / 2 + pad[0], cy + f.size / 2 + pad[1] + 4)
    ImageDraw.Draw(img).rounded_rectangle(box, 999, fill=fill)
    text(img, (cx, cy + 2), s, f, color)
    return box


# ---------------------------------------------------------------- formats
def r_meme(p, cfg, rng):
    img = canvas()
    block(img, p["top"], "bold", (90, 200, 990, 470), start=78, minimum=40)
    item_visual(img, cfg, p["item"], W / 2, 700, 420, rng)
    block(img, p["bottom"], "bold", (90, 920, 990, 1200), gold=True, start=80, minimum=40)
    return [img]


def r_versus(p, cfg, rng):
    img = canvas()
    block(img, p["headline"], "serif", (80, 190, 1000, 330), gold=True, start=72)
    for i, side in enumerate(("left", "right")):
        x0 = 70 + i * 480
        box = (x0, 370, x0 + 460, 1190)
        rrect(img, box, outline=GOLD if side == "right" else (90, 84, 74), width=4 if side == "right" else 2,
              fill=CARD if side == "right" else PANEL)
        cx = (box[0] + box[2]) / 2
        title = p[f"{side}_title"].upper()
        if side == "right":
            gold_text(img, (cx, 440), title, F("impact", 64))
            item_visual(img, cfg, p["right_item"], cx, 700, 300, rng)
        else:
            text(img, (cx, 440), title, F("impact", 64), (160, 155, 145))
            paste_c(img, emoji(p.get("left_emoji") or "😐", 230), cx, 700)
        block(img, p[f"{side}_line"], "med", (box[0] + 30, 900, box[2] - 30, 1150),
              fill=CREAM if side == "right" else (170, 165, 155), start=44, minimum=28)
    d = ImageDraw.Draw(img)
    d.ellipse((W / 2 - 58, 722, W / 2 + 58, 838), fill=GOLD)
    text(img, (W / 2, 782), "VS", F("impact", 58), BG)
    return [img]


def r_battle(p, cfg, rng):
    img = canvas()
    block(img, p["question"], "bold", (90, 190, 990, 360), start=62, minimum=36)
    for i, k in enumerate(("a", "b")):
        x0 = 70 + i * 480
        box = (x0, 400, x0 + 460, 1110)
        rrect(img, box)
        cx = (box[0] + box[2]) / 2
        d = ImageDraw.Draw(img)
        d.ellipse((cx - 48, 372, cx + 48, 468), fill=GOLD)
        text(img, (cx, 422), k.upper(), F("impact", 60), BG)
        item_visual(img, cfg, p[f"{k}_item"], cx, 640, 280, rng)
        gold_text(img, (cx, 840), p[f"{k}_item"].upper(), fit(p[f"{k}_item"].upper(), "impact", 400, 80, 66)[0])
        block(img, p[f"{k}_line"], "reg", (box[0] + 30, 900, box[2] - 30, 1080), start=38, minimum=26)
    pill(img, W / 2, 1180, "COMMENT KARO:  A  ya  B", F("bold", 40))
    return [img]


def r_tag(p, cfg, rng):
    img = canvas()
    gold_text(img, (W / 2, 290), "TAG KARO", F("impact", 150))
    text(img, (W / 2, 410), "us dost ko", F("script", 70), CREAM)
    block(img, p["line"], "bold", (100, 460, 980, 760), start=64, minimum=36)
    item_visual(img, cfg, p["item"], W / 2, 920, 250, rng)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((170, 1110, 910, 1200), 999, outline=GOLD, width=3, fill=CARD)
    text(img, (215, 1155), "@", F("bold", 46), GOLD, anchor="lm")
    d.line((270, 1175, 820, 1175), fill=(110, 95, 70), width=3)
    d.line((830, 1128, 830, 1182), fill=CREAM, width=4)  # blinking cursor look
    return [img]


def r_rate(p, cfg, rng):
    img = canvas()
    text(img, (W / 2, 215), "COMBO ALERT", F("bold", 34), MUTED)
    block(img, p["combo_name"], "serif", (80, 245, 1000, 420), gold=True, start=80)
    items = p["items"][:3]
    n = len(items)
    for i, it in enumerate(items):
        cx = W / 2 + (i - (n - 1) / 2) * 300
        item_visual(img, cfg, it, cx, 590, 230, rng)
        text(img, (cx, 745), it, F("med", 32), CREAM)
        if i < n - 1:
            text(img, (cx + 150, 590), "+", F("bold", 70), GOLD)
    block(img, p["line"], "reg", (100, 790, 980, 920), start=42, minimum=28)
    text(img, (W / 2, 975), "RATE KARO", F("impact", 60), CREAM)
    for i in range(10):
        x = 115 + i * 87
        box = (x, 1030, x + 72, 1110)
        filled = i < 9
        ImageDraw.Draw(img).rounded_rectangle(box, 14, fill=GOLD if i == 9 else CARD,
                                              outline=GOLD, width=2)
        text(img, ((box[0] + box[2]) / 2, 1072), str(i + 1), F("bold", 36), BG if i == 9 else CREAM)
    text(img, (W / 2, 1170), "comments me apna number", F("reg", 30), MUTED)
    return [img]


def r_checklist(p, cfg, rng):
    img = canvas()
    gold_text(img, (W / 2, 270), p["headline"], fit(p["headline"], "serif", 900, 130, 96)[0])
    d = ImageDraw.Draw(img)
    items, done = p["checklist"][:5], p["done"][:5]
    y = 420
    for it, ok in zip(items, done):
        box = (120, y - 42, 204, y + 42)
        d.rounded_rectangle(box, 16, outline=GOLD, width=4, fill=GOLD if ok else None)
        if ok:
            d.line((138, y, 158, y + 22, 188, y - 24), fill=BG, width=10, joint="curve")
        else:
            d.line((140, y - 22, 184, y + 22), fill=(190, 70, 60), width=7)
            d.line((184, y - 22, 140, y + 22), fill=(190, 70, 60), width=7)
        f, lines, _ = fit(it, "bold" if ok else "med", 700, 120, 54, 32)
        if ok:
            gold_text(img, (240, y), lines[0], f, anchor="lm")
        else:
            text(img, (240, y), lines[0], f, (150, 145, 135), anchor="lm")
            tw = f.getlength(lines[0])
            d.line((240, y + 4, 240 + tw, y + 4), fill=(150, 145, 135), width=4)
        y += 150
    last = next((m["name"] for m in cfg["menu"] if m["name"].lower() in items[-1].lower()), None)
    if last:
        item_visual(img, cfg, last, 860, y + 40, 200, rng)
    text(img, (W / 2, 1195), "Ek kaam to pakka hoga", F("script", 54), CREAM)
    return [img]


SCENE_EMOJI = ["🥟", "🍕", "🍔", "☕", "🧋", "🍟", "🍰", "🥤", "🍮", "🌶️", "🧀", "🍩"]


def _scene(rng, n=13):
    items, tries = [], 0
    while len(items) < n and tries < 2000:
        tries += 1
        s = rng.randint(70, 110)
        x, y = rng.randint(60, 920 - 60), rng.randint(60, 400 - 60)
        if all(math.hypot(x - a, y - b) > (s + t) / 2 + 12 for a, b, t, _, _ in items):
            items.append((x, y, s, rng.choice(SCENE_EMOJI), rng.randint(-25, 25)))
    return items


def _panel(items):
    p = Image.new("RGB", (920, 400), PANEL)
    d = ImageDraw.Draw(p)
    for i in range(0, 920, 46):
        d.line((i, 0, i, 400), fill=CARD, width=22)  # wooden-table stripes
    for x, y, s, e, a in items:
        if e:
            paste_c(p, emoji(e, s, a), x, y)
    return p


def r_spotdiff(p, cfg, rng):
    img = canvas()
    gold_text(img, (W / 2, 205), p["headline"], fit(p["headline"], "serif", 900, 90, 64)[0])
    a = _scene(rng)
    b = [list(t) for t in a]
    idx = rng.sample(range(len(b)), 3)
    b[idx[0]][3] = rng.choice([e for e in SCENE_EMOJI if e != b[idx[0]][3]])  # swapped item
    b[idx[1]][3] = None  # missing item
    b[idx[2]][4] = b[idx[2]][4] + 70  # rotated item
    for k, (items, y) in enumerate(((a, 265), ([tuple(t) for t in b], 715))):
        pnl = _panel(items)
        img.paste(pnl, (80, y))
        ImageDraw.Draw(img).rounded_rectangle((78, y - 2, 1002, y + 402), 18, outline=GOLD, width=3)
        ImageDraw.Draw(img).rounded_rectangle((96, y + 14, 156, y + 74), 14, fill=GOLD)
        text(img, (126, y + 46), "AB"[k], F("impact", 44), BG)
    text(img, (W / 2, 1172), "Zoom karo · Comment me batao", F("med", 34), CREAM)
    return [img]


HIDDEN_PAIRS = [("🍩", "🥯"), ("🥟", "🥠"), ("☕", "🍵"), ("🍪", "🥮"), ("🧋", "🥤"), ("🍔", "🥪"), ("🌶️", "🥕")]


def r_hidden(p, cfg, rng):
    img = canvas()
    main, odd = rng.choice(HIDDEN_PAIRS)
    gold_text(img, (W / 2, 205), p["headline"], fit(p["headline"], "serif", 900, 90, 64)[0])
    cols, rows, s = 10, 10, 84
    ox, oy = W / 2 - cols * 94 / 2 + 47, 300
    oi = rng.randrange(cols * rows)
    for i in range(cols * rows):
        r, c = divmod(i, cols)
        paste_c(img, emoji(odd if i == oi else main, s, rng.randint(-12, 12)), ox + c * 94, oy + r * 87)
    text(img, (W / 2, 1200), "Hold karo · zoom karo · dhundo", F("med", 34), CREAM)
    p["_answer"] = f"row {oi // cols + 1}, column {oi % cols + 1}"
    return [img]


def r_count(p, cfg, rng):
    img = canvas()
    gold_text(img, (W / 2, 205), p["headline"], fit(p["headline"], "serif", 900, 90, 64)[0])
    n = rng.randint(14, 23)
    kinds = ["🥟"] * n + [rng.choice(["🍟", "☕", "🍕", "🧋", "🍔", "🌶️"]) for _ in range(22)]
    rng.shuffle(kinds)
    placed = []
    area = (90, 290, 990, 1120)
    for k in kinds:
        for _ in range(400):
            s = rng.randint(68, 104)
            x, y = rng.randint(area[0] + 50, area[2] - 50), rng.randint(area[1] + 50, area[3] - 50)
            if all(math.hypot(x - a, y - b) > (s + t) / 2 * 0.78 for a, b, t in placed):  # slight overlap = harder
                placed.append((x, y, s))
                paste_c(img, emoji(k, s, rng.randint(-35, 35)), x, y)
                break
        else:
            if k == "🥟":
                n -= 1
    pill(img, W / 2, 1180, "Answer comment karo", F("bold", 38))
    p["_answer"] = f"{n} momos"
    return [img]


def _micro_texture(img, box, hidden, rng, size=13):
    """Rows of tiny text; one row hides a message. Unreadable until you zoom in."""
    x0, y0, x1, y1 = box
    f = F("med", size)
    base = "BHAVYA CAFE · ROORKEE · COFFEE · MOMOS · "
    rows = int((y1 - y0) / (size * 1.5))
    target = rng.randint(rows // 3, 2 * rows // 3)
    d = ImageDraw.Draw(img)
    for r in range(rows):
        y = y0 + r * size * 1.5
        s = (base * 30)[(r * 7) % len(base):]
        if r == target:
            pre = (base * 3)[: rng.randint(10, 40)]
            s = pre + " " + hidden.upper() + " · " + s
        while f.getlength(s) > (x1 - x0):
            s = s[:-1]
        d.text((x0, y), s, font=f, fill=tuple(int(c * 0.7) for c in GOLD))
    return target


def r_zoomread(p, cfg, rng):
    img = canvas()
    gold_text(img, (W / 2, 250), p["headline"].upper(), fit(p["headline"].upper(), "impact", 880, 120, 110)[0])
    paste_c(img, emoji("🔍", 80), W / 2, 352)
    ImageDraw.Draw(img).rounded_rectangle((90, 410, 990, 1130), 24, fill=PANEL, outline=GOLD, width=3)
    _micro_texture(img, (115, 430, 965, 1110), p["hidden_message"], rng)
    text(img, (W / 2, 1185), "Secret message chhupa hai · hold karke zoom karo", F("med", 30), CREAM)
    return [img]


def r_zoomcode(p, cfg, rng):
    img = canvas()
    it = p["_offer_item"]
    text(img, (W / 2, 200), "WEEKLY OFFER", F("bold", 34), MUTED)
    gold_text(img, (W / 2, 280), f"FREE {it['name'].upper()}", fit(f"FREE {it['name'].upper()}", "impact", 660, 120, 110)[0])
    paste_c(img, emoji(it.get("emoji", "🎁"), 90), 130, 280)
    paste_c(img, emoji("🎁", 85), 950, 280)
    ImageDraw.Draw(img).rounded_rectangle((90, 360, 990, 900), 24, fill=PANEL, outline=GOLD, width=3)
    _micro_texture(img, (115, 380, 965, 880), f"CODE: {p['_code']}", rng)
    steps = ["1. Image zoom karo", "2. Hidden CODE dhundo", "3. Counter pe dikhao, FREE lo"]
    for i, s in enumerate(steps):
        text(img, (W / 2, 960 + i * 58), s, F("bold", 40), CREAM)
    block(img, cfg["weekly_offer"]["terms"], "reg", (100, 1130, 980, 1220), fill=MUTED, start=26, minimum=20)
    return [img]


def r_carousel(p, cfg, rng):
    slides = p["slides"][:5]
    out = []
    for i, s in enumerate(slides):
        img = canvas()
        last = i == len(slides) - 1
        text(img, (W - 90, 90), f"{i + 1}/{len(slides)}", F("bold", 32), MUTED, anchor="rm")
        if i == 0:
            pill(img, W / 2, 250, "Last slide tak jaana", F("bold", 34))
        block(img, s["big"], "serif" if not last else "impact", (90, 360, 990, 700), gold=True, start=110, minimum=50)
        block(img, s["small"], "med", (110, 720, 970, 960), start=50, minimum=30)
        if last:
            item = next((m["name"] for m in cfg["menu"] if m["name"].lower() in (s["big"] + s["small"]).lower()), "Veg Momos")
            item_visual(img, cfg, item, W / 2, 1090, 190, rng)
        else:
            text(img, (W - 90, H - 140), "swipe  >", F("bold", 40), GOLD, anchor="rm")
        out.append(img)
    return out


def r_thisorthat(p, cfg, rng):
    out = []
    pairs = p["pairs"][:4]
    for i, pr in enumerate(pairs):
        img = canvas()
        text(img, (W / 2, 205), f"THIS  or  THAT   {i + 1}/{len(pairs)}", F("bold", 40), CREAM)
        for k, (key, y) in enumerate((("a", 300), ("b", 760))):
            box = (90, y, 990, y + 400)
            rrect(img, box)
            d = ImageDraw.Draw(img)
            d.ellipse((110, y + 20, 200, y + 110), fill=GOLD)
            text(img, (155, y + 66), key.upper(), F("impact", 54), BG)
            paste_c(img, emoji(pr.get(f"{key}_emoji") or "✨", 190), 330, y + 200)
            f, lines, size = fit(pr[key], "bold", 520, 300, 76, 40)
            yy = y + 200 - size * 1.18 * (len(lines) - 1) / 2
            for l in lines:
                gold_text(img, (470, yy), l, f, anchor="lm")
                yy += size * 1.18
        text(img, (W / 2, 1195), "swipe  >" if i < len(pairs) - 1 else "Comment karo: A B A", F("bold", 38), GOLD)
        out.append(img)
    return out


def r_spotlight(p, cfg, rng):
    img = canvas()
    text(img, (W / 2, 235), p.get("kicker", "").upper(), F("bold", 30), MUTED)
    item_visual(img, cfg, p["item"], W / 2, 600, 560, rng)
    block(img, p["item"], "serif", (80, 900, 1000, 1040), gold=True, start=96, minimum=50)
    block(img, p["tagline"], "reg", (120, 1050, 960, 1150), start=40, minimum=28)
    price = next((m.get("price") for m in cfg["menu"] if m["name"] == p["item"]), None)
    if price:
        pill(img, W / 2, 1205, f"₹{price}", F("bold", 40))
    return [img]


def r_moodquote(p, cfg, rng):
    img = canvas()
    item_visual(img, cfg, p["item"], W / 2, 470, 430, rng)
    text(img, (W / 2, 760), "\u201c", F("serif", 150), GOLD)
    block(img, p["quote"], "serif", (110, 790, 970, 1130), gold=True, start=70, minimum=40, spacing=1.3)
    d = ImageDraw.Draw(img)
    d.line((W / 2 - 60, 1170, W / 2 + 60, 1170), fill=GOLD, width=2)
    text(img, (W / 2, 1205), p["item"], F("med", 30), MUTED)
    return [img]


RENDERERS = {k[2:]: v for k, v in globals().items() if k.startswith("r_")}


def render_images(fmt, post, cfg, seed):
    rng = random.Random(seed)
    return RENDERERS[fmt["renderer"]](post, cfg, rng)


# ---------------------------------------------------------------- reel
def _reel_card(cfg, it, flash_bg):
    w, h = 1080, 1920
    img = Image.new("RGB", (w, h), flash_bg)
    glow(img, w / 2, h / 2, 520, 50)
    gold_text(img, (w / 2, 560), "FREE", F("impact", 260))
    item_visual(img, cfg, it["name"], w / 2, 960, 520)
    f = fit(it["name"].upper(), "impact", 940, 200, 170)[0]
    text(img, (w / 2, 1400), it["name"].upper(), f, CREAM)
    text(img, (w / 2, 1720), "PAUSE  KARO", F("bold", 60), GOLD)
    return img


def _reel_text_card(lines):
    w, h = 1080, 1920
    img = Image.new("RGB", (w, h), BG)
    glow(img, w / 2, h / 2, 560, 40)
    wm = _brand("wordmark.png").copy()
    wm.thumbnail((420, 240), Image.LANCZOS)
    img.paste(wm, (int(w / 2 - wm.width / 2), 170), wm)
    y = 760
    for s, kind, size, gold in lines:
        f = fit(s, kind, 940, size * 2.6, size, 28)[0]
        for l in wrap(s, f, 940):
            if gold:
                gold_text(img, (w / 2, y), l, f)
            else:
                text(img, (w / 2, y), l, f, CREAM)
            y += f.size * 1.25
        y += 30
    return img


def render_reel(post, cfg, out_path, seed):
    rng = random.Random(seed)
    items = list(post["_all_free_items"])
    tmp = tempfile.mkdtemp()
    frames = []
    intro = _reel_text_card([("PAUSE KARO", "impact", 190, True), ("jo item aaye", "bold", 80, False),
                             ("wo FREE", "impact", 150, True)])
    frames += [intro] * 18  # 1.5 s at 12 fps
    cards = [_reel_card(cfg, it, bg) for it in items for bg in [BG, ALT]]
    for i in range(8 * 12):  # 8 s of flashing, 3 frames per item
        frames.append(cards[(i // 3) % len(cards)])
    outro = _reel_text_card([("Screenshot lo", "impact", 130, True),
                             ("Counter pe dikhao, item FREE", "bold", 64, False),
                             (cfg["weekly_offer"]["terms"], "reg", 40, False),
                             ("Near IIT Roorkee", "med", 44, True)])
    frames += [outro] * 36  # 3 s
    for i, fr in enumerate(frames):
        fr.save(os.path.join(tmp, f"{i:04d}.jpg"), quality=92)
    dur = len(frames) / 12
    from .reels import pick_music
    music = pick_music(seed, "game")
    cmd = [ffmpeg_bin(), "-y", "-loglevel", "error", "-framerate", "12", "-i", os.path.join(tmp, "%04d.jpg")]
    if music:
        cmd += ["-stream_loop", "-1", "-i", music, "-map", "0:v", "-map", "1:a",
                "-af", f"afade=t=out:st={dur - 1.5}:d=1.5", "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart",
            "-t", f"{dur}", out_path]
    subprocess.run(cmd, check=True)
    intro.save(out_path.replace(".mp4", "_cover.jpg"), quality=92)
    shutil.rmtree(tmp)
    return out_path


set_theme("classic_gold")
