"""Bhavya Motion Engine — professional motion-graphics reels (1080x1920).

Har reel = scenes ki list (spec). Har reel ke liye seed se naye presets chune jaate hain:
layout, text animation, transitions, light rays, particles, ghost text, colour theme, music.
Cuts music ki beat pe hote hain.

Scene types:
  kinetic   {lines:[..], accent:int, kicker, ghost}
  product   {item, name, tagline, kicker, show_price, index, total}
  stat      {big, sub, kicker}
  split     {a, b, title}
  flash     {items:[..], badge}        (pause-game / offer)
  poster    {image: PIL.Image}         (image post → video)
  logo      {tagline, cta}
"""
import glob
import math
import os
import random
import re
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from . import render as R
from .photos import photos_for

W, H = 1080, 1920
FPS = 24
# AI Art Director yahan apni choices daalta hai (render() se pehle)
STYLE_POOL = {"anims": ["rise", "scale", "blur", "words", "split", "typewriter", "mask", "letters", "bounce", "track"],
              "transitions": ["sweep", "flash", "push", "zoom", "fade", "circle", "blinds", "whip", "leak", "slide_up"],
              "layouts": ["circle", "fullbleed", "card", "editorial", "polaroid", "split"],
              "backgrounds": ["bokeh", "rays"], "left_align": 0.2}


# ---------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = clamp(t)
    return 3 * t * t - 2 * t * t * t


def back_out(t, s=1.70158):
    t = clamp(t) - 1
    return t * t * ((s + 1) * t + s) + 1


def font_italic(size):
    if R.FONTPACK:
        f, v = R.FONTPACK["italic"]
        return R.font(f, size, v)
    return R.font("LoraItalic.ttf", size, "Italic")


def with_alpha(im, a):
    if a >= 0.999:
        return im
    im = im.copy()
    im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    return im


def paste(fr, layer, x=0, y=0, a=1.0, scale=1.0, blur=0.0):
    """RGBA layer ko frame pe — fade, scale (centre se), blur ke saath."""
    if a <= 0.01:
        return
    l = layer
    if abs(scale - 1) > 0.003:
        w, h = l.size
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        l = l.resize((nw, nh), Image.BICUBIC)
        x += (w - nw) / 2
        y += (h - nh) / 2
    if blur > 0.4:
        l = l.filter(ImageFilter.GaussianBlur(blur))
    l = with_alpha(l, a)
    fr.alpha_composite(l, (int(x), int(y)))


def text_img(s, font, fill=None, gold=False, shadow=True, glow=False, tracking=0):
    """Ek line text → tight RGBA image (gold gradient / glow optional)."""
    s = s or ""
    if tracking:
        s = (" " * 0).join(s)
    bbox = font.getbbox(s)
    w, h = bbox[2] - bbox[0] + 60, bbox[3] - bbox[1] + 60
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((30 - bbox[0], 30 - bbox[1]), s, font=font, fill=255)
    if shadow:
        sh = mask.filter(ImageFilter.GaussianBlur(8)).point(lambda v: int(v * (0.18 if R.LIGHT else 0.7)))
        layer.paste((0, 0, 0, 255), (0, 0), sh)
    if glow:
        gl = mask.filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * (0.25 if R.LIGHT else 0.55)))
        layer.paste(R.GOLD + (255,), (0, 0), gl)
    if gold:
        grad = R._gradient(w, h, R.THEME).convert("RGBA")
        layer.paste(grad, (0, 0), mask)
    else:
        layer.paste((fill or R.CREAM) + (255,), (0, 0), mask)
    return layer


def fit_font(s, kind, maxw, start, minimum=30):
    size = start
    while size > minimum:
        f = font_italic(size) if kind == "italic" else R.F(kind, size)
        if f.getlength(s) <= maxw:
            return f
        size -= 4
    return font_italic(minimum) if kind == "italic" else R.F(kind, minimum)


def wrap_lines(s, kind, maxw, start, max_lines=3, minimum=44):
    size = start
    while size >= minimum:
        f = font_italic(size) if kind == "italic" else R.F(kind, size)
        lines = R.wrap(s, f, maxw)
        if len(lines) <= max_lines:
            return f, lines
        size -= 6
    f = font_italic(minimum) if kind == "italic" else R.F(kind, minimum)
    return f, R.wrap(s, f, maxw)


# ---------------------------------------------------------------- background system
class Backdrop:
    """Animated background. styles: rays, bokeh, blobs, grid, stripes, spotlight, grain, rings."""

    def __init__(self, rng, styles=("bokeh",), rays=None, particles=True):
        self.rng = rng
        styles = list(styles)
        if rays and "rays" not in styles:
            styles.append("rays")
        self.styles = set(styles)
        base = Image.new("RGB", (W, H), R.BG)
        R.glow(base, W / 2, H * 0.45, W * 0.75, 18 if R.LIGHT else 34)
        vg = Image.new("L", (W, H), 0)
        ImageDraw.Draw(vg).ellipse((-W * 0.35, -H * 0.15, W * 1.35, H * 1.15), fill=255)
        vg = vg.filter(ImageFilter.GaussianBlur(160))
        dark = Image.new("RGB", (W, H), tuple(int(c * (0.86 if R.LIGHT else 0.35)) for c in R.BG))
        self.base = Image.composite(base, dark, vg).convert("RGBA")
        self.rays = self._rays() if "rays" in self.styles else None
        n = rng.randint(22, 40) if "bokeh" in self.styles else (10 if particles else 0)
        self.parts = [(rng.random() * W, rng.random() * H, rng.uniform(3, 14), rng.uniform(-18, 18),
                       rng.uniform(-60, -10), rng.uniform(0.15, 0.7), rng.random() * 6.28) for _ in range(n)]
        self.dot = {}
        if "blobs" in self.styles:
            self.blobs = []
            for i in range(3):
                r = rng.randint(300, 480)
                b = Image.new("L", (r * 4, r * 4), 0)
                ImageDraw.Draw(b).ellipse((r, r, r * 3, r * 3), fill=255)
                b = b.filter(ImageFilter.GaussianBlur(r * 0.45))
                col = [R.GOLD, getattr(R, "ACCENT2", R.ALT), R.LINE][i % 3]
                im = Image.new("RGBA", b.size, col + (0,))
                im.putalpha(b.point(lambda v: int(v * (0.35 if R.LIGHT else 0.28))))
                self.blobs.append((im, rng.random() * W, rng.random() * H, rng.uniform(20, 50), rng.random() * 6.28))
        if "grid" in self.styles:
            g = Image.new("RGBA", (W + 120, H + 120), (0, 0, 0, 0))
            d = ImageDraw.Draw(g)
            for x in range(0, W + 120, 120):
                d.line((x, 0, x, H + 120), fill=R.LINE + (60,), width=1)
            for y in range(0, H + 120, 120):
                d.line((0, y, W + 120, y), fill=R.LINE + (60,), width=1)
            self.grid = g
        if "stripes" in self.styles:
            st = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
            d = ImageDraw.Draw(st)
            for x in range(-H * 2, W * 2, 140):
                d.polygon([(x, 0), (x + 55, 0), (x + 55 + H * 2, H * 2), (x + H * 2, H * 2)], fill=R.LINE + (34,))
            self.stripes = st
        if "grain" in self.styles:
            self.grain = []
            for i in range(3):
                n_ = (np.random.default_rng(i).random((H // 2, W // 2)) * 255).astype("uint8")
                gi = Image.fromarray(n_, "L").resize((W, H))
                lay = Image.new("RGBA", (W, H), (255, 255, 255, 0) if not R.LIGHT else (0, 0, 0, 0))
                lay.putalpha(gi.point(lambda v: int(v * 0.07)))
                self.grain.append(lay)

    def _rays(self):
        S = 2400
        im = Image.new("L", (S, S), 0)
        d = ImageDraw.Draw(im)
        n = self.rng.choice([14, 18, 22, 28])
        for i in range(n):
            a0 = i * 2 * math.pi / n
            a1 = a0 + math.pi / n * 0.45
            d.polygon([(S / 2, S / 2), (S / 2 + S * math.cos(a0), S / 2 + S * math.sin(a0)),
                       (S / 2 + S * math.cos(a1), S / 2 + S * math.sin(a1))], fill=70)
        im = im.filter(ImageFilter.GaussianBlur(14))
        fade = Image.new("L", (S, S), 0)
        ImageDraw.Draw(fade).ellipse((S * 0.18, S * 0.18, S * 0.82, S * 0.82), fill=255)
        fade = fade.filter(ImageFilter.GaussianBlur(260))
        return ImageChops.multiply(im, fade)

    def _bokeh(self, r):
        r = int(r)
        if r not in self.dot:
            s = r * 4
            m = Image.new("L", (s, s), 0)
            ImageDraw.Draw(m).ellipse((r, r, 3 * r, 3 * r), fill=255)
            m = m.filter(ImageFilter.GaussianBlur(r * 0.6))
            dot = Image.new("RGBA", (s, s), R.GOLD + (0,))
            dot.putalpha(m)
            self.dot[r] = dot
        return self.dot[r]

    def frame(self, T, rays_amount=None):
        fr = self.base.copy()
        if "blobs" in self.styles:
            for im, x, y, sp, ph in self.blobs:
                bx = x + math.sin(T * 0.3 + ph) * sp * 4
                by = y + math.cos(T * 0.25 + ph) * sp * 4
                fr.alpha_composite(im, (int(bx - im.width / 2), int(by - im.height / 2)))
        if "spotlight" in self.styles:
            sx = W / 2 + math.sin(T * 0.6) * 260
            R.glow(fr, sx, H * 0.42, 520, 40 if not R.LIGHT else 25)
        if "grid" in self.styles:
            o = int(T * 20) % 120
            fr.alpha_composite(self.grid.crop((o, o, o + W, o + H)))
        if "stripes" in self.styles:
            o = int(T * 40) % 140
            fr.alpha_composite(self.stripes.crop((o, 0, o + W, H)))
        if "rings" in self.styles:
            d = ImageDraw.Draw(fr)
            for k in range(4):
                r = ((T * 160 + k * 300) % 1200)
                a = int(90 * (1 - r / 1200))
                d.ellipse((W / 2 - r, H * 0.42 - r, W / 2 + r, H * 0.42 + r), outline=R.GOLD + (a,), width=3)
        ra = (1.0 if self.rays is not None else 0.0) if rays_amount is None else rays_amount
        if self.rays is not None and ra > 0.02:
            rot = self.rays.rotate(T * 6, resample=Image.BILINEAR)
            c = rot.crop(((2400 - W) // 2, (2400 - H) // 2 - 150, (2400 + W) // 2, (2400 + H) // 2 - 150))
            c = c.point(lambda v: int(v * ra * (0.6 if R.LIGHT else 1)))
            lay = Image.new("RGBA", (W, H), R.GOLD + (0,))
            lay.putalpha(c)
            fr.alpha_composite(lay)
        for (x, y, r, vx, vy, a, ph) in self.parts:
            px = (x + vx * T) % W
            py = (y + vy * T) % H
            al = a * (0.6 + 0.4 * math.sin(T * 1.7 + ph))
            d = self._bokeh(r)
            fr.alpha_composite(with_alpha(d, al), (int(px - d.width / 2), int(py - d.height / 2)))
        if "grain" in self.styles:
            fr.alpha_composite(self.grain[int(T * FPS) % 3])
        return fr


# ---------------------------------------------------------------- photo layer
def _photo(item, seed):
    from .photos import pick_photo
    path, kind = pick_photo(item, "reel", seed) if item else (None, None)
    if not path:
        return None, None
    STYLE_POOL.setdefault("used", []).append(path)
    im = Image.open(path).convert("RGB")
    s = min(im.size)
    im = im.crop(((im.width - s) // 2, (im.height - s) // 2, (im.width + s) // 2, (im.height + s) // 2))
    im = im.filter(ImageFilter.UnsharpMask(radius=1.6, percent=60, threshold=2))  # crisp food texture
    return im, kind


def photo_circle(im, size, kind):
    im = im.resize((size, size), Image.LANCZOS).convert("RGBA")
    S = size * 3  # supersampled mask → ekdum saaf (anti-aliased) kinara, koi blur nahi
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).ellipse((0, 0, S - 1, S - 1), fill=255)
    im.putalpha(m.resize((size, size), Image.LANCZOS))
    return im


def ring(size, t, width=4):
    """Rotating thin gold arc around the photo."""
    S = size + 60
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((6, 6, S - 6, S - 6), outline=R.LINE + (160,), width=2)
    start = (t * 120) % 360
    d.arc((4, 4, S - 4, S - 4), start, start + 110, fill=R.GOLD + (255,), width=width)
    d.arc((4, 4, S - 4, S - 4), start + 180, start + 230, fill=R.GOLD + (200,), width=width)
    return im


def price_badge(price):
    f = R.F("bold", 58)
    s = f"₹{price}"
    tw = f.getlength(s)
    w, h = int(tw + 70), 100
    im = Image.new("RGBA", (w + 30, h + 30), (0, 0, 0, 0))
    sh = Image.new("L", im.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle((15, 20, w + 15, h + 20), 50, fill=170)
    im.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(8)))
    grad = R._gradient(w, h, R.THEME).convert("RGBA")
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), 50, fill=255)
    im.paste(grad, (15, 15), m)
    ImageDraw.Draw(im).text((15 + w / 2, 15 + h / 2 + 2), s, font=f, fill=R.BG, anchor="mm")
    return im


def price_of(cfg, name):
    for m in cfg["menu"]:
        if m["name"].lower() == str(name).lower():
            return m.get("price")
    return None


# ---------------------------------------------------------------- scene renderers
# Each returns fn(t_local_0_1, T_global_seconds, backdrop) -> RGBA frame

def sc_kinetic(sp, cfg, rng):
    lines = [l for l in sp["lines"] if l][:4]
    accent = sp.get("accent", len(lines) - 1)
    style = sp.get("anim") or rng.choice(STYLE_POOL["anims"])
    align = sp.get("align") or ("left" if rng.random() < STYLE_POOL.get("left_align", 0.2) else "center")
    big = sp.get("size", 150)
    # lambi line → 2-3 lines me tod do taaki text bada aur bold dikhe
    kind = "impact" if sp.get("font", "impact") == "impact" else sp["font"]
    acc_txt = lines[accent] if lines else ""
    expanded, new_acc = [], 0
    for i, l in enumerate(lines):
        txt = l.upper() if kind == "impact" else l
        tgt = big if i == accent % max(1, len(lines)) else int(big * 0.8)
        f, ls = wrap_lines(txt, kind, 940, tgt, 3, max(44, int(tgt * 0.55)))
        for l2 in ls:
            if l == acc_txt:
                new_acc = len(expanded) if not expanded or new_acc == 0 else new_acc
            expanded.append((l2, f, l == acc_txt))
    imgs = [text_img(t, f, gold=g, glow=g) for t, f, g in expanded]
    lines = [t for t, _, _ in expanded]
    accent = next((i for i, (_, _, g) in enumerate(expanded) if g), -1)
    total_h = sum(im.height - 40 for im in imgs)
    y0 = H / 2 - total_h / 2 + sp.get("dy", 0)
    kicker = text_img(sp["kicker"].upper(), R.F("med", 34), fill=R.GOLD, shadow=False) if sp.get("kicker") else None
    ghost = None
    if sp.get("ghost"):
        gf = R.F("impact", 360)
        ghost = text_img(sp["ghost"].upper(), gf, fill=R.LINE, shadow=False)
    word_imgs = None
    if style == "words":
        word_imgs = [[(w, text_img(w, f, gold=g, glow=g)) for w in t.split()] for t, f, g in expanded]
    if style == "letters":
        word_imgs = [[(c, text_img(c, f, gold=g, glow=g)) for c in t] for t, f, g in expanded]
    X = (lambda w: 80) if align == "left" else (lambda w: W / 2 - w / 2)

    def fn(t, T, bd):
        fr = bd.frame(T)
        if ghost:
            gx = W / 2 - ghost.width / 2 + (1 - t) * 180 - 90
            paste(fr, ghost, gx, H / 2 - ghost.height / 2 - 120, a=0.22)
        if kicker:
            paste(fr, kicker, X(kicker.width) + (20 if align == "left" else 0), y0 - 110, a=ease_out(t * 4))
        y = y0
        for i, im in enumerate(imgs):
            d = i * 0.12
            k = ease_out((t - d) * 3.2)
            x = X(im.width)
            if style in ("words", "letters") and word_imgs:
                ws = word_imgs[i]
                gap = 10 if style == "words" else -8
                tw = sum(w.width - 50 for _, w in ws) + gap * (len(ws) - 1)
                xx = (X(tw) - 25) if align == "center" else 55
                step = 0.06 if style == "words" else 0.025
                for j, (_, w) in enumerate(ws):
                    kk = back_out(clamp((t - d - j * step) * 5))
                    paste(fr, w, xx, y + (1 - kk) * 60, a=clamp((t - d - j * step) * 6), scale=0.8 + 0.2 * kk)
                    xx += w.width - 50 + gap
            elif style == "scale":
                paste(fr, im, x, y, a=k, scale=1.35 - 0.35 * back_out(clamp((t - d) * 3)))
            elif style == "blur":
                paste(fr, im, x, y, a=k, blur=(1 - k) * 14)
            elif style == "split":
                paste(fr, im, x + (1 - k) * (500 if i % 2 else -500), y, a=k)
            elif style == "typewriter":
                frac = clamp((t - d) * 2.2)
                if frac > 0:
                    cw = int(im.width * frac)
                    paste(fr, im.crop((0, 0, max(1, cw), im.height)), x, y)
                    if frac < 1:
                        ImageDraw.Draw(fr).rectangle((x + cw - 10, y + 30, x + cw - 4, y + im.height - 30), fill=R.GOLD)
            elif style == "mask":  # text rises from behind an invisible line
                frac = ease_out((t - d) * 3)
                if frac > 0:
                    hh = int(im.height * frac)
                    paste(fr, im.crop((0, 0, im.width, max(1, hh))), x, y + im.height - hh)
            elif style == "bounce":
                kb = back_out(clamp((t - d) * 3), 3.2)
                paste(fr, im, x, y - (1 - kb) * 200, a=clamp((t - d) * 6))
            elif style == "track":  # letters close in (horizontal squeeze)
                kk = ease_out((t - d) * 3)
                if kk > 0:
                    sw = max(1, int(im.width * (1.35 - 0.35 * kk)))
                    st = im.resize((sw, im.height), Image.BILINEAR)
                    paste(fr, st, X(sw), y, a=kk)
            else:  # rise
                paste(fr, im, x, y + (1 - k) * 90, a=k)
            y += im.height - 40
        return fr
    return fn


def sc_product(sp, cfg, rng, seed):
    item = sp["item"]
    layout = sp.get("layout") or rng.choice(STYLE_POOL["layouts"])
    im, kind = _photo(item, seed)
    if im is None:
        layout = "logo"
    elif layout in ("fullbleed", "split") and im.width < 1500:
        # chhoti photo ko poori screen pe khinchne se blur hota hai → sharp layout lo
        layout = rng.choice([l for l in ("circle", "card", "editorial", "polaroid") if l in STYLE_POOL["layouts"]] or ["card"])
    price = price_of(cfg, item) if sp.get("show_price", True) else None
    badge = price_badge(price) if price else None
    name = sp.get("name") or item
    fn_name = fit_font(name.upper(), "bold", 960, 112, 60)
    name_im = text_img(name.upper(), fn_name, fill=R.CREAM, glow=False)
    tag_im = None
    if sp.get("tagline"):
        f, ls = wrap_lines(sp["tagline"], "italic", 900, 56, 2, 38)
        tag_im = [text_img(l, f, fill=R.GOLD, shadow=True) for l in ls]
    kicker = text_img(sp["kicker"].upper(), R.F("impact", 150), gold=True, glow=True) if sp.get("kicker") else None
    ghost = text_img(item.split()[0].upper(), R.F("impact", 300), fill=R.LINE, shadow=False)
    prog = sp.get("index"), sp.get("total")

    if layout == "fullbleed":
        big = im.resize((int(H * 1.1), int(H * 1.1)), Image.LANCZOS)
        grad = Image.new("L", (1, H), 0)
        for yy in range(H):
            grad.putpixel((0, yy), int(255 * clamp((yy - H * 0.62) / (H * 0.3)) ** 1.4 * 0.92))
        grad = grad.resize((W, H))
        topg = Image.new("L", (1, H), 0)
        for yy in range(H):
            topg.putpixel((0, yy), int(150 * clamp(1 - yy / (H * 0.12))))
        topg = topg.resize((W, H))
        shade = Image.new("RGBA", (W, H), R.BG + (0,))
        shade.putalpha(ImageChops.lighter(grad, topg))
    elif layout == "editorial":
        ed = im.resize((1100, 1100), Image.LANCZOS).crop((170, 0, 930, 1100)).convert("RGBA")
        ga = np.tile((np.clip(np.arange(760) / 220.0, 0, 1) * 255).astype("uint8"), (1100, 1))
        gb = np.tile((np.clip((1100 - np.arange(1100)) / 160.0, 0, 1) * 255).astype("uint8")[:, None], (1, 760))
        ed.putalpha(Image.fromarray(np.minimum(ga, gb), "L"))
    elif layout == "polaroid":
        p_ = im.resize((700, 700), Image.LANCZOS).convert("RGBA")
        pol = Image.new("RGBA", (760, 900), (250, 246, 238, 255))
        pol.alpha_composite(p_, (30, 30))
        ImageDraw.Draw(pol).text((380, 815), name, font=font_italic(54), fill=(60, 40, 30), anchor="mm")
        tilt = rng.choice([-6, -4, 4, 6])
        polr = pol.rotate(tilt, expand=True, resample=Image.BICUBIC)
        shp = Image.new("RGBA", (polr.width + 80, polr.height + 80), (0, 0, 0, 0))
        m_ = Image.new("L", shp.size, 0)
        m_.paste(polr.getchannel("A"), (40, 60))
        shp.putalpha(m_.filter(ImageFilter.GaussianBlur(24)).point(lambda v: int(v * 0.6)))
    elif layout == "split":
        sp_img = im.resize((W, W), Image.LANCZOS).crop((0, 80, W, 1080)).convert("RGBA")
    elif layout in ("circle", "card"):
        size = 760 if layout == "circle" else 840
        if layout == "circle":
            ph = photo_circle(im, size, kind)
        else:
            ph = im.resize((size, int(size * 1.1)), Image.LANCZOS).convert("RGBA")
            m = Image.new("L", ph.size, 0)
            ImageDraw.Draw(m).rounded_rectangle((0, 0, ph.width - 1, ph.height - 1), 46, fill=255)
            ph.putalpha(m)
            brd = Image.new("RGBA", (ph.width + 12, ph.height + 12), (0, 0, 0, 0))
            ImageDraw.Draw(brd).rounded_rectangle((0, 0, brd.width - 1, brd.height - 1), 52, outline=R.GOLD + (255,), width=4)
            brd.alpha_composite(ph, (6, 6))
            ph = brd
        shadow = Image.new("RGBA", (ph.width + 120, ph.height + 120), (0, 0, 0, 0))
        sm = Image.new("L", shadow.size, 0)
        sm.paste(ph.getchannel("A"), (60, 80))
        shadow.putalpha(sm.filter(ImageFilter.GaussianBlur(30)).point(lambda v: int(v * 0.75)))

    def fn(t, T, bd):
        fr = bd.frame(T, rays_amount=0.35 if layout != "fullbleed" else 0)
        k = ease_out(t * 3)
        if layout == "fullbleed":
            z = 1.0 + 0.06 * t
            sz = int(H * z)
            b2 = big.resize((sz, sz), Image.BICUBIC)
            x = (W - sz) / 2 + (rng.random() - 0.5) * 0
            fr.paste(b2.convert("RGBA"), (int(x), int((H - sz) / 2)))
            fr.alpha_composite(shade)
            ny = 1460
        elif layout in ("circle", "card"):
            paste(fr, ghost, W / 2 - ghost.width / 2 + (0.5 - t) * 160, 1500, a=0.12)  # sirf neeche, khane ke upar nahi
            cy = 820
            sc = 0.86 + 0.14 * back_out(clamp(t * 2.6)) + 0.03 * t
            paste(fr, shadow, W / 2 - shadow.width / 2, cy - shadow.height / 2 + 20, a=k, scale=sc)
            if layout == "circle":
                rg = ring(760, T)
                paste(fr, rg, W / 2 - rg.width / 2, cy - rg.height / 2, a=k, scale=sc)
            paste(fr, ph, W / 2 - ph.width / 2, cy - ph.height / 2 + (1 - k) * 120, a=k, scale=sc)
            ny = 1300 if layout == "circle" else 1390
        elif layout == "editorial":
            ex = W - 760 + (1 - k) * 300
            fr.alpha_composite(with_alpha(ed, k), (int(ex), 330))
            ny = 1460
        elif layout == "polaroid":
            kb = back_out(clamp(t * 2.4))
            paste(fr, shp, W / 2 - shp.width / 2, 840 - shp.height / 2 + 30, a=k)
            paste(fr, polr, W / 2 - polr.width / 2 + (1 - kb) * 400, 820 - polr.height / 2 + (1 - kb) * -200,
                  a=clamp(t * 4), scale=0.9 + 0.1 * kb)
            ny = 1360
        elif layout == "split":
            cut = int(1000 * ease_out(t * 2.5))
            if cut > 2:
                z = 1 + 0.06 * t
                im2 = sp_img.resize((int(W * z), int(1000 * z)), Image.BILINEAR).crop((0, 0, W, 1000))
                fr.alpha_composite(im2.crop((0, 0, W, cut)), (0, 0))
            ImageDraw.Draw(fr).rectangle((0, 996, W * ease_out(t * 3), 1004), fill=R.GOLD)
            ny = 1180
        else:  # logo fallback
            lg = R._brand("logo.png").copy()
            lg.thumbnail((520, 520), Image.LANCZOS)
            paste(fr, lg, W / 2 - lg.width / 2, 800 - lg.height / 2, a=k, scale=0.9 + 0.1 * k)
            ny = 1300
        if kicker:
            kk = back_out(clamp(t * 4))
            paste(fr, kicker, W / 2 - kicker.width / 2, 250, a=clamp(t * 5), scale=1.3 - 0.3 * kk)
        nk = ease_out((t - 0.15) * 3.5)
        NX = (lambda w: 60) if layout == "editorial" else (lambda w: W / 2 - w / 2)
        if layout != "polaroid":
            paste(fr, name_im, NX(name_im.width), ny + (1 - nk) * 60, a=nk)
            yy = ny + name_im.height - 30
        else:
            yy = ny
        if tag_im:
            for i, ti in enumerate(tag_im):
                tk = ease_out((t - 0.3 - i * 0.05) * 3.5)
                paste(fr, ti, NX(ti.width), yy, a=tk)
                yy += ti.height - 30
        if badge:
            bk = back_out(clamp((t - 0.35) * 4))
            if layout in ("fullbleed", "split"):
                bx, by = W / 2 - badge.width / 2, yy + 10
            elif layout == "editorial":
                bx, by = 60, yy + 10
            else:
                bx, by = W - badge.width - 90, 560
            paste(fr, badge, bx, by, a=clamp((t - 0.35) * 6), scale=0.3 + 0.7 * bk)
        if prog[0]:
            draw_progress(fr, prog[0], prog[1], t)
        return fr
    return fn


def draw_progress(fr, i, n, t):
    d = ImageDraw.Draw(fr)
    f = R.F("bold", 30)
    d.text((70, 120), f"{i:02d}", font=f, fill=R.GOLD, anchor="lm")
    d.text((112, 124), f"/ {n:02d}", font=R.F("reg", 20), fill=R.MUTED, anchor="lm")
    d.text((W / 2 + 40, 122), "B H A V Y A   C A F E", font=R.F("med", 22), fill=R.CREAM, anchor="mm")
    x0, x1 = 70, W - 70
    seg = (x1 - x0 - (n - 1) * 10) / n
    for k in range(n):
        xs = x0 + k * (seg + 10)
        d.rectangle((xs, 160, xs + seg, 164), fill=R.LINE)
        fill = 1 if k < i - 1 else (clamp(t) if k == i - 1 else 0)
        if fill:
            d.rectangle((xs, 160, xs + seg * fill, 164), fill=R.GOLD)


def sc_stat(sp, cfg, rng):
    big = text_img(sp["big"], fit_font(sp["big"], "impact", 980, 330), gold=True, glow=True)
    sub = text_img(sp.get("sub", "").upper(), fit_font(sp.get("sub", "").upper(), "bold", 940, 110), fill=R.CREAM) \
        if sp.get("sub") else None
    kick = text_img(sp["kicker"].upper(), R.F("med", 34), fill=R.GOLD, shadow=False) if sp.get("kicker") else None

    def fn(t, T, bd):
        fr = bd.frame(T, rays_amount=0.6)
        kb = back_out(clamp(t * 3))
        paste(fr, big, W / 2 - big.width / 2, 760 - big.height / 2, a=clamp(t * 5), scale=1.6 - 0.6 * kb)
        if kick:
            paste(fr, kick, W / 2 - kick.width / 2, 520, a=ease_out(t * 3))
        if sub:
            k = ease_out((t - 0.2) * 3)
            paste(fr, sub, W / 2 - sub.width / 2, 960 + (1 - k) * 60, a=k)
        return fr
    return fn


def sc_split(sp, cfg, rng):
    title = text_img((sp.get("title") or "THIS or THAT").upper(), R.F("impact", 110), gold=True)
    cards = []
    for k, key in enumerate(("a", "b")):
        c = Image.new("RGBA", (900, 470), (0, 0, 0, 0))
        R.rrect(c, (0, 0, 899, 469))
        d = ImageDraw.Draw(c)
        d.ellipse((30, 30, 140, 140), fill=R.GOLD)
        d.text((85, 87), key.upper(), font=R.F("impact", 70), fill=R.BG, anchor="mm")
        f, ls = wrap_lines(sp[key], "bold", 640, 96, 2, 50)
        yy = 235 - (len(ls) - 1) * f.size * 0.6
        for l in ls:
            R.gold_text(c, (500, yy), l, f)
            yy += f.size * 1.2
        cards.append(c)
    vs = text_img("VS", R.F("impact", 90), fill=R.CREAM)

    def fn(t, T, bd):
        fr = bd.frame(T)
        paste(fr, title, W / 2 - title.width / 2, 210, a=1)
        for k, c in enumerate(cards):
            kk = ease_out((t - k * 0.08) * 4)
            paste(fr, c, 90 + (1 - kk) * (-700 if k == 0 else 700), 470 + k * 600, a=kk)
        paste(fr, vs, W / 2 - vs.width / 2, 930, a=back_out(clamp((t - 0.2) * 4)), scale=0.6 + 0.4 * back_out(clamp((t - .2) * 4)))
        d = ImageDraw.Draw(fr)
        d.rounded_rectangle((90, 1660, 990, 1682), 11, fill=R.CARD)
        d.rounded_rectangle((90, 1660, 90 + 900 * (1 - t), 1682), 11, fill=R.GOLD)
        return fr
    return fn


def sc_flash(sp, cfg, rng, seed):
    items = sp["items"]
    cards = []
    for i, n in enumerate(items):
        fr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        im, kind = _photo(n, f"{seed}{n}")
        if im is not None:
            ph = photo_circle(im, 700, kind)
            fr.alpha_composite(ph, (W // 2 - 350, 520))
        else:
            lg = R._brand("logo.png").copy()
            lg.thumbnail((500, 500))
            fr.alpha_composite(lg, (W // 2 - lg.width // 2, 620))
        nm = text_img(n.upper(), fit_font(n.upper(), "impact", 960, 150), fill=R.CREAM)
        fr.alpha_composite(nm, (W // 2 - nm.width // 2, 1260))
        if sp.get("badge"):
            b = text_img(sp["badge"], R.F("impact", 230), gold=True, glow=True)
            fr.alpha_composite(b, (W // 2 - b.width // 2, 230))
        p = price_of(cfg, n)
        if p and not sp.get("badge"):
            pb = price_badge(p)
            fr.alpha_composite(pb, (W // 2 - pb.width // 2, 1450))
        cards.append(fr)
    hint = text_img("PAUSE KARO", R.F("bold", 54), fill=R.GOLD)

    def fn(t, T, bd):
        fr = bd.frame(T, rays_amount=0.8)
        idx = int(T * FPS / 3) % len(cards)
        fr.alpha_composite(cards[idx])
        if int(T * FPS / 3) % 2:
            fl = Image.new("RGBA", (W, H), R.GOLD + (22,))
            fr.alpha_composite(fl)
        paste(fr, hint, W / 2 - hint.width / 2, 1680, a=0.6 + 0.4 * math.sin(T * 8))
        return fr
    return fn


def sc_poster(sp, cfg, rng):
    img = sp["image"].convert("RGBA")

    def fn(t, T, bd):
        fr = bd.frame(T)
        z = 0.92 + 0.06 * t
        w, h = int(1000 * z), int(1250 * z)
        im = img.resize((w, h), Image.LANCZOS)
        k = ease_out(t * 4)
        paste(fr, im, W / 2 - w / 2, H / 2 - h / 2 + (1 - k) * 100, a=k)
        return fr
    return fn


def sc_logo(sp, cfg, rng):
    logo = R._brand("logo.png").copy()
    logo.thumbnail((440, 440), Image.LANCZOS)
    wm = R._brand("wordmark.png").copy()
    wm.thumbnail((640, 360), Image.LANCZOS)
    tag = text_img(sp.get("tagline") or "Fresh Food, Good Mood", font_italic(56), fill=R.GOLD)
    ct = (sp.get("cta") or "Near IIT Roorkee").upper()
    cta = text_img(ct, fit_font(ct, "bold", 940, 46, 24), fill=R.CREAM)
    handle = text_img(cfg.get("brand", {}).get("handle", "@bhavya_cafe"), R.F("bold", 50), gold=True)

    plate = None
    if R.LIGHT:  # din wale light theme me gold logo saaf dikhe, isliye peeche dark plate
        plate = Image.new("RGBA", (860, 1080), (0, 0, 0, 0))
        ImageDraw.Draw(plate).rounded_rectangle((0, 0, 859, 1079), 60, fill=R.CREAM + (235,))

    def fn(t, T, bd):
        fr = bd.frame(T, rays_amount=ease_out(t * 2))
        k = back_out(clamp(t * 2.5))
        if plate:
            paste(fr, plate, W / 2 - plate.width / 2, 260, a=ease_out(t * 3))
        paste(fr, logo, W / 2 - logo.width / 2, 330, a=clamp(t * 4), scale=0.6 + 0.4 * k)
        paste(fr, wm, W / 2 - wm.width / 2, 800, a=ease_out((t - 0.15) * 3))
        paste(fr, tag, W / 2 - tag.width / 2, 1160, a=ease_out((t - 0.3) * 3))
        paste(fr, cta, W / 2 - cta.width / 2, 1400, a=ease_out((t - 0.4) * 3))
        paste(fr, handle, W / 2 - handle.width / 2, 1500, a=ease_out((t - 0.5) * 3))
        return fr
    return fn


SCENES = {"kinetic": sc_kinetic, "stat": sc_stat, "split": sc_split, "logo": sc_logo, "poster": sc_poster}


# ---------------------------------------------------------------- transitions
def transition(kind, prev, cur, k):
    """k: 0→1 progress of transition. prev/cur RGBA frames."""
    if kind == "cut" or prev is None:
        return cur
    if kind == "flash":
        out = cur.copy()
        a = int(255 * (1 - k) * 0.85)
        out.alpha_composite(Image.new("RGBA", (W, H), (255, 244, 220, a)))
        return out
    if kind == "push":
        out = Image.new("RGBA", (W, H))
        off = int(W * ease_in_out(k))
        out.paste(prev, (-off, 0))
        out.paste(cur, (W - off, 0))
        return out
    if kind == "zoom":
        z = 1 + 0.25 * (1 - ease_out(k))
        c = cur.resize((int(W * z), int(H * z)), Image.BILINEAR)
        c = c.crop(((c.width - W) // 2, (c.height - H) // 2, (c.width - W) // 2 + W, (c.height - H) // 2 + H))
        return Image.blend(prev, c, ease_out(k))
    if kind == "sweep":  # diagonal gold light bar wipes across
        out = Image.blend(prev, cur, ease_in_out(k))
        x = -400 + (W + 800) * ease_in_out(k)
        bar = Image.new("L", (W, H), 0)
        ImageDraw.Draw(bar).polygon([(x - 140, 0), (x + 40, 0), (x - 260, H), (x - 440, H)], fill=230)
        bar = bar.filter(ImageFilter.GaussianBlur(18))
        lay = Image.new("RGBA", (W, H), (255, 226, 150, 0))
        lay.putalpha(bar)
        out.alpha_composite(lay)
        return out
    if kind == "circle":
        m = Image.new("L", (W, H), 0)
        r = math.hypot(W, H) * 0.55 * ease_in_out(k)
        ImageDraw.Draw(m).ellipse((W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r), fill=255)
        return Image.composite(cur, prev, m)
    if kind == "blinds":
        m = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(m)
        band = H // 8
        for b in range(8):
            hh = band * ease_in_out(clamp(k * 1.4 - b * 0.05))
            d.rectangle((0, b * band, W, b * band + hh), fill=255)
        return Image.composite(cur, prev, m)
    if kind == "whip":
        off = int(W * ease_in_out(k))
        out = Image.new("RGBA", (W, H))
        out.paste(prev, (-off, 0))
        out.paste(cur, (W - off, 0))
        bl = int(40 * math.sin(math.pi * k))
        if bl > 1:
            out = out.filter(ImageFilter.BoxBlur(bl))
        return out
    if kind == "leak":
        out = Image.blend(prev, cur, ease_out(k))
        a = math.sin(math.pi * k)
        lk = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        R.glow(lk, W * 0.85, H * 0.2, 700, int(160 * a))
        lk2 = Image.new("RGBA", (W, H), (255, 150, 60, int(70 * a)))
        out.alpha_composite(lk)
        out.alpha_composite(lk2)
        return out
    if kind == "slide_up":
        off = int(H * ease_in_out(k))
        out = Image.new("RGBA", (W, H))
        out.paste(prev, (0, -off))
        out.paste(cur, (0, H - off))
        return out
    return Image.blend(prev, cur, ease_out(k))  # fade


# ---------------------------------------------------------------- music + beat
def track_bpm(path):
    m = re.search(r"(\d{2,3})\s*bpm", os.path.basename(path).lower())
    if m:
        return int(m.group(1))
    try:  # simple tempo estimate (energy autocorrelation)
        raw = subprocess.run([R.ffmpeg_bin(), "-v", "error", "-i", path, "-t", "30", "-ac", "1", "-ar", "11025",
                              "-f", "s16le", "-"], capture_output=True).stdout
        x = np.frombuffer(raw, np.int16).astype(np.float32)
        hop = 256
        e = np.array([np.sum(x[i:i + hop] ** 2) for i in range(0, len(x) - hop, hop)])
        o = np.maximum(np.diff(np.log1p(e)), 0)
        o -= o.mean()
        fps = 11025 / hop
        best, bb = 0, 100
        for bpm in range(70, 161):
            lag = fps * 60 / bpm
            l = int(round(lag))
            v = np.dot(o[:-l], o[l:]) if l < len(o) else 0
            if v > best:
                best, bb = v, bpm
        return bb
    except Exception:
        return 100


def pick_music(seed, mood=None):
    files = sorted(glob.glob(R.A("music", "*.mp3")) + glob.glob(R.A("music", "*.m4a")))
    if mood:
        m = [f for f in files if mood in os.path.basename(f).lower()]
        files = m or files
    return random.Random(seed).choice(files) if files else None


# ---------------------------------------------------------------- render
def sc_tpl(sp, cfg, rng, dur):
    """Pinterest-style template poster jo animate hota hai (layers)."""
    from . import templates as TT
    layers = sp["layers"]

    PW, PH = sp.get("size", (W, H))

    def fn(t, T, bd):
        fr = TT.compose(layers, PW, PH, t=t * dur, T=T)
        if (PW, PH) == (W, H):
            return fr
        # 4:5 design ko 9:16 reel me: beech me sharp design, upar-neeche usi ka soft blurred extension
        # upar-neeche design ke kinaron ka hi rang (clean extension, koi duplicate/blur nahi)
        top = fr.crop((0, 0, PW, 6)).resize((PW, 1), Image.BILINEAR).resize((W, (H - PH) // 2 + 2), Image.BILINEAR)
        bot = fr.crop((0, PH - 6, PW, PH)).resize((PW, 1), Image.BILINEAR).resize((W, (H - PH) // 2 + 2), Image.BILINEAR)
        bg = Image.new("RGBA", (W, H))
        bg.paste(top, (0, 0))
        bg.paste(bot, (0, H - bot.height))
        bg.alpha_composite(fr, (0, (H - PH) // 2))
        return bg
    return fn


TRANS_SFX = {"push": "whoosh", "whip": "whoosh", "slide_up": "whoosh", "sweep": "whoosh", "zoom": "whoosh",
             "circle": "whoosh", "blinds": "whoosh", "flash": "boom", "leak": "shimmer", "fade": None, "cut": None}


def render(spec, cfg, out_path, seed, mood=None):
    from . import audio
    rng = random.Random(seed)
    recent = STYLE_POOL.get("recent_music", ())
    music, bpm, start, track_len = audio.pick(mood or STYLE_POOL.get("mood"), STYLE_POOL.get("vibe"), seed, recent)
    STYLE_POOL["last_music"] = os.path.basename(music) if music else None
    beat = 60.0 / (bpm or 100)
    while beat < 0.45:
        beat *= 2
    while beat > 0.9:
        beat /= 2
    bd = Backdrop(rng, styles=STYLE_POOL.get("backgrounds") or ["bokeh"], particles=True)
    trans_pool = list(STYLE_POOL.get("transitions") or ["sweep", "fade"])

    built = []
    for i, sp in enumerate(spec):
        t = sp["type"]
        beats = sp.get("beats") or {"kinetic": 4, "product": 4, "stat": 4, "split": 6, "flash": 16,
                                    "logo": 6, "poster": 10, "tpl": 8}[t]
        dur = max(1, round(beats)) * beat
        if t == "product":
            fn = sc_product(sp, cfg, rng, f"{seed}{i}")
        elif t == "flash":
            fn = sc_flash(sp, cfg, rng, f"{seed}{i}")
        elif t == "tpl":
            fn = sc_tpl(sp, cfg, rng, dur)
        else:
            fn = SCENES[t](sp, cfg, rng)
        built.append((fn, dur, sp.get("transition") or rng.choice(trans_pool), sp))

    tmp = tempfile.mkdtemp()
    idx, T, prev_last, cover = 0, 0.0, None, None
    tdur = 0.28
    events = []
    for si, (fn, dur, tr, sp) in enumerate(built):
        t0 = idx / FPS
        if si and TRANS_SFX.get(tr):
            events.append((max(0, t0 - 0.12), TRANS_SFX[tr]))
        if sp["type"] == "product":
            events.append((t0 + 0.35 * dur * 0.6, "pop"))
        elif sp["type"] == "stat":
            events.append((t0 + 0.05, "boom"))
        elif sp["type"] == "logo":
            events.append((t0 + 0.1, "shimmer"))
        elif sp["type"] == "tpl":
            pops = sorted({round(l.delay, 2) for l in sp["layers"] if l.anim == "pop"})[:2]
            events += [(t0 + d, "pop") for d in pops]
        elif sp["type"] == "flash":
            events += [(t0 + k * 3 / FPS, "tick") for k in range(int(dur * FPS / 3))]
        n = max(1, int(round(dur * FPS)))
        last = None
        for k in range(n):
            fr = fn(k / max(1, n - 1), T, bd)
            if prev_last is not None and k / FPS < tdur:
                fr = transition(tr, prev_last, fr, (k / FPS) / tdur)
            out = fr.convert("RGB")
            if cover is None and si == (1 if len(built) > 2 else 0) and k == int(n * 0.8):
                cover = out.copy()
            out.save(os.path.join(tmp, f"{idx:05d}.jpg"), quality=92)
            idx += 1
            T += 1.0 / FPS
            last = fr
        prev_last = last
    total = idx / FPS
    if track_len and start + total > track_len - 2:  # gaane ke end-fade me na jaaye
        start = max(0.0, track_len - 2 - total)
    wav = os.path.join(tmp, "audio.wav")
    audio.mix(total, music, start, events, wav)
    cmd = [R.ffmpeg_bin(), "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(tmp, "%05d.jpg"),
           "-i", wav, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k",
           "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high", "-crf", "17",
           "-preset", "medium", "-movflags", "+faststart", "-t", f"{total:.3f}", out_path]
    subprocess.run(cmd, check=True)
    (cover or Image.open(os.path.join(tmp, "00000.jpg"))).save(out_path.replace(".mp4", "_cover.jpg"), quality=92)
    shutil.rmtree(tmp)
    return out_path
