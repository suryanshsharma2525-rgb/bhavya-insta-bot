"""Pinterest design → Bhavya Cafe ki post + reel (usi design, rang, font me).

  python -m pin.main make  [--type both|image|reel] [--idea ".."] [--item ".."]   # inbox/ ki Pinterest images se
  python -m pin.main idea  --idea "Baarish me garma garam chai" [--item ..] [--type ..] [--style latest|random|ID]
  python -m pin.main daily                                                      # roz: calendar ka idea + saved design
  python -m pin.main publish --dir "NAME1 NAME2"
"""
import argparse
import datetime as dt
import glob
import json
import os
import random
import re

import yaml
from PIL import Image

from . import photos, presets, render, vision

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INBOX = os.path.join(ROOT, "inbox")
OUT = os.path.join(ROOT, "posts", "pin")
STYLES = os.path.join(ROOT, "data", "styles")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

FOOD_WORDS = {  # reference ke khane → hamare menu ka kareebi item
    "burger": ["Aloo Tikki Burger", "Tandoori Burger", "Cheese Burger", "Vada Pav"],
    "sandwich": ["Vada Pav", "Bun Makkhan"], "pav": ["Vada Pav"], "bun": ["Bun Makkhan"],
    "samosa": ["Cheese Burst Samosa"], "pizza": ["Kulhad Pizza"], "momo": ["Veg Momos", "Paneer Momos", "Cheese Sweet Corn Momos"],
    "dumpling": ["Veg Momos", "Paneer Momos"], "fries": ["Potato Twister", "Simple Chips Chaat"],
    "potato": ["Potato Twister"], "chips": ["Simple Chips Chaat", "Loaded Chips Chaat"], "nacho": ["Nachos Chaat"],
    "chaat": ["Corn Chips Chaat", "Loaded Chips Chaat"], "kheer": ["Kesar Pista Kheer", "Peshawari Khewani Kheer"],
    "pudding": ["Butterscotch Kheer", "Kesar Pista Kheer"], "dessert": ["Kesar Pista Kheer", "Butterscotch Kheer"],
    "tea": ["Kulhad Chai"], "chai": ["Kulhad Chai"], "latte": ["Cold Coffee", "Hot Coffee"], "coffee": ["Cold Coffee", "Hot Coffee"],
    "iced": ["Cold Coffee"], "frappe": ["Cold Coffee", "Mocha Shake"], "shake": ["Mocha Shake", "Matcha Shake"],
    "smoothie": ["Matcha Shake", "Mocha Shake"], "matcha": ["Matcha Shake"], "chocolate": ["Mocha Shake"],
    "lemonade": ["Cold Coffee", "Matcha Shake"], "drink": ["Cold Coffee", "Mocha Shake"], "juice": ["Matcha Shake"],
}


def load_cfg():
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _menu_item(name, cfg):
    s = photos.slug(name or "")
    if not s:
        return None
    for m in sorted(cfg["menu"], key=lambda m: -len(m["name"])):
        ms = photos.slug(m["name"])
        if s.startswith(ms) or ms.startswith(s) or ms in s:
            return m["name"]
    return None


def choose_item(hint, food, cfg, idea=""):
    have = photos.items_with_photos(cfg["menu"])
    if not have:
        raise SystemExit("❌ assets/photos/ me ek bhi photo nahi hai. Pehle apni asli photos daalo "
                         "(naam item ke naam se, jaise cold_coffee_1.jpg).")
    for src in (hint, idea):  # file ka naam / idea me item ka naam
        it = None
        if src:
            for m in sorted(cfg["menu"], key=lambda m: -len(m["name"])):
                if m["name"].lower() in src.lower() or photos.slug(src).startswith(photos.slug(m["name"])):
                    it = m["name"]
                    break
        if it:
            if it in have:
                return it
            print(f"⚠️ '{it}' ki asli photo assets/photos me nahi hai — doosra item le rahe hain.")
    f = f"{food or ''} {idea or ''}".lower()
    for w, items in FOOD_WORDS.items():
        if w in f:
            for it in items:
                if it in have:
                    return it
    u = photos._usage()
    return sorted(have, key=lambda it: max((u.get(os.path.basename(p), "") for p in have[it]), default=""))[0]


def caption_text(cap, tags, item, cfg):
    cap = (cap or f"{item}, made fresh at Bhavya Cafe.\nCome hungry, leave happy.").strip()
    tags = [t if t.startswith("#") else "#" + t for t in (tags or [])][:5] or \
        ["#Roorkee", "#IITRoorkee", "#RoorkeeFood", "#BhavyaCafe", "#" + re.sub(r"\W", "", item)]
    return (f"{cap}\n\n{cfg['brand']['location_line']}\nCafe in Roorkee · Near IIT Roorkee · {item} in Roorkee\n\n"
            + " ".join(tags[:5]))


def _offer_badge(spec, offer):
    """Offer/combo ka badge — design ke hi rang me, sabse khaali jagah pe (offer hamesha bada aur saaf dikhe)."""
    spec["elements"] = [e for e in spec["elements"] if e.get("id") != "offer_badge"]
    short = offer.split(" · ")[0].strip()[:42]
    if not short:
        return
    busy = [e["box"] for e in spec["elements"] if e["type"] in ("text", "photo", "icon")]
    cands = [[0.10, 0.865, 0.90, 0.945], [0.10, 0.045, 0.90, 0.125], [0.52, 0.60, 0.96, 0.68], [0.04, 0.60, 0.48, 0.68],
             [0.20, 0.76, 0.80, 0.84]]

    def ov(a, b):
        return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    box = min(cands, key=lambda c: sum(ov(c, b) for b in busy))
    texts = [e for e in spec["elements"] if e["type"] == "text"]
    accent = max(texts, key=lambda e: (e["box"][3] - e["box"][1]) * (e["box"][2] - e["box"][0]))["color"] if texts else "#7c1c12"
    bg = (spec.get("background", {}).get("colors") or ["#ffffff"])[0]
    spec["elements"].append({"id": "offer_badge", "type": "text", "role": "offer", "box": box, "text": short,
                             "font_name": "Montserrat", "font_category": "sans_bold", "weight": "extrabold",
                             "uppercase": True, "color": bg, "pill": accent, "align": "center", "lines": 1, "z": 99})


_KEEP = {"headline": 0, "giant_word": 0, "item_name": 1, "offer": 1, "price": 2, "cta": 2, "subheadline": 3, "tagline": 3, "brand": 3, "location": 4, "handle": 4}


def _declutter(spec, maxn=7):
    """Bahut saare chhote doodle-labels (dusre items ke naam) post ko bhaara bana dete hain → sirf zaroori text rakho."""
    ts = [e for e in spec["elements"] if e["type"] == "text"]
    if len(ts) <= maxn:
        return
    def area(e):
        b = e["box"]
        return (b[2] - b[0]) * (b[3] - b[1])
    keep = sorted(ts, key=lambda e: (_KEEP.get(e.get("role"), 5), -area(e)))[:maxn]
    ids = {id(e) for e in keep}
    spec["elements"] = [e for e in spec["elements"] if e["type"] != "text" or id(e) in ids]
    print(f"Design me {len(ts)} text the → {maxn} zaroori rakhe (baaki hataye taaki saaf dikhe)")


def build(ref, spec, item, cfg, idea=None, compare=True, preset="auto", offer="", occasion=""):
    spec = json.loads(json.dumps(spec))  # saved design na badle
    _declutter(spec, int((cfg.get("pin") or {}).get("max_texts", 7)))
    plain = any(e["type"] == "photo" and e.get("style", "cutout") != "cutout" for e in spec["elements"])
    path = photos.pick(item, cfg["menu"], plain=plain)
    photo = photos.load(path)
    if plain and photos.is_dark(path):  # sirf kaale-bg wali photo hai → poori photo ki jagah saaf cutout
        for e in spec["elements"]:
            if e["type"] == "photo":
                e["style"] = "cutout"
    need_cut = any(e["type"] == "photo" and e.get("style", "cutout") == "cutout" for e in spec["elements"])
    cut = photos.cutout(path) if need_cut else None
    if need_cut and cut is None:
        for e in spec["elements"]:
            if e["type"] == "photo" and e.get("style") == "cutout":
                e["style"] = "rounded"
    if preset == "offer" and not offer:
        offer = presets.weekly_offer_text(cfg, dt.datetime.now(IST).date())
    texts, cap, tags = vision.write_texts(spec, item, cfg, idea, presets.instruction(preset, cfg, offer, occasion))
    if preset in ("offer", "combo") and offer:
        _offer_badge(spec, offer)
        texts["offer_badge"] = offer.split(" · ")[0].strip()[:42]
    if preset in ("offer", "combo") and offer and cap and offer.lower() not in cap.lower():
        cap = f"{cap}\n\n🎁 {offer}"
    out = render.render(spec, texts, photo, cut)
    best = (0, out, None)
    if compare and ref is not None:
        rounds = int((cfg.get("design") or {}).get("fix_rounds", 2))
        for r in range(rounds + 1):
            d = vision.compare(ref, out, spec, cfg)
            if not d:
                print("Compare: AI busy — jo bana wahi rakha")
                best = max(best, (5, out, {"similarity": None}), key=lambda x: x[0])
                break
            sim = float(d.get("similarity") or 0) + (0.5 if d.get("quality_ok") else 0)
            print(f"Round {r + 1}: match {d.get('similarity')}/10, quality_ok={d.get('quality_ok')}, problems={d.get('problems')}")
            if sim > best[0]:
                best = (sim, out, d)
            if r == rounds or (d.get("similarity", 0) >= 9 and d.get("quality_ok")):
                break
            if not vision.apply_fixes(spec, d.get("fixes")):
                break
            out = render.render(spec, texts, photo, cut)
    else:
        best = (6, out, {"similarity": None, "quality_ok": True})
    photos.mark_used(path)
    d = best[2] or {}
    meta = {"item": item, "photo": os.path.basename(path), "caption": caption_text(cap, tags, item, cfg),
            "similarity": d.get("similarity"), "quality_ok": d.get("quality_ok"), "problems": d.get("problems"),
            "idea": idea, "mood": spec.get("mood"), "preset": preset, "offer": offer}
    return best[1], meta, (texts, photo, cut, spec)


def _save(spec, im, meta, parts, kind, cfg, style_id, seed):
    stamp = dt.datetime.now(IST).strftime("%Y-%m-%d_%H%M%S")
    base, n = stamp, 2
    while os.path.exists(os.path.join(OUT, stamp)):  # ek hi second me do posts → alag folder
        stamp, n = f"{base}_{n}", n + 1
    d = os.path.join(OUT, stamp)
    os.makedirs(d, exist_ok=True)
    im.save(os.path.join(d, "post.jpg"), quality=95, optimize=True)
    files = ["post.jpg"]
    if kind in ("reel", "both"):
        from . import reel
        texts, photo, cut, spec_used = parts
        _, music = reel.make(spec_used, texts, photo, cut, cfg, os.path.join(d, "reel.mp4"), seed=seed)
        files += ["reel.mp4", "reel_cover.jpg"]
        meta["music"] = music
    ok = (meta.get("similarity") is None or float(meta["similarity"]) >= (cfg.get("design") or {}).get("min_similarity", 5)) \
        and meta.get("quality_ok") is not False
    meta.update(status="ready" if ok else "review", style=style_id, made=stamp, files=files,
                publish="reel" if kind in ("reel", "both") else "image", date=dt.datetime.now(IST).date().isoformat())
    json.dump(meta, open(os.path.join(d, "post.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✅ posts/pin/{stamp}: {files}  status={meta['status']}")
    return stamp


def _strip(spec):
    s = json.loads(json.dumps(spec))
    for e in s["elements"]:
        if e.get("text"):
            e["ref_shape"] = render.ref_shape(e["text"])  # sirf aakaar (size/baseline ke liye), dusre brand ka text nahi
        e.pop("text", None)
    return s


def _out(names):
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a") as fh:
            fh.write(f"posts={' '.join(names)}\n")


def cmd_make(cfg, kind="both", idea=None, item=None, preset="auto", offer=""):
    refs = sorted(p for p in glob.glob(os.path.join(INBOX, "*")) if p.lower().endswith((".jpg", ".jpeg", ".png", ".webp")))
    if not refs:
        print("inbox/ me koi Pinterest image nahi hai.")
        _out([])
        return []
    made = []
    for ref_path in refs:
        print(f"\n=== {os.path.basename(ref_path)} ===")
        ref = Image.open(ref_path).convert("RGB")
        spec = vision.analyze(ref, cfg)
        if not spec:
            print("❌ Design padh nahi paaye (Gemini busy). Image inbox me hi hai — agli baar dobara try hoga.")
            continue
        spec = vision.sample_colors(spec, ref)
        spec = vision.reframe(spec, ref.size)
        it = choose_item(item or os.path.basename(ref_path), spec.get("food"), cfg, idea or "")
        print("Item:", it, "| reference food:", spec.get("food"), "| mood:", spec.get("mood"))
        im, meta, parts = build(ref, spec, it, cfg, idea, preset=preset, offer=offer)
        style_id = dt.datetime.now(IST).strftime("%Y%m%d_%H%M%S")
        os.makedirs(STYLES, exist_ok=True)
        json.dump(_strip(spec), open(os.path.join(STYLES, f"{style_id}.json"), "w", encoding="utf-8"), indent=1)
        made.append(_save(spec, im, meta, parts, kind, cfg, style_id, seed=style_id))
        os.remove(ref_path)  # public repo — dusre brand ki image nahi rakhni
    _out(made)
    return made


def _styles():
    return sorted(glob.glob(os.path.join(STYLES, "*.json")))


def pick_style(style="latest", seed=""):
    files = _styles()
    if not files:
        raise SystemExit("Abhi koi saved design nahi hai — pehle inbox/ me ek Pinterest image daalo.")
    if style in (None, "", "latest"):
        return files[-1]
    if style == "random":
        used = {}
        for pj in glob.glob(os.path.join(OUT, "*", "post.json")):
            try:
                m = json.load(open(pj, encoding="utf-8"))
                used[m.get("style")] = max(used.get(m.get("style"), ""), m.get("made", ""))
            except Exception:
                pass
        # jo design sabse pehle use hua tha (ya kabhi nahi) wo aaj — har design baari-baari
        return sorted(files, key=lambda f: (used.get(os.path.basename(f)[:-5], ""), random.Random(seed + f).random()))[0]
    p = os.path.join(STYLES, f"{style}.json")
    return p if os.path.exists(p) else files[-1]


def cmd_idea(cfg, idea, item=None, kind="both", style="latest", seed="", preset="auto", offer="", occasion=""):
    f = pick_style(style, seed or idea or "")
    spec = json.load(open(f, encoding="utf-8"))
    it = choose_item(item or "", "", cfg, idea or "")
    print(f"Design: {os.path.basename(f)} | Item: {it} | Idea: {idea}")
    im, meta, parts = build(None, spec, it, cfg, idea, compare=False, preset=preset, offer=offer, occasion=occasion)
    name = _save(spec, im, meta, parts, kind, cfg, os.path.basename(f)[:-5], seed=f"{it}{idea}")
    _out([name])
    return name


def cmd_daily(cfg):
    """Roz: calendar ki aaj ki row (idea, item, reel/post, preset, offer) + baari-baari saved Pinterest design."""
    from . import plan
    today = dt.datetime.now(IST).date()
    if not _styles() or not photos.items_with_photos(cfg["menu"]):
        print("⏸ Daily post skip: pehle assets/photos me asli photos aur inbox/ me kam se kam ek Pinterest design daalo.")
        _out([])
        return None
    tp = plan.today(cfg, today)
    print("Aaj ka plan:", {k: tp.get(k) for k in ("type", "preset", "featured_item", "idea", "offer", "occasion")})
    kind = tp.get("type") if tp.get("type") in ("reel", "image", "both") else "reel"
    return cmd_idea(cfg, tp.get("idea") or "", tp.get("featured_item"), kind, "random", seed=today.isoformat(),
                    preset=tp.get("preset") or "auto", offer=tp.get("offer") or "", occasion=tp.get("occasion") or "")


# ---------------------------------------------------------------- stories (isi design system se, 9:16)
STORY_SLOTS = {"lunch": ("visit_now", "Aaj ka special, dopahar ka break"), "night": ("late_night", "Raat ki cravings")}


def cmd_story(cfg, slot="lunch"):
    from . import plan
    today = dt.datetime.now(IST).date()
    if not _styles() or not photos.items_with_photos(cfg["menu"]):
        print("⏸ Story skip: photos/design nahi hai.")
        return None
    tp = plan.today(cfg, today)
    preset, idea = STORY_SLOTS.get(slot, STORY_SLOTS["lunch"])
    if tp.get("preset") == "offer" and slot == "lunch":
        preset, idea = "offer", "Offer reminder"
    f = pick_style("random", f"story{today}{slot}")
    spec = json.load(open(f, encoding="utf-8"))
    item = tp.get("featured_item") if slot == "night" else None
    it = choose_item(item or "", "", cfg, "")
    _, meta, (texts, photo, cut, spec) = build(None, spec, it, cfg, idea, compare=False, preset=preset,
                                         offer=tp.get("offer") or "", occasion=tp.get("occasion") or "")
    s9 = render.expand_to(spec)
    old = (render.W, render.H)
    render.set_size(1080, 1920)
    try:
        im = render.render(s9, texts, photo, cut)
    finally:
        render.set_size(*old)
    d = os.path.join(OUT, "stories", f"{today.isoformat()}_{slot}")
    os.makedirs(d, exist_ok=True)
    im.save(os.path.join(d, "story.jpg"), quality=94)
    json.dump({"item": it, "preset": preset, "published": False}, open(os.path.join(d, "story.json"), "w"), indent=1)
    print(f"✅ Story: posts/pin/stories/{today.isoformat()}_{slot}/story.jpg ({it}, {preset})")
    return d


def cmd_publish_story(cfg, slot="lunch"):
    from bot.instagram import IG
    today = dt.datetime.now(IST).date()
    name = f"{today.isoformat()}_{slot}"
    d = os.path.join(OUT, "stories", name)
    pj = os.path.join(d, "story.json")
    if not os.path.exists(pj):
        print("Koi story nahi bani.")
        return
    meta = json.load(open(pj))
    if meta.get("published"):
        return
    repo = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    IG(cfg).post_story(image_url=f"https://raw.githubusercontent.com/{repo}/{branch}/posts/pin/stories/{name}/story.jpg")
    meta["published"] = True
    json.dump(meta, open(pj, "w"), indent=1)


def cmd_publish(cfg, names):
    from bot.instagram import IG
    import subprocess
    repo = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    except Exception:
        sha = ""
    ref = sha or branch
    ig = None
    for name in names:
        pj = os.path.join(OUT, name, "post.json")
        if not os.path.exists(pj):
            continue
        meta = json.load(open(pj, encoding="utf-8"))
        if meta.get("permalink"):
            print("Pehle hi post ho chuka:", meta["permalink"])
            continue
        if meta.get("status") != "ready":
            print(f"⏸ {name}: design reference se kam match hua ({meta.get('similarity')}/10) ya quality issue "
                  f"({meta.get('problems')}) — Instagram pe nahi daala. posts/pin/{name}/ dekh lo.")
            continue
        ig = ig or IG(cfg)
        base = f"https://raw.githubusercontent.com/{repo}/{ref}/posts/pin/{name}"
        if meta.get("publish") == "reel" and "reel.mp4" in meta.get("files", []):
            vids = [f"https://cdn.jsdelivr.net/gh/{repo}@{ref}/posts/pin/{name}/reel.mp4", f"{base}/reel.mp4"]
            link = ig.post_reel(vids, meta["caption"], cover_url=f"{base}/reel_cover.jpg")
        else:
            link = ig.post_image(f"{base}/post.jpg", meta["caption"], f"{meta['item']} at Bhavya Cafe near IIT Roorkee")
        meta.update(permalink=link, media_id=getattr(ig, "last_media_id", None))
        json.dump(meta, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        try:  # purana upload log + calendar me bhi
            from bot import calendar_plan
            lm = {"date": meta["date"], "format": "pinterest_design", "kind": meta["publish"], "featured_item": meta["item"],
                  "headline": meta.get("idea") or meta["item"], "caption": meta["caption"]}
            calendar_plan.log_post("pin_" + name, lm, "pinterest", "posted", link)
            calendar_plan.mark_posted(meta["date"], link)
        except Exception as e:
            print("log skip:", e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["make", "idea", "daily", "publish", "plan", "story", "publish-story", "housekeeping"])
    ap.add_argument("--dir", default="")
    ap.add_argument("--item", default="")
    ap.add_argument("--idea", default="")
    ap.add_argument("--type", default="both", help="both | image | reel")
    ap.add_argument("--style", default="latest", help="latest | random | style id")
    ap.add_argument("--preset", default="auto", help="auto | offer | combo | visit_now | new_item | weekend | rainy | exam | festival | late_night")
    ap.add_argument("--offer", default="", help="offer / combo ka text (aapka likha, jaisa hai waisa)")
    ap.add_argument("--slot", default="lunch")
    a = ap.parse_args()
    cfg = load_cfg()
    kind = a.type if a.type in ("both", "image", "reel") else "both"
    preset = a.preset if a.preset in presets.PRESETS else "auto"
    if a.command in ("make", "idea", "daily", "story", "housekeeping"):
        from . import library
        library.housekeeping(cfg)  # nayi photos ko sahi naam + naye designs library me
    if a.command == "housekeeping":
        _out([])
    elif a.command == "make":
        cmd_make(cfg, kind, a.idea or None, a.item or None, preset, a.offer.strip())
    elif a.command == "idea":
        cmd_idea(cfg, a.idea, a.item or None, kind, a.style, preset=preset, offer=a.offer.strip())
    elif a.command == "plan":
        from . import plan
        plan.plan(cfg)
    elif a.command == "story":
        cmd_story(cfg, a.slot)
    elif a.command == "publish-story":
        cmd_publish_story(cfg, a.slot)
    elif a.command == "daily":
        cmd_daily(cfg)
    else:
        cmd_publish(cfg, [x for x in a.dir.split() if x])


if __name__ == "__main__":
    main()
