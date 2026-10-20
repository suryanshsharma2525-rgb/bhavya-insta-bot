"""Pinterest-style poster templates (aapke reference designs se seekhe hue layouts).

Har template LAYERS ki list deta hai. Static post = saare layers final position pe.
Reel = wahi layers animation ke saath (rise / pop / slide / wipe / draw / ken-burns).
Colours + fonts "style card" se aate hain (data/reference_styles.json) — content Bhavya ka hota hai.
"""
import math
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import render as R
from .photos import cutout, pick_photo


# ---------------------------------------------------------------- basics
class L:
    def __init__(self, img, x, y, anim="fade", delay=0.0, dur=0.55, kb=0.0):
        self.img, self.x, self.y, self.anim, self.delay, self.dur, self.kb = img, x, y, anim, delay, dur, kb


def C(c):
    if isinstance(c, str):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(c)


def fnt(card, role, size):
    f, v = (card.get("fonts") or {}).get(role) or DEFAULT_FONTS[role]
    return R.font(f, int(size), v)


DEFAULT_FONTS = {"display": ("Anton.ttf", None), "serif": ("PlayfairDisplay.ttf", "Bold"), "script": ("GreatVibes.ttf", None),
                 "sans": ("Montserrat.ttf", "SemiBold"), "sans_bold": ("Montserrat.ttf", "ExtraBold"),
                 "hand": ("Caveat.ttf", "Bold"), "italic": ("PlayfairItalic.ttf", "Italic")}


def txt(s, font, color, shadow=0.0, spacing=0, stroke=0, stroke_color=None):
    s = s or ""
    if "₹" in s and not R.has_rupee(os.path.basename(getattr(font, "path", "") or "")):
        font = R.font("Montserrat.ttf", int(font.size), "ExtraBold")  # ₹ kabhi dabba/galat na dikhe
    if spacing:
        s = (" " * spacing).join(list(s))
    bb = font.getbbox(s, stroke_width=stroke)
    w, h = bb[2] - bb[0] + 40, bb[3] - bb[1] + 40
    im = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    if shadow:
        m = Image.new("L", im.size, 0)
        ImageDraw.Draw(m).text((20 - bb[0], 24 - bb[1]), s, font=font, fill=255, stroke_width=stroke)
        im.paste((0, 0, 0, 255), (0, 0), m.filter(ImageFilter.GaussianBlur(8)).point(lambda v: int(v * shadow)))
    ImageDraw.Draw(im).text((20 - bb[0], 20 - bb[1]), s, font=font, fill=C(color) + (255,), stroke_width=stroke,
                            stroke_fill=C(stroke_color or color) + (255,))
    im.info["kind"] = "text"
    return im


def fit(s, card, role, maxw, start, minimum=20, **kw):
    size = start
    sp = kw.get("spacing") or 0
    probe = (" " * sp).join(list(s or "")) if sp else (s or "")
    while size > minimum:
        f = fnt(card, role, size)
        if f.getlength(probe) + 40 <= maxw:
            break
        size -= 3
    return txt(s, fnt(card, role, size), **kw)


def multiline(lines, card, role, maxw, start, color, gap=-18, align="center", **kw):
    ims = [fit(l, card, role, maxw, start, color=color, **kw) for l in lines if l]
    if not ims:
        return Image.new("RGBA", (1, 1))
    w = max(i.width for i in ims)
    h = sum(i.height for i in ims) + gap * (len(ims) - 1)
    out = Image.new("RGBA", (w, max(1, h)), (0, 0, 0, 0))
    y = 0
    for i in ims:
        x = (w - i.width) // 2 if align == "center" else (0 if align == "left" else w - i.width)
        out.alpha_composite(i, (x, y))
        y += i.height + gap
    out.info["kind"] = "text"
    return out


def shadowed(img, blur=26, opacity=0.55, dy=24):
    pad = blur * 2
    out = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2 + dy), (0, 0, 0, 0))
    m = Image.new("L", out.size, 0)
    m.paste(img.getchannel("A"), (pad, pad + dy))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 255))
    sh.putalpha(m.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * opacity)))
    out.alpha_composite(sh)
    out.alpha_composite(img, (pad, pad))
    out.info.update(img.info)
    return out


def rounded(im, r):
    im = im.convert("RGBA")
    S = 3
    m = Image.new("L", (im.width * S, im.height * S), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, im.width * S - 1, im.height * S - 1), r * S, fill=255)
    im.putalpha(m.resize(im.size, Image.LANCZOS))
    return im


def pill(text_, card, color, bg, size=40, pad=(46, 20), outline=None, role="sans_bold"):
    t = txt(text_, fnt(card, role, size), color)
    w, h = t.width + pad[0] * 2 - 40, t.height + pad[1] * 2 - 40
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if bg:
        d.rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=C(bg) + (255,))
    if outline:
        d.rounded_rectangle((1, 1, w - 2, h - 2), h // 2, outline=C(outline) + (255,), width=3)
    im.alpha_composite(t, (pad[0] - 20, pad[1] - 20))
    im.info["kind"] = "text"
    return im


def circle_badge(lines, card, color, bg, d=230, ring=None):
    S = 3
    im = Image.new("RGBA", (d * S, d * S), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    if bg:
        dr.ellipse((0, 0, d * S - 1, d * S - 1), fill=C(bg) + (255,))
    if ring:
        dr.arc((10 * S, 10 * S, d * S - 10 * S, d * S - 10 * S), 200, 520, fill=C(ring) + (255,), width=4 * S)
    im = im.resize((d, d), Image.LANCZOS)
    t = multiline(lines, card, "sans_bold", d * 0.78, d * 0.28, color, gap=-24)
    im.alpha_composite(t, ((d - t.width) // 2, (d - t.height) // 2))
    im.info["kind"] = "text"
    return im


def arrow(color, w=180, h=120, curve=1, seed=0, width=5):
    """Haath se bana curved arrow (doodle)."""
    rng = random.Random(seed)
    S = 3
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = []
    for i in range(30):
        t = i / 29
        x = 10 + t * (w - 30)
        y = h * 0.75 - math.sin(t * math.pi) * h * 0.55 * curve + rng.uniform(-1.5, 1.5)
        pts.append((x * S, y * S))
    d.line(pts, fill=C(color) + (255,), width=width * S, joint="curve")
    ex, ey = pts[-1]
    px, py = pts[-4]
    ang = math.atan2(ey - py, ex - px)
    for s in (-1, 1):
        a = ang + math.pi + s * 0.5
        d.line((ex, ey, ex + math.cos(a) * 22 * S, ey + math.sin(a) * 22 * S), fill=C(color) + (255,), width=width * S)
    out = im.resize((w, h), Image.LANCZOS)
    out.info["kind"] = "deco"
    return out


def brand(card, color, w=230):
    """Bhavya wordmark kisi bhi colour me (light/dark backgrounds pe saaf)."""
    wm = R._brand("wordmark.png").copy()
    wm.thumbnail((w, w), Image.LANCZOS)
    if card.get("brand_gold", False) and not card.get("light"):
        return wm
    solid = Image.new("RGBA", wm.size, C(color) + (0,))
    solid.putalpha(wm.getchannel("A"))
    return solid


def logo_mark(card, color, d=150):
    lg = R._brand("logo.png").copy()
    lg.thumbnail((d, d), Image.LANCZOS)
    if card.get("brand_gold", False):
        return lg
    solid = Image.new("RGBA", lg.size, C(color) + (0,))
    solid.putalpha(lg.getchannel("A"))
    return solid


# ---------------------------------------------------------------- dish images
def dish(item, size, ctx, cut=True, radius=40):
    """Dish ki photo: cut-out (background hata ke) ya rounded photo. Repeat-tracking ke saath."""
    path, kind = pick_photo(item, ctx.get("mode", "image"), ctx.get("seed", ""), ctx.get("today"))
    if not path:
        lg = R._brand("logo.png").copy()
        lg.thumbnail((int(size * 0.7), int(size * 0.7)), Image.LANCZOS)
        lg.info["kind"] = "dish"
        return lg, None
    ctx.setdefault("used", []).append(path)
    if cut and not ctx.get("no_cut"):
        c = cutout(path)
        if c is not None:
            c.thumbnail((size, size), Image.LANCZOS)
            c.info["kind"] = "dish"
            return c, path
    im = Image.open(path).convert("RGB")
    s = min(im.size)
    im = im.crop(((im.width - s) // 2, (im.height - s) // 2, (im.width + s) // 2, (im.height + s) // 2))
    im = im.resize((size, size), Image.LANCZOS).filter(ImageFilter.UnsharpMask(1.4, 50, 2))
    im = rounded(im, radius)
    im.info["kind"] = "dish"
    return im, path


def photo_bg(item, W, H, ctx, darken=0.0, blur=0):
    path, kind = pick_photo(item, ctx.get("mode", "image"), ctx.get("seed", "") + "bg", ctx.get("today"))
    if not path:
        return None
    ctx.setdefault("used", []).append(path)
    im = Image.open(path).convert("RGB")
    sc = max(W / im.width, H / im.height) * 1.08
    im = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)
    im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H))
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    im = im.convert("RGBA")
    if darken:
        im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * darken))))
    return im


def solid(W, H, color):
    return Image.new("RGBA", (W, H), C(color) + (255,))


def grad(W, H, c1, c2, vertical=True):
    a, b = C(c1), C(c2)
    g = Image.linear_gradient("L").resize((W, H) if vertical else (H, W))
    if not vertical:
        g = g.rotate(90, expand=True)
    return Image.composite(Image.new("RGBA", (W, H), b + (255,)), Image.new("RGBA", (W, H), a + (255,)), g)


def grain(img, amount=0.06, seed=1):
    import numpy as np
    n = (np.random.default_rng(seed).random((img.height // 2, img.width // 2)) * 255).astype("uint8")
    g = Image.fromarray(n, "L").resize(img.size)
    lay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    lay.putalpha(g.point(lambda v: int(v * amount)))
    img.alpha_composite(lay)
    return img


# ---------------------------------------------------------------- templates
# Each: (card, c=content, W, H, ctx) -> list[L]
def t_giant_vertical(card, c, W, H, ctx):
    p = card["palette"]
    u = W / 1080
    bg = solid(W, H, p["bg"])
    panel_w = int(W * card.get("params", {}).get("panel", 0.42))
    pan = Image.new("RGBA", (panel_w, H), (0, 0, 0, 0))
    ImageDraw.Draw(pan).rounded_rectangle((-60, -60, panel_w, H + 60), int(90 * u), fill=C(p["panel"]) + (255,))
    word = (c.get("word") or c["item"].split()[-1]).upper()
    gw = fit(word, card, "display", H * 0.9, int(H * 0.36), color=p["word"])
    gw = gw.rotate(90, expand=True)
    if card.get("params", {}).get("texture"):
        gw = grain(gw, 0.0)
    D, path = dish(c["item"], int(W * 0.78), ctx)
    D = shadowed(D, 30, 0.5)
    head = multiline(c.get("headline_lines") or ["THE BEST", "IS HERE", "AT BHAVYA"], card, "display", W * 0.5,
                     int(96 * u), p["text"], gap=-28, align="center")
    sub = fit(c.get("sub") or "", card, "sans", W * 0.5, int(36 * u), color=p["text2"])
    return [L(bg, 0, 0, "none"), L(pan, 0, 0, "left", 0.0, 0.5),
            L(gw, int(panel_w * 0.5 - gw.width / 2), int((H - gw.height) / 2), "rise", 0.1, 0.7),
            L(D, int(W * 0.56 - D.width / 2), int(H * 0.6 - D.height / 2), "pop", 0.35, 0.6, kb=0.04),
            L(head, int(W * 0.73 - head.width / 2), int(H * 0.06), "right", 0.5),
            L(sub, int(W * 0.73 - sub.width / 2), int(H * 0.06 + head.height), "fade", 0.7)]


def t_curve_split(card, c, W, H, ctx):
    p = card["palette"]
    u = W / 1080
    bg = solid(W, H, p["bg"])
    arc = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    S = 2
    m = Image.new("L", (W * S, H * S), 0)
    R0 = int(W * 1.25 * S)
    ImageDraw.Draw(m).ellipse((int(W * 0.25 * S), int(H * 0.12 * S), int(W * 0.25 * S) + R0, int(H * 0.12 * S) + R0), fill=255)
    arc.paste(C(p["panel"]) + (255,), (0, 0), m.resize((W, H), Image.LANCZOS))
    word = (c.get("word") or c["item"].split()[-1]).upper()
    letters = [word[i:i + 2] for i in range(0, len(word), 2)] if len(word) > 4 else list(word)
    gl_dark = multiline(letters, card, "display", W * 0.42, int(H * 0.24), p["panel"], gap=-int(60 * u), align="left")
    gl_light = multiline(letters, card, "display", W * 0.42, int(H * 0.24), p["word"], gap=-int(60 * u), align="left")
    gx, gy = int(W * 0.03), int(H * 0.08)
    am = arc.getchannel("A").crop((gx, gy, gx + gl_dark.width, gy + gl_dark.height))
    gl = gl_dark.copy()
    gl.paste(gl_light, (0, 0), ImageChops.multiply(am, gl_light.getchannel("A")))
    title = multiline(c.get("title_lines") or [c["item"]], card, "script", W * 0.8, int(70 * u), p["text"], gap=-30)
    D, _ = dish(c["item"], int(W * 0.8), ctx)
    D = shadowed(D, 30, 0.55)
    price = c.get("price")
    right = []
    if price:
        pr = fit(f"₹{price}", card, "sans_bold", W * 0.3, int(130 * u), color=p["word"])
        right.append(L(pr, int(W * 0.66), int(H * 0.68), "pop", 0.7))
    cta = fit(c.get("button") or "Visit Today!", card, "script", W * 0.38, int(66 * u), color=p["word"])
    handle = fit(c.get("handle", "@bhavya_cafe"), card, "sans_bold", W * 0.4, int(32 * u), color=p["word"])
    dots = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rr = random.Random(3)
    dd = ImageDraw.Draw(dots)
    for _ in range(26):
        x, y = rr.uniform(W * 0.2, W * 0.9), rr.uniform(H * 0.1, H * 0.35)
        dd.ellipse((x, y, x + 9 * u, y + 15 * u), fill=C(p["text2"]) + (220,))
    return [L(bg, 0, 0, "none"), L(arc, 0, 0, "wipe", 0.0, 0.7), L(dots, 0, 0, "fade", 0.6),
            L(gl, gx, gy, "left", 0.15, 0.6),
            L(title, int(W * 0.5 - title.width / 2), int(H * 0.01), "fade", 0.2),
            L(D, int(W * 0.58 - D.width / 2), int(H * 0.47 - D.height / 2), "pop", 0.35, 0.6, kb=0.04),
            *right, L(cta, int(W * 0.62), int(H * 0.82), "rise", 0.8), L(handle, int(W * 0.6), int(H * 0.9), "fade", 0.9)]


def t_script_bold(card, c, W, H, ctx):
    p = card["palette"]
    u = W / 1080
    bg = solid(W, H, p["bg"])
    layers = [L(bg, 0, 0, "none")]
    if card.get("params", {}).get("diagonal"):
        dg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(dg).polygon([(W * 0.45, H), (W, H * 0.42), (W, H), ], fill=C(p["panel"]) + (255,))
        layers.append(L(dg, 0, 0, "wipe", 0.05))
    caps = fit(c.get("small_caps") or "HOT  /  FRESH  /  DELICIOUS", card, "sans", W * 0.8, int(28 * u), color=p["text"], spacing=1)
    scr = fit(c.get("script") or "The Ultimate", card, "script", W * 0.75, int(120 * u), color=p["text"])
    big = fit((c.get("word") or c["item"]).upper(), card, "display", W * 0.9, int(250 * u), color=p["word"])
    tail = fit(c.get("tail") or "IN ROORKEE", card, "sans_bold", W * 0.6, int(64 * u), color=p["text"], spacing=0)
    D, _ = dish(c["item"], int(W * 0.7), ctx)
    D = shadowed(D, 34, 0.6)
    y0 = int(H * 0.06)
    by = y0 + int(60 * u)
    layers += [L(caps, int(W * 0.08), y0, "fade", 0.05),
               L(big, int(W / 2 - big.width / 2), by, "rise", 0.15, 0.6),
               L(scr, int(W * 0.08), by + int(big.height * 0.62), "wipe", 0.35, 0.6),
               L(tail, int(W * 0.95 - tail.width), by + int(big.height * 0.62) + scr.height - int(40 * u), "right", 0.45),
               L(D, int(W / 2 - D.width / 2), int(H * 0.64 - D.height / 2), "pop", 0.5, 0.6, kb=0.04)]
    if c.get("price"):
        b = circle_badge(["SIRF", f"₹{c['price']}"], card, p["word"], None, int(230 * u), ring=p["word"])
        layers.append(L(b, int(W * 0.03), int(H * 0.34), "pop", 0.75))
    if not card.get("params", {}).get("features", True):
        return layers
    feats = c.get("features") or ["Fresh ingredients", "Freshly made", "Real flavour"]
    fw = W // 3
    row = Image.new("RGBA", (W, int(120 * u)), (0, 0, 0, 0))
    dr = ImageDraw.Draw(row)
    for i, ft in enumerate(feats[:3]):
        cx = fw * i + fw // 2
        dr.ellipse((cx - fw * 0.36 - 22 * u, 30 * u, cx - fw * 0.36 + 22 * u, 74 * u), outline=C(p["word"]) + (255,), width=3)
        t = multiline(ft.upper().split(" ", 1), card, "sans", fw * 0.6, int(24 * u), p["text"], gap=-14, align="left")
        row.alpha_composite(t, (int(cx - fw * 0.36 + 34 * u), int(52 * u - t.height / 2)))
        if i:
            dr.line((fw * i, 24 * u, fw * i, 90 * u), fill=C(p["word"]) + (160,), width=2)
    row.info["kind"] = "text"
    layers.append(L(row, 0, int(H * 0.9), "fade", 0.9))
    return layers


def t_editorial_mood(card, c, W, H, ctx):
    p = card["palette"]
    u = W / 1080
    bg = solid(W, H, p["bg"])
    br = brand(card, p["word"], int(260 * u))
    lines = c.get("headline_lines") or ["it's a", "mood."]
    h1 = fit(lines[0], card, "serif", W * 0.6, int(190 * u), color=p["word"])
    h2 = fit(lines[1] if len(lines) > 1 else "", card, "serif", W * 0.84, int(260 * u), color=p["word"])
    D, _ = dish(c["item"], int(W * 0.64), ctx)
    D = shadowed(D, 30, 0.35)
    note = multiline(c.get("note_lines") or [c["item"], f"₹{c.get('price', '')}"], card, "sans", W * 0.3, int(40 * u),
                     p["text"], gap=-12)
    ar = arrow(p["text"], int(150 * u), int(110 * u), seed=2)
    ar2 = arrow(p["text"], int(120 * u), int(100 * u), curve=-1, seed=5).transpose(Image.FLIP_LEFT_RIGHT)
    mark = circle_badge([""], card, p["bg"], p["word"], int(200 * u))
    lm = logo_mark({**card, "brand_gold": False}, p["bg"], int(150 * u))
    mark.alpha_composite(lm, ((mark.width - lm.width) // 2, (mark.height - lm.height) // 2))
    return [L(bg, 0, 0, "none"), L(br, int(W / 2 - br.width / 2), int(H * 0.04), "fade", 0.0),
            L(h1, int(W * 0.08), int(H * 0.15), "rise", 0.1),
            L(h2, int(min(W * 0.16, W * 0.96 - h2.width)), int(H * 0.15 + h1.height * 0.72), "rise", 0.25),
            L(D, int(W * 0.44 - D.width / 2), int(H * 0.38), "rise", 0.45, 0.7, kb=0.03),
            L(note, int(W * 0.7), int(H * 0.45), "fade", 0.8), L(ar, int(W * 0.68), int(H * 0.52), "draw", 0.9),
            L(ar2, int(W * 0.06), int(H * 0.33), "draw", 0.8), L(mark, int(W * 0.08), int(H * 0.56), "pop", 0.7)]


def t_editorial_overlay(card, c, W, H, ctx):
    p = card["palette"]
    u = W / 1080
    bg = photo_bg(c["item"], W, H, ctx, darken=0.18) or solid(W, H, p["bg"])
    top = grad(W, int(H * 0.45), (0, 0, 0), (0, 0, 0))
    top.putalpha(Image.linear_gradient("L").rotate(180).resize((W, int(H * 0.45))).point(lambda v: int(v * 0.55)))
    scr = fit(c.get("script") or "a good", card, "italic", W * 0.5, int(120 * u), color=p["text"])
    word = (c.get("word") or c["item"].split()[-1]).upper()
    big = fit(word, card, "sans_bold", W * 0.9, int(220 * u), color=p["text"])
    sub = multiline(c.get("sub_lines") or ["For the best experience", "eat it hot"], card, "italic", W * 0.5, int(40 * u),
                    p["text"], gap=-14)
    br = brand(card, p["text"], int(200 * u))
    return [L(bg, 0, 0, "kb", 0, 1, kb=0.06), L(top, 0, 0, "none"),
            L(scr, int(W * 0.56 - scr.width / 2), int(H * 0.11), "wipe", 0.2),
            L(big, int(W / 2 - big.width / 2), int(H * 0.11) + int(scr.height * 0.62), "rise", 0.3, 0.6),
            L(sub, int(W / 2 - sub.width / 2), int(H * 0.11) + int(scr.height * 0.62) + big.height - int(10 * u), "fade", 0.6),
            L(br, int(W / 2 - br.width / 2), int(H * 0.9), "fade", 0.8)]


def t_cozy_minimal(card, c, W, H, ctx):
    p = card["palette"]
    u = W / 1080
    bg = photo_bg(c["item"], W, H, ctx, darken=0.22) or grad(W, H, p["bg"], p["panel"])
    warm = Image.new("RGBA", (W, H), C(p["panel"]) + (40,))
    br = brand(card, p["text"], int(190 * u))
    line = multiline(c.get("headline_lines") or ["A quiet moment", "worth pausing for"], card, "sans", W * 0.55,
                     int(54 * u), p["text"], gap=-10, align="left")
    nm = fit(c.get("script") or c["item"], card, "script", W * 0.7, int(110 * u), color=p["text"])
    sub = fit((c.get("sub") or "too good to resist").upper(), card, "sans", W * 0.6, int(26 * u), color=p["text"], spacing=1)
    return [L(bg, 0, 0, "kb", 0, 1, kb=0.05), L(warm, 0, 0, "none"), L(br, int(W * 0.07), int(H * 0.05), "fade", 0.1),
            L(line, int(W * 0.1), int(H * 0.2), "rise", 0.3), L(nm, int(W * 0.08), int(H * 0.72), "wipe", 0.6),
            L(sub, int(W * 0.1), int(H * 0.72) + nm.height - int(20 * u), "fade", 0.85)]


def t_insta_mockup(card, c, W, H, ctx):
    p = card["palette"]
    u = W / 1080
    bg = photo_bg(c["item"], W, H, ctx, darken=0.08, blur=22) or solid(W, H, p["bg"])
    cw = int(W * 0.78)
    D, _ = dish(c["item"], cw - int(40 * u), ctx, cut=False, radius=4)
    ch = D.height + int(260 * u)
    card_im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ImageDraw.Draw(card_im).rounded_rectangle((0, 0, cw - 1, ch - 1), int(40 * u), fill=(255, 255, 255, 255))
    lm = R._brand("logo.png").copy()
    lm.thumbnail((int(76 * u), int(76 * u)), Image.LANCZOS)
    circ = Image.new("RGBA", (int(86 * u), int(86 * u)), (0, 0, 0, 0))
    ImageDraw.Draw(circ).ellipse((0, 0, circ.width - 1, circ.height - 1), fill=(24, 20, 16, 255))
    circ.alpha_composite(lm, ((circ.width - lm.width) // 2, (circ.height - lm.height) // 2))
    card_im.alpha_composite(circ, (int(26 * u), int(24 * u)))
    hn = txt(c.get("handle", "@bhavya_cafe").lstrip("@"), R.font("Montserrat.ttf", int(34 * u), "Bold"), (20, 20, 20))
    loc = txt("Roorkee", R.font("Montserrat.ttf", int(26 * u), "Medium"), (90, 90, 90))
    card_im.alpha_composite(hn, (int(126 * u), int(16 * u)))
    card_im.alpha_composite(loc, (int(126 * u), int(56 * u)))
    dots = txt("•••", R.font("Montserrat.ttf", int(30 * u), "Bold"), (30, 30, 30))
    card_im.alpha_composite(dots, (cw - dots.width - int(10 * u), int(24 * u)))
    card_im.alpha_composite(D, (int(20 * u), int(130 * u)))
    dr = ImageDraw.Draw(card_im)
    y = int(130 * u) + D.height + int(40 * u)
    x = int(40 * u)
    s = int(44 * u)
    dr.polygon([(x + s / 2, y + s), (x, y + s * 0.35), (x + s * 0.25, y), (x + s / 2, y + s * 0.22), (x + s * 0.75, y),
                (x + s, y + s * 0.35)], fill=(237, 64, 77))
    dr.ellipse((x + 80 * u, y, x + 80 * u + s, y + s), outline=(30, 30, 30), width=4)
    dr.polygon([(x + 160 * u, y + s * 0.1), (x + 160 * u + s, y + s * 0.5), (x + 160 * u, y + s * 0.9)], outline=(30, 30, 30), width=4)
    dr.rectangle((cw - 80 * u, y, cw - 80 * u + s * 0.7, y + s), outline=(30, 30, 30), width=4)
    card_im = shadowed(card_im, 40, 0.45)
    cap = fit(c.get("script") or c["item"], card, "script", W * 0.8, int(90 * u), color=p["text"])
    return [L(bg, 0, 0, "kb", 0, 1, kb=0.04), L(card_im, int(W / 2 - card_im.width / 2), int(H * 0.47 - card_im.height / 2), "pop", 0.2, 0.6),
            L(cap, int(W / 2 - cap.width / 2), int(H * 0.86), "rise", 0.7)]


def t_doodle(card, c, W, H, ctx):
    p = card["palette"]
    u = W / 1080
    bg = photo_bg(c["item"], W, H, ctx, darken=0.25) or solid(W, H, p["bg"])
    notes = (c.get("notes") or ["Cheese ka overflow!", "So good!", "Crispy!", f"₹{c.get('price', '')} only!", "Yum!"])[:5]
    spots = [(0.08, 0.30, 1), (0.60, 0.26, -1), (0.06, 0.62, 1), (0.62, 0.66, -1), (0.36, 0.82, 1)]
    layers = [L(bg, 0, 0, "kb", 0, 1, kb=0.05)]
    head = multiline(c.get("headline_lines") or ["WEEKEND", "VIBES!"], card, "hand", W * 0.5, int(110 * u), p["text"], gap=-30, align="left")
    layers.append(L(head, int(W * 0.05), int(H * 0.04), "pop", 0.1))
    for i, (n, (fx, fy, side)) in enumerate(zip(notes, spots)):
        t = fit(n, card, "hand", W * 0.36, int(64 * u), color=p["text"], shadow=0.4)
        a = arrow(p["text"], int(130 * u), int(90 * u), curve=side, seed=i)
        if side < 0:
            a = a.transpose(Image.FLIP_LEFT_RIGHT)
        layers.append(L(t, int(W * fx), int(H * fy), "pop", 0.3 + i * 0.12))
        layers.append(L(a, int(W * fx + (t.width * 0.3 if side > 0 else -40 * u)), int(H * fy + t.height - 10 * u), "draw", 0.38 + i * 0.12))
    tail = multiline(c.get("tail_lines") or ["EAT &", "DRINK"], card, "hand", W * 0.35, int(96 * u), p["text"], gap=-26)
    layers.append(L(tail, int(W * 0.95 - tail.width), int(H * 0.86), "pop", 1.0))
    return layers


def t_diagonal_split(card, c, W, H, ctx):
    p = card["palette"]
    u = W / 1080
    cols = [C(x) for x in p.get("bands") or [p["bg"], p["panel"], p["word"]]]
    items = (c.get("items") or [c["item"]] * 3)[:3]
    layers = []
    bh = H / 3
    for i in range(3):
        band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        y0, y1 = bh * i, bh * (i + 1)
        tilt = H * 0.05
        poly = [(0, y0 + (tilt if i else -10)), (W, y0 - (tilt if i else 10)), (W, y1 - tilt + (10 if i == 2 else 0) + (H if i == 2 else 0)),
                (0, y1 + tilt + (H if i == 2 else 0))]
        ImageDraw.Draw(band).polygon(poly, fill=cols[i] + (255,))
        layers.append(L(band, 0, 0, "left" if i % 2 == 0 else "right", i * 0.1, 0.5))
    for i, it in enumerate(items):
        D, _ = dish(it, int(W * 0.44), {**ctx, "seed": ctx.get("seed", "") + str(i)})
        D = shadowed(D, 22, 0.45)
        left = i % 2 == 0
        x = int(W * (0.04 if left else 0.55))
        y = int(bh * i + bh / 2 - D.height / 2)
        layers.append(L(D, x, y, "pop", 0.35 + i * 0.15, kb=0.03))
        lab = pill(it, card, p["text"], None, int(34 * u), outline=p["text"], role="sans")
        if left:
            layers.append(L(lab, int(W * 0.6), int(bh * i + bh * 0.55), "fade", 0.5 + i * 0.15))
            ar = arrow(p["text"], int(110 * u), int(70 * u), seed=i + 7)
            layers.append(L(ar, int(W * 0.5), int(bh * i + bh * 0.32), "draw", 0.55 + i * 0.15))
        else:
            layers.append(L(lab, int(W * 0.6), int(bh * i + bh * 0.86), "fade", 0.5 + i * 0.15))
    s1 = fit(c.get("script") or "Three flavours", card, "script", W * 0.46, int(96 * u), color=p["text"])
    s2 = multiline(c.get("headline_lines") or ["One", "obsession"], card, "serif", W * 0.46, int(110 * u), p["text"], gap=-30, align="left")
    ty = int(bh + bh / 2 - (s1.height * 0.8 + s2.height) / 2)
    layers += [L(s1, int(W * 0.05), ty, "wipe", 0.9), L(s2, int(W * 0.05), ty + int(s1.height * 0.8), "rise", 1.0)]
    return layers


def t_repeat_text(card, c, W, H, ctx):
    p = card["palette"]
    u = W / 1080
    bg = solid(W, H, p["bg"])
    word = (c.get("word") or c["item"].split()[-1]).upper()
    rep = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    f = fnt(card, "display", int(190 * u))
    y = -30 * u
    k = 0
    while y < H:
        t = txt((word + "  ") * 4, f, p["panel"])
        rep.alpha_composite(t, (int(-((k * 160 * u) % (t.width / 4))), int(y)))
        y += t.height - 50 * u
        k += 1
    D, _ = dish(c["item"], int(W * 0.62), ctx)
    tall = D.height > D.width * 1.25  # sirf lambe glass/cup side me fit hote hain
    D = shadowed(D, 30, 0.5)
    cw, chh = int(W * 0.56), int(H * 0.3)
    cardim = Image.new("RGBA", (cw, chh), (0, 0, 0, 0))
    ImageDraw.Draw(cardim).rounded_rectangle((0, 0, cw - 1, chh - 1), int(46 * u), fill=C(p["word"]) + (255,))
    e = fit((c.get("small_caps") or "ENJOY"), card, "sans", cw * 0.6, int(32 * u), color=p["bg"], spacing=2)
    nm = fit(c["item"].upper(), card, "display", cw * 0.86, int(110 * u), color=p["bg"])
    sc = fit(c.get("script") or "Bhavya Special", card, "italic", cw * 0.8, int(56 * u), color=p["bg"])
    cardim.alpha_composite(e, ((cw - e.width) // 2, int(30 * u)))
    cardim.alpha_composite(nm, ((cw - nm.width) // 2, int(30 * u) + e.height - int(20 * u)))
    cardim.alpha_composite(sc, ((cw - sc.width) // 2, int(30 * u) + e.height + nm.height - int(46 * u)))
    br = brand(card, p["word"], int(200 * u))
    btn = pill((c.get("button") or "Visit Today") + "  ›", card, p["bg"], p["word"], int(34 * u))
    head = [L(bg, 0, 0, "none"), L(rep, 0, 0, "fade", 0, 0.8), L(br, int(W * 0.06), int(H * 0.04), "fade", 0.1)]
    if not tall:  # chauda dish (vada pav, samosa, momos) → upar dish, neeche card (kuch na dhake)
        dy = int(H * 0.11)
        cy = int(H * 0.84) - chh
        D, _ = dish(c["item"], int(min(W * 0.8, cy - dy - 20 * u)), ctx)
        D = shadowed(D, 30, 0.5)
        return head + [L(D, int(W / 2 - D.width / 2), dy + (cy - dy - D.height + 84) // 2 - 30, "pop", 0.3, kb=0.03),
                       L(cardim, int(W / 2 - cw / 2), cy, "rise", 0.5),
                       L(btn, int(W / 2 - btn.width / 2), int(H * 0.88), "rise", 0.8)]
    return head + [L(D, int(W * 0.04), int(H * 0.5 - D.height / 2), "pop", 0.3, kb=0.03),
                   L(cardim, int(W * 0.4), int(H * 0.38), "right", 0.5), L(btn, int(W / 2 - btn.width / 2), int(H * 0.86), "rise", 0.8)]


def t_menu_flyer(card, c, W, H, ctx):
    p = card["palette"]
    u = W / 1080
    bg = solid(W, H, p["bg"])
    waves = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dw = ImageDraw.Draw(waves)
    for k in range(-2, 14):
        pts = [(x, k * 120 * u + math.sin(x / (90 * u)) * 26 * u) for x in range(0, W + 20, 20)]
        dw.line(pts, fill=C(p["panel"]) + (70,), width=int(16 * u))
    items = (c.get("items") or [c["item"]])[:5]
    big = fit(c.get("word") or "NEW", card, "display", W * 0.45, int(280 * u), color=p["text"])
    side = multiline(c.get("headline_lines") or ["BHAVYA", "BEST-", "SELLERS"], card, "display", W * 0.45, int(96 * u),
                     p["text"], gap=-24, align="left")
    layers = [L(bg, 0, 0, "none"), L(waves, 0, 0, "fade"), L(big, int(W * 0.05), int(H * 0.05), "rise", 0.05),
              L(side, int(W * 0.06) + big.width - int(20 * u), int(H * 0.07), "right", 0.15)]
    for i, it in enumerate(items[:2]):
        pw, ph = int(W * 0.9), int(H * 0.2)
        pan = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        ImageDraw.Draw(pan).rounded_rectangle((0, 0, pw - 1, ph - 1), int(40 * u), fill=C(p["panel2"]) + (255,))
        nm = multiline(it.upper().split(" ", 1) if len(it) > 9 else [it.upper()], card, "display", pw * 0.42, int(84 * u),
                       p["word"], gap=-20, align="left")
        left = i % 2 == 0
        pan.alpha_composite(nm, (int(pw * (0.05 if left else 0.53)), int(ph / 2 - nm.height / 2)))
        y = int(H * (0.27 + i * 0.225))
        layers.append(L(pan, int(W * 0.05), y, "left" if left else "right", 0.25 + i * 0.15))
        D, _ = dish(it, int(ph * 1.15), {**ctx, "seed": ctx.get("seed", "") + str(i)})
        D = shadowed(D, 20, 0.45)
        layers.append(L(D, int(W * (0.52 if left else 0.0)), y + ph // 2 - D.height // 2, "pop", 0.4 + i * 0.15))
        pr = R.font("Montserrat.ttf", 10)
        pv = next((m.get("price") for m in ctx["cfg"]["menu"] if m["name"] == it), None)
        if pv:
            b = circle_badge([f"₹{pv}"], card, p["panel2"], p["word"], int(140 * u))
            layers.append(L(b, int(W * (0.43 if left else 0.3)), y + ph - int(110 * u), "pop", 0.55 + i * 0.15))
    small = items[2:5]
    for i, it in enumerate(small):
        bw = int(W * 0.28)
        box = Image.new("RGBA", (bw, int(H * 0.14)), (0, 0, 0, 0))
        ImageDraw.Draw(box).rounded_rectangle((0, int(H * 0.04), bw - 1, int(H * 0.14) - 1), int(26 * u), fill=C(p["panel2"]) + (255,))
        nm = multiline(it.upper().split(" ", 1), card, "display", bw * 0.9, int(40 * u), p["word"], gap=-12, align="left")
        box.alpha_composite(nm, (int(14 * u), int(H * 0.14) - nm.height - int(10 * u)))
        x = int(W * 0.05 + i * (bw + W * 0.035))
        layers.append(L(box, x, int(H * 0.79), "rise", 0.7 + i * 0.1))
        pv = next((m.get("price") for m in ctx["cfg"]["menu"] if m["name"] == it), None)
        if pv:
            pt = fit(f"₹{pv}", card, "sans_bold", bw * 0.6, int(70 * u), color=p["text"])
            layers.append(L(pt, x, int(H * 0.735), "pop", 0.8 + i * 0.1))
    hd = fit(c.get("handle", "@bhavya_cafe"), card, "sans_bold", W * 0.5, int(34 * u), color=p["text"])
    layers.append(L(hd, int(W / 2 - hd.width / 2), int(H * 0.94), "fade", 1.0))
    return layers


def t_pedestal(card, c, W, H, ctx):
    p = card["palette"]
    u = W / 1080
    bg = solid(W, H, p["bg"])
    block = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(block).rectangle((0, H * 0.7, W, H), fill=C(p["panel"]) + (255,))
    ped = Image.new("RGBA", (int(W * 0.5), int(H * 0.12)), (0, 0, 0, 0))
    ImageDraw.Draw(ped).rectangle((0, 0, ped.width, ped.height), fill=C(p["panel2"]) + (255,))
    halo = Image.new("RGBA", (int(W * 0.52), int(W * 0.52)), (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse((0, 0, halo.width - 1, halo.height - 1), fill=C(p.get("halo", p["text"])) + (90,))
    D, _ = dish(c["item"], int(W * 0.62), ctx)
    D = shadowed(D, 18, 0.35, dy=10)
    t1 = fit(c["item"].upper(), card, "serif", W * 0.8, int(110 * u), color=p["word"])
    t2 = fit(c.get("sub") or "Bhavya signature", card, "sans", W * 0.7, int(38 * u), color=p["word"])
    note = multiline(c.get("note_lines") or ["Freshly made", "near IIT Roorkee"], card, "sans", W * 0.36, int(28 * u), p["text"], gap=-10, align="left")
    br = brand(card, p["text"], int(170 * u))
    return [L(bg, 0, 0, "none"), L(block, 0, 0, "rise", 0, 0.5), L(halo, int(W / 2 - halo.width / 2), int(H * 0.7 - halo.width * 0.95), "pop", 0.1),
            L(ped, int(W / 2 - ped.width / 2), int(H * 0.7), "rise", 0.2),
            L(D, int(W / 2 - D.width / 2), int(H * 0.7 - D.height + 50 * u), "pop", 0.35, kb=0.03),
            L(t1, int(W / 2 - t1.width / 2), int(H * 0.06), "rise", 0.5), L(t2, int(W / 2 - t2.width / 2), int(H * 0.06) + t1.height - int(20 * u), "fade", 0.6),
            L(note, int(W * 0.06), int(H * 0.88), "fade", 0.8), L(br, int(W * 0.94 - br.width), int(H * 0.9), "fade", 0.85)]


TEMPLATES = {k[2:]: v for k, v in globals().items() if k.startswith("t_")}


# ---------------------------------------------------------------- render
def layout(card, content, W, H, ctx):
    p = card["palette"]
    for k in ("text2", "panel2", "word"):
        p.setdefault(k, p.get("text") if k != "panel2" else p.get("panel"))
    layers = TEMPLATES[card["template"]](card, content, W, H, ctx)
    report = guard(layers, W, H)
    ctx.setdefault("guard_log", []).append(report)
    return layers


# ---------------------------------------------------------------- layout guard (khana kabhi na chhupe)
GF = 0.25  # masks 1/4 resolution pe (fast)


def _small_mask(img, thr):
    import numpy as np
    a = img.getchannel("A").resize((max(1, int(img.width * GF)), max(1, int(img.height * GF))), Image.BILINEAR)
    return np.array(a) > thr


def _place(canvas_shape, m, x, y):
    """m ko canvas pe (x,y) pe rakho; return (canvas-mask, total pixels of m)."""
    import numpy as np
    Hs, Ws = canvas_shape
    out = np.zeros(canvas_shape, bool)
    x, y = int(round(x * GF)), int(round(y * GF))
    l, t = max(0, -x), max(0, -y)
    r, b = min(m.shape[1], Ws - x), min(m.shape[0], Hs - y)
    if r > l and b > t:
        out[y + t:y + b, x + l:x + r] = m[t:b, l:r]
    return out


def guard(layers, W, H):
    """Har dish layer check karo: (1) upar koi box/text use dhak to nahi raha, (2) frame se bahar to nahi kat rahi,
    (3) dish khud kisi chhote text (naam/price) ko to nahi dhak rahi. Problem ho to dish ko chhota/shift karke
    sabse achhi jagah dhoondo. Report return karta hai (AI auditor bhi ise dekhta hai)."""
    import numpy as np
    shape = (int(H * GF), int(W * GF))
    full = lambda l: l.img.width >= W * 0.97 and l.img.height >= H * 0.97
    report = []
    for i, d in enumerate(layers):
        if d.img.info.get("kind") != "dish":
            continue
        occ = np.zeros(shape, np.float32)
        prot = np.zeros(shape, bool)
        for j, o in enumerate(layers):
            if j == i or full(o):
                continue
            kind = o.img.info.get("kind")
            sm = _small_mask(o.img, 60)
            if kind == "text" and sm.any():  # text ka poora area (letters ke beech ki jagah bhi) gina jaye
                ys, xs = np.nonzero(sm)
                g = 5  # ~20px saans lene ki jagah text ke chaaron taraf
                big = np.zeros((sm.shape[0] + 2 * g, sm.shape[1] + 2 * g), bool)
                big[ys.min():ys.max() + 1 + 2 * g, xs.min():xs.max() + 1 + 2 * g] = True
                om = _place(shape, big, o.x - g / GF, o.y - g / GF)
            else:
                om = _place(shape, sm, o.x, o.y)
            if j > i:
                occ += om * (0.5 if kind == "deco" else 1.0)
            elif kind == "dish" or (kind == "text" and o.img.width * o.img.height < 0.12 * W * H):
                prot |= om
        prot_total = max(1, int(prot.sum()))
        cx0, cy0 = d.x + d.img.width / 2, d.y + d.img.height / 2

        def score(s, dx, dy, m):
            w, h = d.img.width * s, d.img.height * s
            x, y = cx0 + dx - w / 2, cy0 + dy - h / 2
            pm = _place(shape, m, x, y)
            tot = max(1, int(m.sum()))
            vis = int(pm.sum())
            outside = 1 - vis / tot
            occl = float((occ * pm).sum()) / tot
            cov = float((prot & pm).sum()) / prot_total
            return dict(cost=10 * occl + 10 * outside + 6 * cov + 0.8 * (1 - s) + (abs(dx) + abs(dy)) / W,
                        occluded=round(occl, 3), outside=round(outside, 3), covers_text=round(cov, 3), scale=s, dx=dx, dy=dy)

        base_m = _small_mask(d.img, 170)
        before = score(1.0, 0, 0, base_m)
        rec = dict(layer=i, before={k: before[k] for k in ("occluded", "outside", "covers_text")}, fixed=False)
        if before["occluded"] > 0.006 or before["outside"] > 0.01 or before["covers_text"] > 0.03:
            best = before
            for s in (1.0, 0.92, 0.85, 0.78, 0.71, 0.64):
                m = base_m if s == 1.0 else _small_mask(d.img.resize((max(1, int(d.img.width * s)), max(1, int(d.img.height * s)))), 170)
                for dx in np.linspace(-0.22, 0.22, 11) * W:
                    for dy in np.linspace(-0.22, 0.22, 11) * H:
                        sc = score(s, dx, dy, m)
                        if sc["cost"] < best["cost"]:
                            best = sc
            if best is not before:
                s = best["scale"]
                img = d.img if s == 1.0 else d.img.resize((int(d.img.width * s), int(d.img.height * s)), Image.LANCZOS)
                img.info["kind"] = "dish"
                d.img = img
                d.x, d.y = int(cx0 + best["dx"] - img.width / 2), int(cy0 + best["dy"] - img.height / 2)
                rec["fixed"] = True
            rec["after"] = {k: best[k] for k in ("occluded", "outside", "covers_text", "scale")}
        else:
            rec["after"] = rec["before"]
        report.append(rec)
    return report


def compose(layers, W, H, t=None, T=0.0):
    """t=None → final static. t (seconds into scene) → animated frame."""
    fr = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    for l in layers:
        img, x, y = l.img, l.x, l.y
        if t is None:
            fr.alpha_composite(img, (int(x), int(y))) if _inside(img, x, y, W, H) else _paste_clip(fr, img, x, y)
            continue
        k = (t - l.delay) / max(0.01, l.dur)
        if k <= 0 and l.anim != "none" and l.anim != "kb":
            continue
        k = max(0.0, min(1.0, k))
        e = 1 - (1 - k) ** 3
        a = 1.0
        if l.anim == "kb" or l.kb:
            z = 1 + (l.kb or 0.05) * min(1.0, T / 6.0)
            if abs(z - 1) > 0.002:
                img = img.resize((int(img.width * z), int(img.height * z)), Image.BICUBIC)
                x -= (img.width - l.img.width) / 2
                y -= (img.height - l.img.height) / 2
        if l.anim == "fade":
            a = e
        elif l.anim == "rise":
            y += (1 - e) * 80
            a = e
        elif l.anim == "left":
            x -= (1 - e) * W * 0.6
        elif l.anim == "right":
            x += (1 - e) * W * 0.6
        elif l.anim == "pop":
            s = 0.6 + 0.4 * _back(k)
            if abs(s - 1) > 0.01:
                nw, nh = max(1, int(img.width * s)), max(1, int(img.height * s))
                x += (img.width - nw) / 2
                y += (img.height - nh) / 2
                img = img.resize((nw, nh), Image.BICUBIC)
            a = min(1, k * 3)
        elif l.anim in ("wipe", "draw"):
            cw = int(img.width * e)
            if cw < 2:
                continue
            img = img.crop((0, 0, cw, img.height))
        if a < 0.99:
            img = img.copy()
            img.putalpha(img.getchannel("A").point(lambda v: int(v * a)))
        _paste_clip(fr, img, x, y)
    return fr


def _back(t, s=1.7):
    t = t - 1
    return t * t * ((s + 1) * t + s) + 1


def _inside(img, x, y, W, H):
    return x >= 0 and y >= 0 and x + img.width <= W and y + img.height <= H


def _paste_clip(fr, img, x, y):
    x, y = int(x), int(y)
    l, t = max(0, -x), max(0, -y)
    r, b = min(img.width, fr.width - x), min(img.height, fr.height - y)
    if r <= l or b <= t:
        return
    fr.alpha_composite(img.crop((l, t, r, b)), (x + l, y + t))
