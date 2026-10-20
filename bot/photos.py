"""AI food photo library.

Har menu item ki realistic food photos AI se banti hain aur assets/photos_ai/ me save ho jaati hain
(ek baar banti hain, phir har post me reuse hoti hain — isliye free limit me aaram se chalta hai).
Priority: assets/photos (tumhari asli photos) → assets/photos_stock (Pexels, free license) + assets/photos_ai → logo.
"""
import base64
import glob
import io
import os
import re
import urllib.parse

import requests
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI_DIR = os.path.join(ROOT, "assets", "photos_ai")
REAL_DIR = os.path.join(ROOT, "assets", "photos")
STOCK_DIR = os.path.join(ROOT, "assets", "photos_stock")
CREDITS = os.path.join(ROOT, "data", "photo_credits.csv")

# Pexels search words per item ("" = stock photo mat lo, ye item unique hai → sirf asli/AI photo)
STOCK_QUERY = {
    "aloo tikki burger": "veg burger", "tandoori burger": "spicy burger", "cheese burger": "cheese burger",
    "vada pav": "vada pav", "cheese burst samosa": "samosa", "bun makkhan": "bun butter tea",
    "potato twister": "tornado potato", "simple chips chaat": "indian chaat", "corn chips chaat": "corn chaat",
    "loaded chips chaat": "loaded nachos cheese", "nachos chaat": "nachos", "kulhad pizza": "",
    "veg momos": "momos", "paneer momos": "momos dumplings", "cheese sweet corn momos": "steamed dumplings",
    "peshawari khewani kheer": "kheer", "kesar pista kheer": "kheer pistachio", "butterscotch kheer": "rice pudding",
    "kulhad chai": "kulhad chai", "hot coffee": "cappuccino", "cold coffee": "iced coffee",
    "mocha shake": "chocolate milkshake", "matcha shake": "matcha latte",
}

# Indian-cafe style descriptions so the AI makes the right dish
DISH = {
    "aloo tikki burger": "an Indian aloo tikki burger: crispy spiced potato patty, onion, tomato, lettuce and mint mayo in a soft sesame bun",
    "tandoori burger": "a tandoori burger: smoky tandoori-masala crispy patty with onion rings, lettuce and tandoori mayo in a toasted bun",
    "cheese burger": "a veg cheese burger with crispy patty and a thick melting cheese slice dripping over, lettuce, tomato, sesame bun",
    "vada pav": "Mumbai-style vada pav: golden fried potato vada inside a soft pav with green chutney and red garlic chutney, one fried green chilli on the side",
    "cheese burst samosa": "a golden crispy samosa being torn apart by hand with a long gooey molten cheese pull, spiced potato and pea filling visible, more samosas and green chutney in the background, steam rising",
    "bun makkhan": "Indian bun makkhan: a soft round sweet bun sliced open and thickly loaded with white butter, served with a kulhad of chai",
    "potato twister": "spiral tornado potatoes on wooden skewers, golden and crispy, dusted with peri-peri masala and drizzled with white mayo and orange chipotle sauce, on a ceramic plate or kraft paper tray",
    "simple chips chaat": "Indian chips chaat: potato chips topped with chopped onion, tomato, sev, green and tamarind chutney and coriander, in a paper bowl",
    "corn chips chaat": "corn chips chaat: crunchy corn chips topped with sweet corn, onion, tomato, chutneys, sev and coriander, in a bowl",
    "loaded chips chaat": "loaded chips chaat: chips heavily loaded with cheese sauce, sweet corn, onion, tomato, chutneys, sev, curd and coriander",
    "nachos chaat": "Indian nachos chaat: tortilla nachos topped with salsa, cheese sauce, onion, tomato, jalapeno, sev and chutneys in a black bowl",
    "kulhad pizza": "kulhad pizza: a terracotta clay kulhad cup filled with pizza, golden-brown bubbling mozzarella overflowing and dripping down the sides, black olive rings, sweet corn, capsicum, sprinkled oregano and chilli flakes; optional fork pulling a long cheese stretch",
    "veg momos": "8 hand-pleated steamed veg momos on a wooden plate or bamboo steamer, spring onion garnish, a small bowl of fiery red momo chutney, steam rising",
    "paneer momos": "8 steamed paneer momos, one cut open showing the paneer filling, with red chutney, on a dark plate",
    "cheese sweet corn momos": "8 steamed cheese sweet corn momos, one cut open with stretchy cheese and corn filling, with red chutney",
    "peshawari khewani kheer": "Peshawari khewani kheer in a clay kulhad bowl, creamy with vermicelli, dry fruits, pistachio and almond slivers",
    "kesar pista kheer": "top-down view of creamy kesar pista kheer in a copper or clay bowl, saffron strands, slivered pistachios and almonds on top, brass spoon beside, warm linen napkin",
    "butterscotch kheer": "butterscotch kheer in a clay bowl, golden caramel colour topped with crunchy butterscotch praline bits",
    "kulhad chai": "hot masala chai in a clay kulhad cup with steam rising, a couple of cardamom pods beside it",
    "hot coffee": "a cup of hot cappuccino with latte art heart, steam rising, on a saucer",
    "cold coffee": "a tall glass of Indian cafe cold coffee with ice, whipped cream on top and chocolate syrup drizzle, condensation on the glass, a straw",
    "mocha shake": "a thick mocha chocolate-coffee shake in a tall glass with whipped cream, chocolate drizzle, chocolate chunks and a straw",
    "matcha shake": "a thick green matcha shake in a tall glass with whipped cream, matcha powder dusting and a straw",
}

STYLE = ("Professional appetizing food photography for an Instagram cafe page. {dish}. "
         "Single dish, centered, fully visible, shot slightly from above. Matte jet-black background with a soft warm "
         "golden rim light, dark moody luxury cafe style, realistic, sharp focus, natural portion size as served in a "
         "small Indian cafe (not overly fancy). No text, no logo, no watermark, no hands, no people. Square image.")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def item_from_file(fname, cfg):
    """'cold_coffee_2.jpg' → 'Cold Coffee' (menu me sabse lamba match)."""
    f = os.path.basename(fname).lower()
    best = None
    for m in cfg.get("menu", []):
        if f.startswith(slug(m["name"])) and (not best or len(m["name"]) > len(best)):
            best = m["name"]
    return best or re.sub(r"_\d+.*$", "", os.path.splitext(f)[0]).replace("_", " ").title()


def _gate(im, name, cfg, source):
    """AI Auditor: sirf HD, sharp, sahi dish, bina watermark wali tasty photo hi library me aaye."""
    if not cfg.get("audit", {}).get("photos", True):
        return True, {}
    from . import audit
    ok, rep = audit.photo_check(im, name, cfg, source)
    if not ok:
        print(f"Auditor ne {source} photo reject ki ({name}):", rep.get("issues") or rep.get("problems"))
    return ok, rep


def photos_for(name):
    s = slug(name)
    real = [p for p in glob.glob(os.path.join(REAL_DIR, "*")) if os.path.basename(p).lower().startswith(s)
            and p.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    if real:
        return sorted(real), "real"
    stock = sorted(glob.glob(os.path.join(STOCK_DIR, f"{s}_*.jpg")))
    ai = sorted(glob.glob(os.path.join(AI_DIR, f"{s}_*.jpg")))
    if stock:
        return stock + ai, "stock"
    return ai, "ai" if ai else None


def fetch_stock(name, cfg, n=5):
    """Pexels (free for commercial use) se HD food photos. Ek item ke liye sirf ek baar search hota hai."""
    if os.environ.get("PIXABAY_API_KEY", "").strip():
        return fetch_pixabay(name, cfg, n)
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key and "_nokey" not in _DEAD:
        _DEAD.add("_nokey")
        print("⚠️ PIXABAY_API_KEY nahi mila — stock photos skip. (GitHub Secret ka naam check karo, aur workflow file me "
              "'PIXABAY_API_KEY: ${{ secrets.PIXABAY_API_KEY }}' line honi chahiye.)")
    s = slug(name)
    marker = os.path.join(STOCK_DIR, f".done_{s}")
    queries = {**STOCK_QUERY, **{k.lower(): v for k, v in (cfg.get("photos", {}).get("stock_queries") or {}).items()}}
    q = queries.get(name.lower(), name)
    if not key or not q or os.path.exists(marker) or "pexels" in _DEAD:
        return 0
    os.makedirs(STOCK_DIR, exist_ok=True)
    # same query wale items (jaise 3 momos) ko alag photos mile
    same = [k for k, v in queries.items() if v == q]
    offset = same.index(name.lower()) * n if name.lower() in same else 0
    try:
        r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": key},
                         params={"query": q, "per_page": 40, "orientation": "square", "size": "large"}, timeout=40)
        if r.status_code == 401:
            print("Pexels: API key galat hai (401)")
            _DEAD.add("pexels")
            return 0
        r.raise_for_status()
        photos = [p for p in r.json().get("photos", []) if min(p.get("width", 0), p.get("height", 0)) >= 1000]
    except Exception as e:
        print("Pexels failed:", str(e)[:200])
        return 0
    picked = (photos[offset:] + photos[:offset])[:n * 3]
    made = 0
    for i, p in enumerate(picked, 1):
        if made >= n:
            break
        try:
            img = requests.get(p["src"].get("original") or p["src"]["large2x"], timeout=90).content
            im = Image.open(io.BytesIO(img)).convert("RGB")
            sz = min(im.size)
            im = im.crop(((im.width - sz) // 2, (im.height - sz) // 2, (im.width + sz) // 2, (im.height + sz) // 2))
            if sz > 2048:
                im = im.resize((2048, 2048), Image.LANCZOS)  # HD rakho (full-screen layouts ke liye)
            ok, arep = _gate(im, name, cfg, "stock")
            if not ok:
                continue
            path = os.path.join(STOCK_DIR, f"{s}_{made + 1}.jpg")
            im.save(path, quality=92)
            _credit(name, path, p)
            if arep:
                from . import audit
                audit.remember_photo(path, True, arep)
            made += 1
        except Exception as e:
            print("Pexels download failed:", str(e)[:150])
    open(marker, "w").write(q)
    print(f"Pexels: {name} → {made} photos ('{q}')")
    return made


def fetch_pixabay(name, cfg, n=5):
    """Pixabay (free, commercial use OK) — ek item ke liye ek hi search, photos download karke repo me."""
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    s = slug(name)
    marker = os.path.join(STOCK_DIR, f".done_{s}")
    queries = {**STOCK_QUERY, **{k.lower(): v for k, v in (cfg.get("photos", {}).get("stock_queries") or {}).items()}}
    q = queries.get(name.lower(), name)
    if not key or not q or os.path.exists(marker) or "pixabay" in _DEAD:
        return 0
    os.makedirs(STOCK_DIR, exist_ok=True)
    same = [k for k, v in queries.items() if v == q]
    offset = same.index(name.lower()) * n if name.lower() in same else 0
    try:
        r = requests.get("https://pixabay.com/api/", params={"key": key, "q": q[:100], "image_type": "photo",
                                                             "category": "food", "min_width": 1600, "min_height": 1200, "per_page": 60,
                                                             "safesearch": "true", "order": "popular"}, timeout=40)
        if r.status_code in (400, 401, 403):
            print("Pixabay key problem:", r.text[:120])
            _DEAD.add("pixabay")
            return 0
        r.raise_for_status()
        hits = r.json().get("hits", [])
    except Exception as e:
        print("Pixabay failed:", str(e)[:200])
        return 0
    picked = (hits[offset:] + hits[:offset])[:n * 3]  # reject hone pe agli photo try
    made = 0
    for i, h in enumerate(picked, 1):
        if made >= n:
            break
        try:
            # sabse badi available size (fullHD/original sirf full-access keys pe aati hai, warna 1280px large)
            src = h.get("imageURL") or h.get("fullHDURL") or h.get("largeImageURL") or h["webformatURL"]
            img = requests.get(src, timeout=90).content
            im = Image.open(io.BytesIO(img)).convert("RGB")
            sz = min(im.size)
            im = im.crop(((im.width - sz) // 2, (im.height - sz) // 2, (im.width + sz) // 2, (im.height + sz) // 2))
            if sz > 2048:
                im = im.resize((2048, 2048), Image.LANCZOS)
            ok, arep = _gate(im, name, cfg, "stock")
            if not ok:
                continue
            path = os.path.join(STOCK_DIR, f"{s}_{made + 1}.jpg")
            im.save(path, quality=93)
            _credit(name, path, {"photographer": h.get("user", ""), "url": h.get("pageURL", "")})
            if arep:
                from . import audit
                audit.remember_photo(path, True, arep)
            made += 1
        except Exception as e:
            print("Pixabay download failed:", str(e)[:150])
    open(marker, "w").write(q)
    print(f"Pixabay: {name} → {made} photos ('{q}')")
    return made


BG_VID_DIR = os.path.join(ROOT, "assets", "bg_videos")
BG_VIDEO_QUERIES = ["coffee steam", "tea pouring", "cafe bokeh lights", "coffee beans falling", "smoke dark background",
                    "golden particles", "rain window", "latte art"]


def fetch_bg_videos(max_new=4):
    """Pixabay se mood wale background videos (chai steam, cafe bokeh...). Sirf mahaul ke liye, khana nahi."""
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key:
        return 0
    os.makedirs(BG_VID_DIR, exist_ok=True)
    made = 0
    for q in BG_VIDEO_QUERIES:
        if made >= max_new:
            break
        marker = os.path.join(BG_VID_DIR, f".done_{slug(q)}")
        if os.path.exists(marker):
            continue
        try:
            r = requests.get("https://pixabay.com/api/videos/", params={"key": key, "q": q, "per_page": 5,
                                                                        "safesearch": "true"}, timeout=40)
            r.raise_for_status()
            for h in r.json().get("hits", [])[:1]:
                v = h["videos"].get("medium") or h["videos"].get("small")
                if not v or not v.get("url"):
                    continue
                data = requests.get(v["url"], timeout=120).content
                with open(os.path.join(BG_VID_DIR, f"{slug(q)}.mp4"), "wb") as fh:
                    fh.write(data)
                _credit("bg video: " + q, os.path.join(BG_VID_DIR, f"{slug(q)}.mp4"),
                        {"photographer": h.get("user", ""), "url": h.get("pageURL", "")})
                made += 1
            open(marker, "w").write(q)
        except Exception as e:
            print("Pixabay video failed:", str(e)[:150])
    return made


def _credit(name, path, p):
    import csv
    os.makedirs(os.path.dirname(CREDITS), exist_ok=True)
    new = not os.path.exists(CREDITS)
    with open(CREDITS, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["item", "file", "photographer", "pexels_url"])
        w.writerow([name, os.path.relpath(path, ROOT), p.get("photographer", ""), p.get("url", "")])


_DEAD = set()  # is run me jo service fail ho chuki, use dobara try nahi karte


def _cf_clean(acc_raw, tok_raw):
    """Secrets me galti se extra lines / 'Bearer' / curl text aa jaye to bhi asli ID aur token nikaal lo."""
    import re
    acc_raw, tok_raw = acc_raw or "", tok_raw or ""
    ids = re.findall(r"\b[0-9a-f]{32}\b", acc_raw) or re.findall(r"[0-9a-f]{32}", acc_raw + " " + tok_raw)
    acc = ids[0] if ids else acc_raw.strip()
    words = [w for w in re.findall(r"[A-Za-z0-9_\-]{30,}", tok_raw) if w != acc and not re.fullmatch(r"[0-9a-f]{32}", w)]
    tok = (sorted(words, key=lambda w: (len(w) != 40, -len(w)))[0] if words else tok_raw.strip())
    if "_cf_logged" not in _DEAD:
        _DEAD.add("_cf_logged")
        print(f"Cloudflare secrets check: account_id lines={len(acc_raw.splitlines())} ok={bool(ids)}, "
              f"token lines={len(tok_raw.splitlines())} picked_length={len(tok)}")
    return acc, tok


def _cloudflare(prompt, cfg):
    """Cloudflare Workers AI (FLUX schnell) — free ~170 images/day. Needs CF_ACCOUNT_ID + CF_API_TOKEN."""
    acc, tok = _cf_clean(os.environ.get("CF_ACCOUNT_ID"), os.environ.get("CF_API_TOKEN"))
    if not acc or not tok or "cf" in _DEAD:
        return None
    url = f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    try:
        r = requests.post(url, headers={"Authorization": f"Bearer {tok}"},
                          json={"prompt": prompt[:2000], "steps": 8}, timeout=180)
        r.raise_for_status()
        img = (r.json().get("result") or {}).get("image")
        if img:
            return base64.b64decode(img)
        print("Cloudflare: no image in response", r.text[:300])
    except Exception as e:
        print("Cloudflare failed:", str(e)[:300])
        _DEAD.add("cf")
    return None


def _gemini_image(prompt, cfg):
    key = os.environ.get("GEMINI_API_KEY")
    if not key or "gemini" in _DEAD:
        return None
    model = cfg.get("ai", {}).get("image_model", "gemini-2.5-flash-image")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "1:1"}}}
    try:
        r = requests.post(url, params={"key": key}, json=body, timeout=180)
        r.raise_for_status()
        for part in r.json()["candidates"][0]["content"]["parts"]:
            data = (part.get("inlineData") or part.get("inline_data") or {}).get("data")
            if data:
                return base64.b64decode(data)
        print("Gemini image: no image in response")
    except Exception as e:
        print("Gemini image failed:", str(e)[:300])
        _DEAD.add("gemini")
    return None


def _pollinations(prompt, cfg):
    key = os.environ.get("POLLINATIONS_KEY")
    if not key or "poll" in _DEAD:
        return None
    url = "https://gen.pollinations.ai/image/" + urllib.parse.quote(prompt)
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    try:
        r = requests.get(url, params={"model": "flux", "width": 1024, "height": 1024, "nologo": "true"},
                         headers=headers, timeout=180)
        r.raise_for_status()
        if r.headers.get("content-type", "").startswith("image"):
            return r.content
        print("Pollinations: not an image")
    except Exception as e:
        print("Pollinations failed:", str(e)[:300])
        _DEAD.add("poll")
    return None


def generate_one(name, cfg, variant):
    dish = DISH.get(name.lower(), f"{name} as served in a modern Indian cafe")
    angles = [" Hero shot at 45 degrees, steam or melting texture visible, extremely appetizing.",
              " Macro close-up showing texture and freshness, shallow depth of field.",
              " Top-down flat lay on a dark wooden table with a few ingredients around.",
              " Side angle on a dark ceramic plate with a gold rim, warm cosy cafe light.",
              " Served with a kulhad of chai in the background, soft bokeh."]
    prompt = STYLE.format(dish=dish) + angles[variant % len(angles)]
    raw = _cloudflare(prompt, cfg) or _gemini_image(prompt, cfg) or _pollinations(prompt, cfg)
    if not raw:
        return None
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    s = min(im.size)
    im = im.crop(((im.width - s) // 2, (im.height - s) // 2, (im.width + s) // 2, (im.height + s) // 2))
    im = im.resize((1024, 1024), Image.LANCZOS)
    ok, arep = _gate(im, name, cfg, "ai")
    if not ok:
        return None
    os.makedirs(AI_DIR, exist_ok=True)
    path = os.path.join(AI_DIR, f"{slug(name)}_{variant + 1}.jpg")
    im.save(path, quality=92)
    if arep:
        from . import audit
        audit.remember_photo(path, True, arep)
    print("AI photo saved:", os.path.relpath(path, ROOT))
    return path


def ensure_photos(names, cfg, per_item=None, max_new=None):
    """Make sure every item has enough AI photos. Only generates what's missing."""
    pc = cfg.get("photos", {})
    if not pc.get("ai_photos", True):
        return 0
    per_item = per_item or pc.get("variants_per_item", 3)
    max_new = pc.get("max_new_per_run", 12) if max_new is None else max_new
    made = 0
    for name in dict.fromkeys(names):  # unique, keep order
        files, kind = photos_for(name)
        if kind == "real":
            continue
        made += fetch_stock(name, cfg, pc.get("stock_per_item", 5))
        files, kind = photos_for(name)
        for _ in range(per_item - len(files)):
            if made >= max_new:
                return made
            n_ai = len(glob.glob(os.path.join(AI_DIR, f"{slug(name)}_*.jpg")))
            if not (generate_one(name, cfg, n_ai) or (not _DEAD & {"cf"} and generate_one(name, cfg, n_ai + 1))):
                break  # AI band / 2 baar reject → agla item (stock wale items phir bhi aate rahein)
            made += 1
    return made


# ---------------------------------------------------------------- cut-outs + no-repeat usage
CUT_DIR = os.path.join(ROOT, "assets", "cutouts")
USAGE = os.path.join(ROOT, "data", "photo_usage.json")
_SESSION = {}


def cutout(path):
    """Background hata ke sirf dish (PNG with alpha). Cache assets/cutouts/ me. Na bane to None."""
    import hashlib
    key = hashlib.md5((path + str(os.path.getmtime(path)) + "v2").encode()).hexdigest()[:10]
    out = os.path.join(CUT_DIR, f"{os.path.splitext(os.path.basename(path))[0]}_{key}.png")
    if os.path.exists(out):
        return Image.open(out).convert("RGBA")
    try:
        from rembg import new_session, remove
        if "s" not in _SESSION:
            _SESSION["s"] = new_session("u2netp")
        im = Image.open(path).convert("RGB")
        im.thumbnail((1400, 1400))
        cut = remove(im, session=_SESSION["s"])
    except Exception as e:
        print("cutout failed:", str(e)[:120])
        return None
    cut = _clean_alpha(cut)
    a = cut.getchannel("A")
    bbox = a.point(lambda v: 255 if v > 40 else 0).getbbox()
    if not bbox:
        return None
    cover = sum(a.histogram()[128:]) / (a.width * a.height)
    if cover < 0.06:  # dish pehchani nahi gayi
        return None
    cut = cut.crop(bbox)
    os.makedirs(CUT_DIR, exist_ok=True)
    cut.save(out)
    return cut


def _clean_alpha(cut):
    """Background removal ki galtiyan theek karo:
    - glass / transparent hisse ke andar ke 'chhed' bhar do (cold coffee ka beech gayab na ho)
    - andar ka hissa poora solid, sirf kinare soft
    - chhote bikhre tukde (leftover background) hata do"""
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
    soft = np.where(filled, a, 0)  # kept components ke bahar sab saaf
    near = nd.binary_dilation(filled, iterations=3)
    soft = np.where(near & ~filled, a * 0.6, soft)  # kinare ka halka feather rehne do
    out = np.where(inner, 255, np.maximum(soft, np.where(filled, 200, 0)))
    res = cut.copy()
    res.putalpha(Image.fromarray(np.clip(out, 0, 255).astype("uint8")))
    return res


def _load_usage():
    import json
    try:
        with open(USAGE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def pick_photo(name, mode="image", seed="", today=None):
    """Repeat se bachao: image posts me main photo 21 din tak dobara nahi; reels me ek photo max 3 baar."""
    import datetime as _dt
    import random as _r
    files, kind = photos_for(name)
    if not files:
        return None, None
    u = _load_usage()
    today = today or _dt.date.today()
    rel = lambda p: os.path.relpath(p, ROOT)

    def score(p):
        rec = u.get(rel(p), {})
        last = rec.get("last_main")
        recent = last and (today - _dt.date.fromisoformat(last)).days < 21
        return ((mode == "image" and recent), (mode == "reel" and rec.get("reel", 0) >= 3),
                rec.get("main", 0) + rec.get("reel", 0), _r.Random(f"{seed}{p}").random())
    best = sorted(files, key=score)[0]
    return best, kind


def record_use(paths, mode, today):
    import json
    u = _load_usage()
    for p in set(paths):
        rec = u.setdefault(os.path.relpath(p, ROOT), {})
        if mode == "image":
            rec["main"] = rec.get("main", 0) + 1
            rec["last_main"] = today.isoformat()
        else:
            rec["reel"] = rec.get("reel", 0) + 1
    os.makedirs(os.path.dirname(USAGE), exist_ok=True)
    with open(USAGE, "w", encoding="utf-8") as fh:
        json.dump(u, fh, indent=1)
