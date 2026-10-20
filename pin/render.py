"""Design SPEC → final post image (1080x1350).

Spec (Gemini reference padh ke banata hai):
{
  "background": {"type": "solid|gradient|radial", "colors": ["#hex", ...], "direction": "vertical|horizontal|diagonal"},
  "elements": [
    {"id": "s1", "type": "shape", "shape": "rect|rounded|circle|ellipse|polygon", "box": [x0,y0,x1,y1],
     "points": [[x,y],...] (polygon), "color": "#hex", "radius": 0..0.5, "opacity": 0..1, "outline": "#hex", "z": 1},
    {"id": "p1", "type": "photo", "box": [...], "style": "cutout|fill|rounded|circle", "anchor": "center|bottom",
     "shadow": true, "z": 3},
    {"id": "t1", "type": "text", "box": [...], "role": "headline|item|price|...", "font_name": "Bebas Neue",
     "font_category": "display_condensed", "weight": "bold", "italic": false, "color": "#hex", "align": "left|center|right",
     "uppercase": true, "tracking": 0.0, "rotation": 0, "lines": 1, "pill": "#hex"|null, "stroke": "#hex"|null, "z": 4},
    {"id": "i1", "type": "icon", "kind": "arrow|line|dots|star|logo|circle_ring", "box": [...], "color": "#hex", "z": 5}
  ]
}
Box = 0..1 me (canvas ke hisaab se).
"""
import math
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from . import fonts as FN

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1080, 1350
SS = 2  # shapes supersampling (saaf kinare)


def C(c, default=(0, 0, 0)):
    try:
        c = (c or "").lstrip("#")
        if len(c) == 3:
            c = "".join(x * 2 for x in c)
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return default


def px(box):
    x0, y0, x1, y1 = box
    return int(round(min(x0, x1) * W)), int(round(min(y0, y1) * H)), int(round(max(x0, x1) * W)), int(round(max(y0, y1) * H))


# ---------------------------------------------------------------- background
def background(bg):
    bg = bg or {}
    cols = [C(c) for c in (bg.get("colors") or ["#111111"])]
    t = bg.get("type", "solid")
    if t == "solid" or len(cols) == 1:
        return Image.new("RGB", (W, H), cols[0])
    if t == "radial":
        im = Image.new("RGB", (W, H), cols[-1])
        m = Image.radial_gradient("L").resize((W, H))  # center 0 → edge 255
        im.paste(Image.new("RGB", (W, H), cols[0]), (0, 0), ImageOps.invert(m))
        return im
    d = bg.get("direction", "vertical")
    g = Image.linear_gradient("L")
    if d == "horizontal":
        g = g.rotate(90)
    elif d == "diagonal":
        g = g.rotate(45, resample=Image.BICUBIC, expand=False)
    g = g.resize((W, H))
    a, b = Image.new("RGB", (W, H), cols[0]), Image.new("RGB", (W, H), cols[1])
    return Image.composite(b, a, g)


# ---------------------------------------------------------------- shapes
def shape_mask(e):
    """Shape ka full-canvas mask (L). Two-tone text aur shape drawing dono me kaam aata hai."""
    x0, y0, x1, y1 = px(e["box"])
    m = Image.new("L", (W * SS, H * SS), 0)
    d = ImageDraw.Draw(m)
    kind = e.get("shape", "rect")
    bb = (x0 * SS, y0 * SS, x1 * SS, y1 * SS)
    if kind == "polygon" and e.get("points"):
        d.polygon([(p[0] * W * SS, p[1] * H * SS) for p in e["points"]], fill=255)
    elif kind in ("circle", "ellipse"):
        if kind == "circle":
            r = min(x1 - x0, y1 - y0) / 2
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            bb = ((cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS)
        d.ellipse(bb, fill=255)
    elif kind == "rounded":
        d.rounded_rectangle(bb, radius=float(e.get("radius", 0.15)) * min(x1 - x0, y1 - y0) * SS, fill=255)
    else:
        d.rectangle(bb, fill=255)
    if e.get("hole"):  # beech me ellipse kaat do (arc / ring / curved band)
        h0, k0, h1, k1 = px(e["hole"])
        d.ellipse((h0 * SS, k0 * SS, h1 * SS, k1 * SS), fill=0)
    m = m.resize((W, H), Image.LANCZOS)
    if e.get("rotation"):
        m = m.rotate(-float(e["rotation"]), resample=Image.BICUBIC, center=((x0 + x1) / 2, (y0 + y1) / 2))
    return m


def draw_shape(canvas, e):
    if e.get("hole") or not e.get("outline"):
        col = C(e.get("color"), (200, 200, 200))
        m = shape_mask(e)
        if e.get("opacity") not in (None, 1, 1.0):
            m = m.point(lambda v: int(v * float(e["opacity"])))
        canvas.paste(Image.new("RGBA", canvas.size, col + (255,)), (0, 0), m)
        return
    _draw_shape_outline(canvas, e)


def _draw_shape_outline(canvas, e):
    x0, y0, x1, y1 = px(e["box"])
    col = C(e.get("color"), (200, 200, 200))
    alpha = int(255 * float(e.get("opacity", 1) or 1))
    lay = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    kind = e.get("shape", "rect")
    fill = col + (alpha,) if e.get("color") else None
    out = C(e["outline"]) + (255,) if e.get("outline") else None
    ow = int((e.get("outline_width") or 4) * SS)
    bb = (x0 * SS, y0 * SS, x1 * SS, y1 * SS)
    if kind == "polygon" and e.get("points"):
        pts = [(p[0] * W * SS, p[1] * H * SS) for p in e["points"]]
        d.polygon(pts, fill=fill, outline=out, width=ow if out else 0)
    elif kind in ("circle", "ellipse"):
        if kind == "circle":
            r = min(x1 - x0, y1 - y0) / 2
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            bb = ((cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS)
        d.ellipse(bb, fill=fill, outline=out, width=ow if out else 0)
    elif kind == "rounded":
        r = float(e.get("radius", 0.15)) * min(x1 - x0, y1 - y0) * SS
        d.rounded_rectangle(bb, radius=r, fill=fill, outline=out, width=ow if out else 0)
    else:
        d.rectangle(bb, fill=fill, outline=out, width=ow if out else 0)
    lay = lay.resize((W, H), Image.LANCZOS)
    if e.get("rotation"):
        lay = lay.rotate(-float(e["rotation"]), resample=Image.BICUBIC, center=((x0 + x1) / 2, (y0 + y1) / 2))
    canvas.alpha_composite(lay)


# ---------------------------------------------------------------- text
def _draw_tracked(text, font, color, tracking, stroke=None):
    """Letter-spacing ke saath text → RGBA (tight)."""
    sw = 2 if stroke else 0
    if not tracking:
        bb = font.getbbox(text, stroke_width=sw)
        im = Image.new("RGBA", (bb[2] - bb[0] + 4, bb[3] - bb[1] + 4), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((2 - bb[0], 2 - bb[1]), text, font=font, fill=color + (255,), stroke_width=sw,
                                stroke_fill=(C(stroke) + (255,)) if stroke else None)
        return im
    gap = tracking * font.size
    widths = [font.getlength(ch) for ch in text]
    total = sum(widths) + gap * (len(text) - 1)
    asc, desc = font.getmetrics()
    im = Image.new("RGBA", (int(total) + 8, asc + desc + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = 4
    for ch, w in zip(text, widths):
        d.text((x, 4), ch, font=font, fill=color + (255,), stroke_width=sw,
               stroke_fill=(C(stroke) + (255,)) if stroke else None)
        x += w + gap
    bb = im.getbbox() or (0, 0, 1, 1)
    return im.crop(bb)


def _wrap(words, n):
    """Words ko n lines me baraabar baanto."""
    if n <= 1 or len(words) <= 1:
        return [" ".join(words)]
    n = min(n, len(words))
    best, best_score = None, 1e9
    import itertools
    for cuts in itertools.combinations(range(1, len(words)), n - 1):
        parts = [words[a:b] for a, b in zip((0,) + cuts, cuts + (len(words),))]
        lens = [len(" ".join(p)) for p in parts]
        sc = max(lens) - min(lens)
        if sc < best_score:
            best, best_score = parts, sc
    return [" ".join(p) for p in best]


def text_image(e, text, box_w, box_h):
    """Text ko box me max size pe fit karo (lines/tracking/align ke saath)."""
    if e.get("uppercase"):
        text = text.upper()
    spec = FN.resolve(e.get("font_name"), e.get("font_category", "sans"), e.get("weight", "bold"), bool(e.get("italic")))
    if "₹" in text and not FN.has_glyph(os.path.join(FN.FONT_DIR, spec[0]), "₹"):
        spec = FN.LOCAL["sans_bold"]
    col = C(e.get("color"), (255, 255, 255))
    lines_n = max(1, int(e.get("lines") or 1))
    words = text.split()
    if "\n" in text:
        lines = text.split("\n")
    else:
        lines = _wrap(words, lines_n)
    tracking = float(e.get("tracking") or 0)
    lh = float(e.get("line_height") or 1.0)
    lo, hi = 6, int(box_h * 1.6 / max(1, len(lines))) + 10
    best = None
    while lo <= hi:  # binary search: sabse bada size jo box me aaye
        mid = (lo + hi) // 2
        f = FN.font(spec, mid)
        ims = [_draw_tracked(l, f, col, tracking, e.get("stroke")) for l in lines]
        asc, desc = f.getmetrics()
        step = int((asc + desc) * 0.92 * lh)
        tw = max(i.width for i in ims)
        th = step * (len(ims) - 1) + ims[-1].height if len(ims) > 1 else ims[0].height
        if tw <= box_w and th <= box_h:
            best = (ims, step, tw, th)
            lo = mid + 1
        else:
            hi = mid - 1
    if not best:
        f = FN.font(spec, 6)
        ims = [_draw_tracked(l, f, col, tracking) for l in lines]
        best = (ims, 8, max(i.width for i in ims), sum(i.height for i in ims))
    ims, step, tw, th = best
    out = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    y = 0
    al = e.get("align", "center")
    for i, im in enumerate(ims):
        x = 0 if al == "left" else (tw - im.width if al == "right" else (tw - im.width) // 2)
        yy = y if i == 0 else y
        out.alpha_composite(im, (x, min(yy, th - im.height)))
        y += step
    return out


def ref_shape(t):
    """Original text ka 'aakaar' (bina asli shabdon ke): ascender/descender/capital pattern — size aur baseline
    match karne ke liye. Dusre brand ka text save nahi hota."""
    out = []
    for ch in t or "":
        if ch.isupper():
            out.append("H")
        elif ch.isdigit():
            out.append("8")
        elif ch in "bdfhklt":
            out.append("h")
        elif ch in "gjpqy":
            out.append("p")
        elif ch.isalpha():
            out.append("x")
        else:
            out.append(ch)
    return "".join(out)


def _single_line_matched(canvas, e, text):
    """Ek line wala text: original ke size + baseline pe likho (reference jaisa hi dikhe)."""
    shape = e.get("ref_shape") or ref_shape(e.get("text", ""))
    if not shape or "\n" in shape or "\n" in text or int(e.get("lines") or 1) > 1 or e.get("rotation") or e.get("pill"):
        return False
    if e.get("uppercase"):
        text, shape = text.upper(), shape.upper()
    x0, y0, x1, y1 = px(e["box"])
    bw, bh = x1 - x0, y1 - y0
    spec = FN.resolve(e.get("font_name"), e.get("font_category", "sans"), e.get("weight", "bold"), bool(e.get("italic")))
    if "₹" in text and not FN.has_glyph(os.path.join(FN.FONT_DIR, spec[0]), "₹"):
        spec = FN.LOCAL["sans_bold"]
    lo, hi, size = 6, int(bh * 2.5) + 10, 6
    while lo <= hi:  # original ka size: uski ink box me fit ho
        mid = (lo + hi) // 2
        l, t, r, b = FN.font(spec, mid).getbbox(shape, anchor="ls")
        if (r - l) <= bw * 1.02 and (b - t) <= bh * 1.02:
            size, lo = mid, mid + 1
        else:
            hi = mid - 1
    f = FN.font(spec, size)
    l, t, r, b = f.getbbox(shape, anchor="ls")
    base = y0 + (bh - (b - t)) / 2 - t  # original ki baseline
    tracking = float(e.get("tracking") or 0)
    if e.get("role") in ("price", "offer", "giant_word", "item_name"):  # chhota naya text → jagah bharne do (max 1.8x)
        cap = size
        for s2 in range(size, int(size * 1.8) + 1, 2):
            l2, t2, r2, b2 = FN.font(spec, s2).getbbox(text, anchor="ls")
            if (r2 - l2) + tracking * s2 * max(0, len(text) - 1) > bw or (b2 - t2) > bh * 1.05:
                break
            cap = s2
        if cap > size:
            size, f = cap, FN.font(spec, cap)
            l, t, r, b = f.getbbox(text, anchor="ls")
            base = y0 + (bh - (b - t)) / 2 - t
    while size > 6:  # naya text chauda ho to hi chhota karo
        tw = f.getlength(text) + tracking * size * max(0, len(text) - 1)
        if tw <= bw * 1.02:
            break
        size -= 2
        f = FN.font(spec, size)
    col = C(e.get("color"), (255, 255, 255))
    lay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    tw = f.getlength(text) + tracking * size * max(0, len(text) - 1)
    al = e.get("align", "center")
    x = x0 if al == "left" else (x1 - tw if al == "right" else x0 + (bw - tw) / 2)
    sw = 2 if e.get("stroke") else 0
    if tracking:
        for ch in text:
            d.text((x, base), ch, font=f, fill=col + (255,), anchor="ls", stroke_width=sw,
                   stroke_fill=(C(e["stroke"]) + (255,)) if sw else None)
            x += f.getlength(ch) + tracking * size
    else:
        d.text((x, base), text, font=f, fill=col + (255,), anchor="ls", stroke_width=sw,
               stroke_fill=(C(e["stroke"]) + (255,)) if sw else None)
    if e.get("alt_color") and e.get("_alt_mask") is not None:
        alt = Image.new("RGBA", canvas.size, C(e["alt_color"]) + (255,))
        alt.putalpha(ImageChops.multiply(lay.getchannel("A"), e["_alt_mask"]))
        canvas.alpha_composite(lay)
        canvas.alpha_composite(alt)
    else:
        canvas.alpha_composite(lay)
    return True


def draw_text(canvas, e, text):
    if not text:
        return
    if _single_line_matched(canvas, e, text):
        return
    x0, y0, x1, y1 = px(e["box"])
    bw, bh = x1 - x0, y1 - y0
    rot = int(round(float(e.get("rotation") or 0) / 90.0)) * 90 if abs(float(e.get("rotation") or 0)) >= 45 else 0
    pad = 0
    if e.get("pill"):
        pad = int(min(bw, bh) * 0.18)
    if rot in (90, -90, 270, -270):
        im = text_image(e, text, bh - 2 * pad, bw - 2 * pad).rotate(rot if rot > 0 else rot, expand=True)
    else:
        im = text_image(e, text, bw - 2 * pad, bh - 2 * pad)
        small = float(e.get("rotation") or 0)
        if small:
            im = im.rotate(-small if rot == 0 else 0, expand=True, resample=Image.BICUBIC)
    al = e.get("align", "center")
    if e.get("pill"):
        pw, ph = im.width + 2 * pad + int(pad * 0.8), im.height + 2 * pad
        pill = Image.new("RGBA", (pw * SS, ph * SS), (0, 0, 0, 0))
        ImageDraw.Draw(pill).rounded_rectangle((0, 0, pw * SS - 1, ph * SS - 1), radius=ph * SS // 2,
                                               fill=C(e["pill"]) + (255,))
        pill = pill.resize((pw, ph), Image.LANCZOS)
        pill.alpha_composite(im, ((pw - im.width) // 2, (ph - im.height) // 2))
        im = pill
    x = x0 if al == "left" else (x1 - im.width if al == "right" else x0 + (bw - im.width) // 2)
    y = y0 + (bh - im.height) // 2
    if e.get("alt_color") and e.get("_alt_mask") is not None:  # do-rang wala text (shape ke upar doosra rang)
        lay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        lay.alpha_composite(im, (int(x), int(y)))
        alt = Image.new("RGBA", canvas.size, C(e["alt_color"]) + (255,))
        alt.putalpha(ImageChops.multiply(lay.getchannel("A"), e["_alt_mask"]))
        canvas.alpha_composite(lay)
        canvas.alpha_composite(alt)
        return
    canvas.alpha_composite(im, (int(x), int(y)))


# ---------------------------------------------------------------- photo
def draw_photo(canvas, e, photo, cutout=None):
    if photo is None:
        return
    x0, y0, x1, y1 = px(e["box"])
    bw, bh = x1 - x0, y1 - y0
    style = e.get("style", "cutout")
    if style == "cutout" and cutout is not None:
        im = cutout.copy()
        s_fit = min(bw / im.width, bh / im.height)
        # khane ka aakaar box se alag ho (lamba glass ki jagah chaudi plate) → thodi zyada jagah do, chhota na dikhe
        s_area = math.sqrt(bw * bh * 0.78 / (im.width * im.height))
        s = max(s_fit, min(s_area, bw * 1.3 / im.width, bh * 1.02 / im.height))
        cx = x0 + bw / 2
        max_half = min(cx - W * 0.03, W * 0.97 - cx)  # frame ke kinare se bahar na jaye
        if im.width * s / 2 > max_half:
            s = max(s_fit, max_half * 2 / im.width)

        def hits(sc):  # badi photo kisi text pe na chadhe
            w_, h_ = im.width * sc, im.height * sc
            rx0 = x0 + (bw - w_) / 2
            ry0 = y1 - h_ if e.get("anchor") == "bottom" else y0 + (bh - h_) / 2
            return any(not (rx0 + w_ * 0.985 < a0 or rx0 + w_ * 0.015 > a1 or ry0 + h_ * 0.985 < b0 or ry0 + h_ * 0.015 > b1)
                       for a0, b0, a1, b1 in e.get("_avoid", []))
        while s > s_fit * 1.01 and hits(s):
            s = max(s_fit, s * 0.95)
        im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
        x = x0 + (bw - im.width) // 2
        y = y1 - im.height if e.get("anchor") == "bottom" else y0 + (bh - im.height) // 2
        if e.get("shadow", True):
            sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            m = Image.new("L", canvas.size, 0)
            m.paste(im.getchannel("A"), (x, y + int(bh * 0.03)))
            sh.putalpha(m.filter(ImageFilter.GaussianBlur(max(8, bw // 30))).point(lambda v: int(v * 0.45)))
            canvas.alpha_composite(sh)
        canvas.alpha_composite(im, (x, y))
        return
    # fill / rounded / circle → crop (cover) + mask
    im = photo.convert("RGB")
    s = max(bw / im.width, bh / im.height)
    im = im.resize((max(bw, int(im.width * s) + 1), max(bh, int(im.height * s) + 1)), Image.LANCZOS)
    l, t = (im.width - bw) // 2, (im.height - bh) // 2
    im = im.crop((l, t, l + bw, t + bh)).filter(ImageFilter.UnsharpMask(1.2, 40, 2))
    m = Image.new("L", (bw * SS, bh * SS), 0)
    d = ImageDraw.Draw(m)
    if style == "circle":
        d.ellipse((0, 0, bw * SS - 1, bh * SS - 1), fill=255)
    elif style == "rounded":
        d.rounded_rectangle((0, 0, bw * SS - 1, bh * SS - 1), radius=int(float(e.get("radius", 0.08)) * min(bw, bh) * SS),
                            fill=255)
    else:
        d.rectangle((0, 0, bw * SS, bh * SS), fill=255)
    m = m.resize((bw, bh), Image.LANCZOS)
    canvas.paste(im, (x0, y0), m)


# ---------------------------------------------------------------- icons
def draw_icon(canvas, e):
    x0, y0, x1, y1 = px(e["box"])
    bw, bh = max(2, x1 - x0), max(2, y1 - y0)
    col = C(e.get("color"), (255, 255, 255))
    kind = e.get("kind", "line")
    lay = Image.new("RGBA", (bw * SS, bh * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    lw = max(2, int(min(bw, bh) * 0.06)) * SS
    if kind == "logo":
        wm = Image.open(os.path.join(ROOT, "assets", "brand", "wordmark.png")).convert("RGBA")
        wm.thumbnail((bw, bh), Image.LANCZOS)
        tint = Image.new("RGBA", wm.size, col + (255,))
        tint.putalpha(wm.getchannel("A"))
        canvas.alpha_composite(tint, (x0 + (bw - wm.width) // 2, y0 + (bh - wm.height) // 2))
        return
    if kind == "arrow":
        pts = []
        for i in range(24):
            t = i / 23
            pts.append((t * bw * SS * 0.9, (bh * 0.75 - math.sin(t * math.pi) * bh * 0.5) * SS))
        d.line(pts, fill=col + (255,), width=lw, joint="curve")
        ex, ey = pts[-1]
        px_, py_ = pts[-4]
        a = math.atan2(ey - py_, ex - px_)
        for s in (-1, 1):
            b = a + math.pi + s * 0.5
            d.line((ex, ey, ex + math.cos(b) * bw * 0.18 * SS, ey + math.sin(b) * bw * 0.18 * SS), fill=col + (255,), width=lw)
    elif kind == "dots":
        r = min(bw, bh) * 0.12 * SS
        n = max(2, int(bw / (bh * 0.6)))
        for i in range(n):
            cx = (i + 0.5) * bw * SS / n
            d.ellipse((cx - r, bh * SS / 2 - r, cx + r, bh * SS / 2 + r), fill=col + (255,))
    elif kind == "star":
        cx, cy, R = bw * SS / 2, bh * SS / 2, min(bw, bh) * SS / 2
        pts = [(cx + math.cos(math.pi / 2 + i * math.pi / 5) * (R if i % 2 == 0 else R * 0.45),
                cy - math.sin(math.pi / 2 + i * math.pi / 5) * (R if i % 2 == 0 else R * 0.45)) for i in range(10)]
        d.polygon(pts, fill=col + (255,))
    elif kind == "circle_ring":
        d.ellipse((lw, lw, bw * SS - lw, bh * SS - lw), outline=col + (255,), width=lw)
    else:  # line
        if bw >= bh:
            d.line((0, bh * SS / 2, bw * SS, bh * SS / 2), fill=col + (255,), width=lw)
        else:
            d.line((bw * SS / 2, 0, bw * SS / 2, bh * SS), fill=col + (255,), width=lw)
    canvas.alpha_composite(lay.resize((bw, bh), Image.LANCZOS), (x0, y0))


# ---------------------------------------------------------------- compose
def _overlap(a, b):
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def _prep(spec, by_id):
    els = spec.get("elements", [])
    for e in els:
        if e.get("type") == "text" and e.get("alt_over") in by_id:
            e["_alt_mask"] = shape_mask(by_id[e["alt_over"]])
        if e.get("type") == "photo":  # jin texts se photo pehle se nahi takrati, unse aage bhi na takraye
            pb = px(e["box"])
            e["_avoid"] = [px(t["box"]) for t in els if t.get("type") == "text" and not _overlap(px(t["box"]), pb)]



def render(spec, texts, photo=None, cutout=None):
    """texts = {element_id: text}. photo = PIL (original), cutout = PIL RGBA (background hata hua)."""
    canvas = background(spec.get("background")).convert("RGBA")
    by_id = {e.get("id"): e for e in spec.get("elements", [])}
    _prep(spec, by_id)
    els = sorted(enumerate(spec.get("elements", [])), key=lambda ie: (float(ie[1].get("z", 0) or 0), ie[0]))
    for _, e in els:
        try:
            t = e.get("type")
            if t == "shape":
                draw_shape(canvas, e)
            elif t == "photo":
                draw_photo(canvas, e, photo, cutout)
            elif t == "text":
                draw_text(canvas, e, texts.get(e.get("id"), e.get("text", "")))
            elif t == "icon":
                draw_icon(canvas, e)
        except Exception as ex:
            print("element skip:", e.get("id"), ex)
    for e in spec.get("elements", []):
        e.pop("_alt_mask", None)
        e.pop("_avoid", None)
    return canvas.convert("RGB")


# ---------------------------------------------------------------- reel ke liye: alag-alag layers + size
def set_size(w, h):
    global W, H
    W, H = int(w), int(h)


def render_layers(spec, texts, photo=None, cutout=None):
    """Background + har element ki alag RGBA layer (sirf uska hissa crop karke) → reel animation ke liye.
    Return: (bg RGB, [(element, layer_crop RGBA, (x, y))]) — z-order me."""
    bg = background(spec.get("background")).convert("RGB")
    by_id = {e.get("id"): e for e in spec.get("elements", [])}
    _prep(spec, by_id)
    out = []
    els = sorted(enumerate(spec.get("elements", [])), key=lambda ie: (float(ie[1].get("z", 0) or 0), ie[0]))
    for _, e in els:
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        try:
            t = e.get("type")
            if t == "shape":
                draw_shape(lay, e)
            elif t == "photo":
                draw_photo(lay, e, photo, cutout)
            elif t == "text":
                draw_text(lay, e, texts.get(e.get("id"), e.get("text", "")))
            elif t == "icon":
                draw_icon(lay, e)
        except Exception as ex:
            print("element skip:", e.get("id"), ex)
            continue
        bb = lay.getchannel("A").getbbox()
        if bb:
            out.append((e, lay.crop(bb), (bb[0], bb[1])))
    for e in spec.get("elements", []):
        e.pop("_alt_mask", None)
        e.pop("_avoid", None)
    return bg, out


def expand_to(spec, from_aspect=1350 / 1080, to_aspect=1920 / 1080):
    """4:5 post design → 9:16 reel: design beech me, upar-neeche saans lene ki jagah (sizes same rehte hain).
    Jo cheezein kinare tak thi (background photo, patti) wo kinare tak hi failti hain."""
    import copy
    s2 = copy.deepcopy(spec)
    if to_aspect <= from_aspect:
        return s2
    k = from_aspect / to_aspect

    def fy(y, snap=True):
        if snap and abs(y) <= 0.003:
            return 0.0  # kinare tak tha → kinare tak hi
        if snap and abs(y - 1) <= 0.003:
            return 1.0
        return 0.5 + (y - 0.5) * k
    for e in s2["elements"]:
        x0, y0, x1, y1 = e["box"]
        e["box"] = [x0, fy(y0), x1, fy(y1)]
        if e.get("hole"):
            hx0, hy0, hx1, hy1 = e["hole"]
            e["hole"] = [hx0, fy(hy0, False), hx1, fy(hy1, False)]
        if e.get("points"):
            e["points"] = [[p[0], fy(p[1])] for p in e["points"]]
    return s2
