"""Bot ka dimaag: Pinterest reference → design spec → cafe ka content → compare + sudhaar.

1. analyze(): Gemini reference dekh ke har cheez ki jagah (box), rang, font, size batata hai.
2. sample_colors(): rang Gemini ke andaaze se nahi — reference ke asli pixels se naape jaate hain (exact match).
3. write_texts(): har text ki jagah Bhavya Cafe ka text, utni hi lambai ka (layout na toote).
4. compare(): bana hua post vs reference → Gemini batata hai kya alag hai → bot theek karta hai (2 baar tak).
"""
import json

import numpy as np
from PIL import Image, ImageDraw

from . import ai, render as R
from .fonts import LOCAL

ROLES = ["headline", "subheadline", "item_name", "giant_word", "price", "offer", "tagline", "body", "cta", "brand",
         "handle", "contact", "location", "label", "small_caps", "date", "other"]
CATS = list(LOCAL)

ANALYZE = """You are a senior graphic designer. Reverse-engineer this social-media food poster into an exact,
re-buildable DESIGN SPEC so we can rebuild the SAME design (same layout, colours, fonts, sizes) for our own cafe
with our own food photo and our own text.

Coordinates: use "box_2d": [ymin, xmin, ymax, xmax] normalised 0-1000 over the WHOLE image. Be precise — measure
tight boxes around each element.

List elements (back to front):
- "shape": every flat coloured panel, band, circle, blob, card, stripe, badge background, diagonal block.
  shape: rect | rounded | circle | ellipse | polygon. For polygon give "points": [[y,x],...] in 0-1000.
  For a curved band/arc/ring: shape "ellipse" with its full (possibly off-canvas, values <0 or >1000 allowed) box and
  "hole_2d" = box of the inner ellipse that is cut out.
- "photo": the main food photo area. style: "cutout" (food floats on the design, no photo background),
  "fill" (rectangular photo with its own background), "rounded", "circle". If a photo is the full background,
  box = whole image and style "fill". Give "food" = what food it shows.
- "text": EVERY separate text block (each line-group separately; giant stacked letters → one element per row).
  Give: "text" (exact original text), "role" (one of ROLES), "font_name" (closest GOOGLE FONTS family name),
  "font_category" (one of CATS), "weight" (light|regular|medium|semibold|bold|extrabold|black), "italic",
  "uppercase", "tracking" (letter spacing as fraction of font size, 0 normal, 0.3 very wide), "lines" (number of
  lines), "align" (left|center|right), "rotation" (degrees, e.g. 90 for vertical reading bottom-to-top, -90
  top-to-bottom), "pill" (hex colour if the text sits on its own rounded pill/button, else null).
  If one text is drawn in TWO colours where it crosses a shape, give "alt_color" and "alt_over" = that shape's id.
- "icon": small graphics — arrow | line | dots | star | circle_ring | logo (any brand logo / logo text).
Every element: "id" (short unique), "type", "color" (hex), "z" (stacking order, bigger = in front).
Also "background": {"type": solid|gradient|radial, "colors": [hex...], "direction": vertical|horizontal|diagonal}.

ROLES = %s
CATS = %s
Return ONLY JSON: {"background": {...}, "elements": [...], "food": "...", "mood": "short design description"}"""


def _box(b2d):
    """[ymin,xmin,ymax,xmax] 0-1000 → [x0,y0,x1,y1] 0-1."""
    y0, x0, y1, x1 = [float(v) / 1000.0 for v in b2d]
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


def normalise(raw):
    els = []
    for i, e in enumerate(raw.get("elements") or []):
        if not isinstance(e, dict) or e.get("type") not in ("shape", "photo", "text", "icon"):
            continue
        b = e.get("box_2d") or e.get("box")
        if not b or len(b) != 4:
            continue
        e = dict(e)
        e["box"] = _box(b) if e.get("box_2d") else b
        e.pop("box_2d", None)
        if e.get("hole_2d"):
            e["hole"] = _box(e.pop("hole_2d"))
        if e.get("points"):
            e["points"] = [[float(p[1]) / 1000.0, float(p[0]) / 1000.0] for p in e["points"] if len(p) == 2]
        e.setdefault("id", f"e{i}")
        e.setdefault("z", i)
        if e["type"] == "text" and e.get("font_category") not in CATS:
            e["font_category"] = "sans_bold"
        els.append(e)
    bg = raw.get("background") or {"type": "solid", "colors": ["#111111"]}
    return {"background": bg, "elements": els, "food": raw.get("food", ""), "mood": raw.get("mood", "")}


def reframe(spec, ref_size, target=1350 / 1080):
    """Lamba reference (jaise 9:16) → Instagram 4:5. Pehle khaali upar/neeche hata ke, phir jitna kam ho sake utna dabao."""
    w, h = ref_size
    ratio = (h / w) / target  # >1 matlab reference zyada lamba hai
    if ratio <= 1.01:
        return spec
    win = 1.0 / ratio  # 4:5 window ki height (0-1 units me)
    els = [e for e in spec["elements"] if e["type"] in ("text", "photo", "icon")] or spec["elements"]
    if not els:
        return spec
    top = min(e["box"][1] for e in els)
    bot = max(e["box"][3] for e in els)
    pad = 0.025
    span = (bot - top) + 2 * pad
    if span <= win:  # sab kuch 4:5 window me aa jata hai → bina dabaye crop
        c = (top + bot) / 2
        a = min(max(0.0, c - win / 2), 1.0 - win)
        size = win
    else:  # thoda dabana padega — sirf utna jitna zaroori
        a, size = max(0.0, top - pad), min(1.0, bot + pad) - max(0.0, top - pad)

    def fy(y):
        return (y - a) / size
    for e in spec["elements"]:
        x0, y0, x1, y1 = e["box"]
        e["box"] = [x0, fy(y0), x1, fy(y1)]
        if e.get("hole"):
            hx0, hy0, hx1, hy1 = e["hole"]
            e["hole"] = [hx0, fy(hy0), hx1, fy(hy1)]
        if e.get("points"):
            e["points"] = [[p[0], fy(p[1])] for p in e["points"]]
    print(f"Reframe: reference {w}x{h} → 4:5 (window {a:.2f}–{a + size:.2f}, dabav {max(1.0, size / win):.2f}x)")
    return spec


def analyze(ref, cfg):
    prompt = ANALYZE % (ROLES, CATS)
    d = ai.call([{"text": prompt}, ai.image_part(ref, 1600)], cfg, temperature=0.2, timeout=180, quality=True)
    if not isinstance(d, dict) or not d.get("elements"):
        return None
    return normalise(d)  # NOTE: sample_colors ke BAAD reframe karna (colours original coordinates se)


# ---------------------------------------------------------------- exact colours from pixels
def _hex(c):
    return "#%02x%02x%02x" % tuple(int(v) for v in c[:3])


def _region(arr, box, shrink=0.0):
    h, w = arr.shape[:2]
    x0, y0, x1, y1 = box
    dx, dy = (x1 - x0) * shrink, (y1 - y0) * shrink
    a = arr[int(max(0, (y0 + dy)) * h):int(min(1, (y1 - dy)) * h), int(max(0, (x0 + dx)) * w):int(min(1, (x1 - dx)) * w)]
    return a.reshape(-1, 3) if a.size else np.zeros((0, 3))


def _kmeans(px, k=3, it=8):
    if len(px) < k:
        return [px.mean(0)] if len(px) else [], [len(px)]
    px = px[np.random.default_rng(0).choice(len(px), min(6000, len(px)), replace=False)].astype(np.float32)
    cent = px[np.linspace(0, len(px) - 1, k).astype(int)]
    for _ in range(it):
        lab = ((px[:, None] - cent[None]) ** 2).sum(-1).argmin(1)
        cent = np.array([px[lab == j].mean(0) if (lab == j).any() else cent[j] for j in range(k)])
    counts = [(lab == j).sum() for j in range(k)]
    return list(cent), counts


def sample_colors(spec, ref):
    """Har shape/text/background ka rang reference ke pixels se."""
    arr = np.asarray(ref.convert("RGB").resize((500, int(500 * ref.height / ref.width))), np.float32)
    h, w = arr.shape[:2]
    els = spec["elements"]
    blockers = [e["box"] for e in els if e["type"] in ("photo", "text")]

    def mask_of(e):
        R.W, R.H = w, h
        try:
            m = np.asarray(R.shape_mask(e)) > 128
        finally:
            R.W, R.H = 1080, 1350
        return m

    # background: border pixels jo kisi photo ke andar na hon
    border = np.concatenate([arr[:6].reshape(-1, 3), arr[-6:].reshape(-1, 3), arr[:, :6].reshape(-1, 3), arr[:, -6:].reshape(-1, 3)])
    if spec["background"].get("type", "solid") == "solid":
        cents, cnt = _kmeans(border, 3)
        if cents:
            spec["background"]["colors"] = [_hex(cents[int(np.argmax(cnt))])]
    for e in els:
        try:
            if e["type"] == "shape":
                m = mask_of(e)
                for b in blockers:  # text/photo ke pixels shape ke rang me na milein
                    x0, y0, x1, y1 = b
                    m[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)] = False
                px = arr[m]
                if len(px) > 50:
                    cents, cnt = _kmeans(px, 2)
                    e["color"] = _hex(cents[int(np.argmax(cnt))])
            elif e["type"] == "text" and e.get("alt_over") in {x["id"] for x in els}:
                continue  # do-rang text: neeche alag se (shape + background ke rang ulte)
            elif e["type"] == "text" and not e.get("rotation"):
                x0, y0, x1, y1 = e["box"]
                sub = arr[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)].copy()
                keep = np.ones(sub.shape[:2], bool)
                for pb in [b for b in blockers if b is not e["box"]]:  # photo ke pixels text ke rang me na gine jayein
                    if any(o is pb for o in [x["box"] for x in els if x["type"] == "photo"]):
                        ax0, ay0 = int((pb[0] - x0) * w), int((pb[1] - y0) * h)
                        ax1, ay1 = int((pb[2] - x0) * w), int((pb[3] - y0) * h)
                        keep[max(0, ay0):max(0, ay1), max(0, ax0):max(0, ax1)] = False
                px = sub[keep].reshape(-1, 3) if keep.any() else sub.reshape(-1, 3)
                if len(px) < 30:
                    continue
                cents, cnt = _kmeans(px, 3)
                # aas-paas (box ke kinare) ka rang = background; text = usse sabse alag cluster
                x0, y0, x1, y1 = e["box"]
                ring = np.concatenate([_region(arr, [x0, y0, x1, y0 + (y1 - y0) * 0.08]),
                                       _region(arr, [x0, y1 - (y1 - y0) * 0.08, x1, y1])])
                bgc = ring.mean(0) if len(ring) else cents[int(np.argmax(cnt))]
                total = sum(cnt)
                cand = [(np.linalg.norm(c - bgc), c) for c, n in zip(cents, cnt) if n > total * 0.04]
                if cand:
                    dist, col = max(cand, key=lambda x: x[0])
                    if dist > 40:
                        e["color"] = _hex(col)
            elif e["type"] == "icon":
                px = _region(arr, e["box"])
                if len(px) > 20:
                    cents, cnt = _kmeans(px, 2)
                    e["color"] = _hex(cents[int(np.argmin(cnt))])
        except Exception as ex:
            print("colour sample skip", e.get("id"), ex)
    by = {x["id"]: x for x in els}
    bgcol = (spec["background"].get("colors") or ["#000000"])[0]
    for e in els:  # do-rang text: background pe shape ka rang, shape pe background ka rang (Pinterest ka common style)
        if e["type"] == "text" and e.get("alt_over") in by:
            e["color"] = by[e["alt_over"]].get("color", e.get("color"))
            e["alt_color"] = bgcol
    return spec


# ---------------------------------------------------------------- cafe ka content
def write_texts(spec, item, cfg, idea=None, preset_text=""):
    menu = {m["name"]: m.get("price") for m in cfg["menu"]}
    brand = cfg["brand"]
    blocks = [{"id": e["id"], "role": e.get("role"), "original": e.get("text", ""),
               "chars": len(e.get("text") or e.get("ref_shape") or ""),
               "lines": e.get("lines", 1), "uppercase": e.get("uppercase", False)}
              for e in spec["elements"] if e["type"] == "text"]
    prompt = (
        "You are the copywriter of BHAVYA CAFE (premium cafe near IIT Roorkee; students + Roorkee locals). We are "
        "rebuilding a Pinterest poster design for our cafe. Replace EVERY text block with OUR text.\n"
        f"Featured item: {item} (price ₹{menu.get(item)})\nFull menu with prices: {json.dumps(menu, ensure_ascii=False)}\n"
        f"Our handle: {brand.get('handle')}  Location: near IIT Roorkee  {('Hours: ' + brand['hours']) if brand.get('hours') else ''}\n"
        f"{('OWNER IDEA (the whole post must be built around this, same vibe as the design): ' + idea) if idea else ''}\n"
        f"{('POST TYPE: ' + preset_text) if preset_text else ''}\n"
        "RULES:\n"
        "- Keep each block about the SAME number of characters as the original (±25%) and the same number of lines "
        "(use \\n between lines), so the layout stays identical. Same tone & style (if original is a big single word, "
        "give a big single word).\n"
        "- giant_word rows (one big word split into rows like BU/R/G/ER): split OUR word the same way across those ids.\n"
        "- Prices: ONLY real menu prices with ₹. NEVER invent discounts, % OFF, free delivery, phone numbers, websites or "
        "dates (the only allowed offer is the owner-approved one given in POST TYPE, written exactly). Replace such blocks with something true (Freshly made / Near IIT Roorkee / our handle / price).\n"
        "- Other brands' names/logos → 'Bhavya Cafe'. Phone/website/contact → our handle or 'Near IIT Roorkee'.\n"
        "- English or simple Hinglish, classy, no emojis.\n"
        f"BLOCKS: {json.dumps(blocks, ensure_ascii=False)}\n"
        'Return JSON: {"texts": {"<id>": "text", ...}, "caption": "Instagram caption (2-4 short lines, premium, '
        'ends with a soft call to visit)", "hashtags": ["#..."] (exactly 5, mix of #Roorkee #IITRoorkee #RoorkeeFood + 2 '
        'item-specific)}'
    )
    d = ai.text(prompt, cfg, 0.8)
    texts = {}
    if isinstance(d, dict) and isinstance(d.get("texts"), dict):
        texts = {k: str(v) for k, v in d["texts"].items()}
    giants = [b for b in blocks if b["role"] == "giant_word" and b["id"] not in texts]
    if giants:  # bada shabd rows me baanto (VA/DA/PA/V jaisa)
        n = len(giants)
        word = item.split()[-1].upper()
        if len(word) < n + 1:  # rows zyada, shabd chhota → poora naam (VADAPAV → VA/DA/PA/V)
            word = item.replace(" ", "").upper()
        base, rem = divmod(len(word), n)
        pos = 0
        for i, g in enumerate(giants):  # har row me barabar akshar (koi row khaali nahi)
            size = max(1, base + (1 if i < rem else 0))
            texts[g["id"]] = word[pos:pos + size] or word[-1]
            pos += size
    for b in blocks:  # AI na chale to bhi kuch sahi bhar do
        if b["id"] not in texts:
            texts[b["id"]] = _fallback(b, item, menu, brand)
    cap = (d or {}).get("caption") if isinstance(d, dict) else None
    tags = (d or {}).get("hashtags") if isinstance(d, dict) else None
    return texts, cap, tags


def _fallback(b, item, menu, brand):
    r = b["role"]
    if r == "price":
        return f"₹{menu.get(item)}"
    if r in ("handle", "contact"):
        return brand.get("handle", "@bhavya_cafe")
    if r == "brand":
        return "Bhavya Cafe"
    if r == "location":
        return "Near IIT Roorkee"
    if r == "cta":
        return "Visit Today"
    return item if b["chars"] >= 6 else item.split()[-1]


# ---------------------------------------------------------------- compare + fix
FIXABLE = {"box_2d", "color", "font_name", "font_category", "weight", "italic", "uppercase", "tracking", "lines",
           "align", "rotation", "pill", "shape", "radius", "style", "z", "alt_color"}


def compare(ref, ours, spec, cfg):
    ids = [{"id": e["id"], "type": e["type"], "role": e.get("role"),
            "box_2d": [round(e["box"][1] * 1000), round(e["box"][0] * 1000), round(e["box"][3] * 1000), round(e["box"][2] * 1000)]}
           for e in spec["elements"]]
    prompt = (
        "Image 1 = original Pinterest design. Image 2 = our rebuild for Bhavya Cafe (different food photo and "
        "text ON PURPOSE — do not judge content). Compare ONLY the DESIGN: layout positions, sizes, colours, fonts, "
        "letter style, shapes. Also check quality problems in image 2: food cut off or hidden behind text/shapes, text "
        "overlapping other text, text too small or cut at edges.\n"
        f"Our elements: {json.dumps(ids)}\n"
        'Return JSON: {"similarity": 1-10, "quality_ok": true/false, "problems": ["..."], "fixes": [{"id": "...", '
        '"box_2d": [ymin,xmin,ymax,xmax] (0-1000, only if position/size must change), "color": "#hex", '
        '"font_name": "...", "weight": "...", "uppercase": bool, "tracking": number, "lines": number, ...}] '
        "(max 8 most important fixes)}"
    )
    d = ai.call([{"text": prompt}, ai.image_part(ref, 1024), ai.image_part(ours, 1024)], cfg, temperature=0.2,
                timeout=180, quality=True)
    return d if isinstance(d, dict) else None


def apply_fixes(spec, fixes):
    by = {e["id"]: e for e in spec["elements"]}
    n = 0
    for f in fixes or []:
        e = by.get(f.get("id"))
        if not e:
            continue
        for k, v in f.items():
            if k == "id" or k not in FIXABLE:
                continue
            if k == "box_2d":
                if isinstance(v, list) and len(v) == 4:
                    e["box"] = _box(v)
                    n += 1
            else:
                e[k] = v
                n += 1
    return n
