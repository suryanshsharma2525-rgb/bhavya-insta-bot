"""AI food photo library.

Har menu item ki realistic food photos AI se banti hain aur assets/photos_ai/ me save ho jaati hain
(ek baar banti hain, phir har post me reuse hoti hain — isliye free limit me aaram se chalta hai).
Priority: assets/photos (tumhari asli photos) → assets/photos_ai (AI photos) → emoji.
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

# Indian-cafe style descriptions so the AI makes the right dish
DISH = {
    "aloo tikki burger": "an Indian aloo tikki burger: crispy spiced potato patty, onion, tomato, lettuce and mint mayo in a soft sesame bun",
    "tandoori burger": "a tandoori burger: smoky tandoori-masala crispy patty with onion rings, lettuce and tandoori mayo in a toasted bun",
    "cheese burger": "a veg cheese burger with crispy patty and a thick melting cheese slice dripping over, lettuce, tomato, sesame bun",
    "vada pav": "Mumbai-style vada pav: golden fried potato vada inside a soft pav with green chutney and red garlic chutney, one fried green chilli on the side",
    "cheese burst samosa": "two golden crispy samosas, one broken open showing a molten stretchy cheese and spiced potato filling, green chutney on the side",
    "bun makkhan": "Indian bun makkhan: a soft round sweet bun sliced open and thickly loaded with white butter, served with a kulhad of chai",
    "potato twister": "a spiral potato twister (tornado potato) on a long wooden skewer, golden and crispy, dusted with peri-peri masala",
    "simple chips chaat": "Indian chips chaat: potato chips topped with chopped onion, tomato, sev, green and tamarind chutney and coriander, in a paper bowl",
    "corn chips chaat": "corn chips chaat: crunchy corn chips topped with sweet corn, onion, tomato, chutneys, sev and coriander, in a bowl",
    "loaded chips chaat": "loaded chips chaat: chips heavily loaded with cheese sauce, sweet corn, onion, tomato, chutneys, sev, curd and coriander",
    "nachos chaat": "Indian nachos chaat: tortilla nachos topped with salsa, cheese sauce, onion, tomato, jalapeno, sev and chutneys in a black bowl",
    "kulhad pizza": "kulhad pizza: pizza baked inside a clay kulhad cup, overflowing with melted bubbling cheese, capsicum, corn, olives and oregano",
    "veg momos": "8 steamed veg momos (dumplings) in a bamboo steamer with spicy red momo chutney in a small bowl, steam rising",
    "paneer momos": "8 steamed paneer momos, one cut open showing the paneer filling, with red chutney, on a dark plate",
    "cheese sweet corn momos": "8 steamed cheese sweet corn momos, one cut open with stretchy cheese and corn filling, with red chutney",
    "peshawari khewani kheer": "Peshawari khewani kheer in a clay kulhad bowl, creamy with vermicelli, dry fruits, pistachio and almond slivers",
    "kesar pista kheer": "kesar pista kheer in a clay bowl, saffron yellow-cream colour, topped with chopped pistachios and saffron strands",
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


def photos_for(name):
    s = slug(name)
    real = [p for p in glob.glob(os.path.join(REAL_DIR, "*")) if os.path.basename(p).lower().startswith(s)
            and p.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    if real:
        return sorted(real), "real"
    ai = sorted(glob.glob(os.path.join(AI_DIR, f"{s}_*.jpg")))
    return ai, "ai" if ai else None


def _gemini_image(prompt, cfg):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
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
    return None


def _pollinations(prompt, cfg):
    key = os.environ.get("POLLINATIONS_KEY")
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
    return None


def generate_one(name, cfg, variant):
    dish = DISH.get(name.lower(), f"{name} as served in a modern Indian cafe")
    angles = ["", " Close-up hero shot.", " 45-degree angle, a few ingredients scattered around.",
              " Top-down flat lay.", " Served on a dark ceramic plate with a gold rim."]
    prompt = STYLE.format(dish=dish) + angles[variant % len(angles)]
    raw = _gemini_image(prompt, cfg) or _pollinations(prompt, cfg)
    if not raw:
        return None
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    s = min(im.size)
    im = im.crop(((im.width - s) // 2, (im.height - s) // 2, (im.width + s) // 2, (im.height + s) // 2))
    im = im.resize((1024, 1024), Image.LANCZOS)
    os.makedirs(AI_DIR, exist_ok=True)
    path = os.path.join(AI_DIR, f"{slug(name)}_{variant + 1}.jpg")
    im.save(path, quality=92)
    print("AI photo saved:", os.path.relpath(path, ROOT))
    return path


def ensure_photos(names, cfg, per_item=None, max_new=None):
    """Make sure every item has enough AI photos. Only generates what's missing."""
    pc = cfg.get("photos", {})
    if not pc.get("ai_photos", True):
        return
    per_item = per_item or pc.get("variants_per_item", 3)
    max_new = pc.get("max_new_per_run", 12) if max_new is None else max_new
    made = 0
    for name in dict.fromkeys(names):  # unique, keep order
        files, kind = photos_for(name)
        if kind == "real":
            continue
        for v in range(len(files), per_item):
            if made >= max_new:
                return
            if not generate_one(name, cfg, v):
                return  # API down / quota over → emoji fallback today, try again tomorrow
            made += 1
