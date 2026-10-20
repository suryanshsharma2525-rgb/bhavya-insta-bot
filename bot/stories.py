"""Daily Instagram Stories (9:16) — din me 2 baar: lunch aur raat.

Types:
  special   – aaj ka special item (badi saaf photo + price)
  question  – "A ya B?" sawaal → log DM me jawab dete hain → auto-reply unhe cafe bulata hai
  new_post  – aaj ka naya post/reel ka teaser
  mood      – time ke hisaab se ek line (shaam ki chai, late-night study break...)
  offer     – offer wale din reminder (sirf config.yaml ka approved offer)

Note: Instagram API se poll / link / question STICKER nahi lagte (Meta allow nahi karta),
isliye sawaal ka jawab "DM karo" style me hota hai.
"""
import datetime as dt
import json
import os
import random

from PIL import Image, ImageDraw, ImageFilter

from . import ai, photos, render as R, style as style_mod
from . import templates as T

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1080, 1920
SAFE_TOP, SAFE_BOTTOM = 250, 1640  # Instagram ke apne buttons/profile pic is area ke bahar rehte hain

SAMPLES = {
    "special": {"kicker": "AAJ KA SPECIAL", "line": "Fresh bana, garam parosa", "button": "Aaj hi aao"},
    "question": {"question": "Aaj ka mood kya hai?", "a_label": "Cheesy", "b_label": "Spicy",
                 "footer": "Reply karke batao, jawab hum dete hain"},
    "new_post": {"kicker": "NEW POST", "line": "Feed pe dekho, save karna mat bhoolna"},
    "mood": {"line": "Assignment baad me, chai pehle.", "sub": "Shaam ka adda: Bhavya Cafe"},
    "offer": {"kicker": "OFFER REMINDER", "line": "Aaj ka free item mat chhodna"},
}


def _texts(kind, cfg, ctx):
    prompt = (ai.STYLE_RULES + "\n\nWrite text for ONE Instagram STORY (9:16) for Bhavya Cafe. Very short, punchy, "
              "Hinglish, premium tone, no emojis, no hashtags.\n"
              f"Story type: {kind}\nContext: {json.dumps(ctx, ensure_ascii=False, default=str)}\n"
              f"Return JSON with exactly these keys: {list(SAMPLES[kind])}. Each value max 6 words "
              "(question max 7 words, footer max 9).")
    d = ai._gemini(prompt, cfg)
    base = dict(SAMPLES[kind])
    if isinstance(d, dict):
        for k in base:
            if isinstance(d.get(k), str) and d[k].strip():
                base[k] = ai.strip_emoji(d[k])[:60]
    return base


def _bg(pal, seed):
    from . import motion
    rng = random.Random(seed)
    old = (motion.W, motion.H)
    motion.W, motion.H = W, H
    try:
        bd = motion.Backdrop(rng, styles=tuple(rng.sample(["blobs", "bokeh", "spotlight", "grain", "rays"], 2)))
        im = bd.frame(rng.uniform(1, 4)).convert("RGB")
    finally:
        motion.W, motion.H = old
    return im.convert("RGBA")


def _card(pal):
    """Story ke text ke liye fonts (Art Director ka font pack)."""
    fp = R.FONTPACK or style_mod.FONT_PACKS["classic"]
    return {"fonts": {"display": list(fp["display"]), "serif": list(fp["serif"]), "script": list(fp["italic"]),
                      "sans": list(fp["body"]), "sans_bold": ["Montserrat.ttf", "ExtraBold"], "hand": ["Caveat.ttf", "Bold"],
                      "italic": list(fp["italic"])},
            "palette": {}}


def _hex(c):
    return "#%02x%02x%02x" % tuple(c[:3])


def _price(cfg, item):
    return next((m.get("price") for m in cfg["menu"] if m["name"] == item), None)


def _footer(im, cfg, pal, card):
    hours = (cfg.get("brand") or {}).get("hours") or ""
    line = " · ".join(x for x in [hours, "near IIT Roorkee", cfg["brand"].get("handle", "@bhavya_cafe")] if x)
    t = T.fit(line, card, "sans", W * 0.86, 34, color=_hex(pal["cream"]))
    im.alpha_composite(t, (int(W / 2 - t.width / 2), SAFE_BOTTOM - t.height))
    br = T.brand({"light": pal.get("light")}, _hex(pal["gold"]), 230)
    im.alpha_composite(br, (int(W / 2 - br.width / 2), SAFE_TOP - 70))


def render_story(kind, cfg, date, seed, ctx):
    look = style_mod.choose(cfg, seed, {"format": "story_" + kind}, use_ai=False)
    style_mod.apply(look)
    pal = look["palette"]
    card = _card(pal)
    im = _bg(pal, seed)
    cream, gold = _hex(pal["cream"]), _hex(pal["gold"])
    tx = _texts(kind, cfg, ctx)
    tctx = dict(mode="image", seed=seed, cfg=cfg, today=date, used=[])
    if kind in ("special", "offer"):
        item = ctx.get("item")
        kick = T.fit(tx["kicker"], card, "sans", W * 0.8, 40, color=gold, spacing=3)
        D, _ = T.dish(item, 900, tctx)
        D = T.shadowed(D, 34, 0.55)
        D.thumbnail((960, 760), Image.LANCZOS)
        nm = T.fit(item.upper(), card, "display", W * 0.88, 150, color=cream)
        ln = T.fit(tx["line"], card, "script", W * 0.8, 70, color=gold)
        p = _price(cfg, item)
        if kind == "offer":
            badge = T.pill("FREE", card, _hex(pal["bg"]), gold, 64, role="sans_bold")
            terms = T.fit(str(ctx.get("terms") or ""), card, "sans", W * 0.8, 32, color=cream)
            extra = [badge, terms]
        else:
            extra = [T.pill(f"₹{p}", card, _hex(pal["bg"]), gold, 56)] if p else []
        _stack(im, [kick, D, nm, ln] + extra, gaps=[10, -10, -20, 16, 6])
    elif kind == "question":
        q = T.multiline(_wrap(tx["question"], 14), card, "display", W * 0.86, 130, cream, gap=-30)
        im.alpha_composite(q, (int(W / 2 - q.width / 2), 380))
        y0 = 400 + q.height + 40
        for i, (it, lab) in enumerate(((ctx["a_item"], tx["a_label"]), (ctx["b_item"], tx["b_label"]))):
            D, _ = T.dish(it, 470, {**tctx, "seed": seed + str(i)})
            D = T.shadowed(D, 22, 0.5)
            D.thumbnail((500, 520), Image.LANCZOS)
            cx = int(W * (0.27 if i == 0 else 0.73))
            im.alpha_composite(D, (cx - D.width // 2, y0))
            tag = T.pill(f"{'A' if i == 0 else 'B'} · {it}", card, _hex(pal["bg"]), gold, 32, role="sans_bold")
            im.alpha_composite(tag, (cx - tag.width // 2, y0 + D.height - 20))
            lb = T.fit(lab, card, "script", W * 0.42, 64, color=cream)
            im.alpha_composite(lb, (cx - lb.width // 2, y0 + D.height + tag.height))
        ft = T.fit(tx["footer"], card, "sans", W * 0.86, 40, color=gold)
        im.alpha_composite(ft, (int(W / 2 - ft.width / 2), SAFE_BOTTOM - 150))
    elif kind == "new_post":
        src = ctx.get("post_image")
        kick = T.fit(tx["kicker"], card, "display", W * 0.8, 140, color=cream)
        parts = [kick]
        if src and os.path.exists(src):
            p = Image.open(src).convert("RGB")
            p.thumbnail((680, 850), Image.LANCZOS)
            p = T.rounded(p, 36)
            fr = Image.new("RGB", (p.width + 24, p.height + 24), (255, 255, 255))
            fr = T.rounded(fr, 44)
            fr.alpha_composite(p, (12, 12))
            parts.append(T.shadowed(fr.rotate(-3, expand=True, resample=Image.BICUBIC), 36, 0.55))
        parts.append(T.fit(tx["line"], card, "script", W * 0.86, 66, color=gold))
        _stack(im, parts, gaps=[10, 10])
    else:  # mood
        bgp = T.photo_bg(ctx.get("item"), W, H, tctx, darken=0.45)
        if bgp is not None:
            im = bgp.convert("RGBA")
            shade = Image.new("RGBA", (W, H), pal["bg"][:3] + (110,))
            im.alpha_composite(shade)
        ln = T.multiline(_wrap(tx["line"], 16), card, "serif", W * 0.86, 120, cream, gap=-20)
        im.alpha_composite(ln, (int(W / 2 - ln.width / 2), int(H * 0.42 - ln.height / 2)))
        sb = T.fit(tx["sub"], card, "script", W * 0.8, 72, color=gold)
        im.alpha_composite(sb, (int(W / 2 - sb.width / 2), int(H * 0.42 + ln.height / 2 + 30)))
    _footer(im, cfg, pal, card)
    return im.convert("RGB"), tctx["used"], tx, look


def _stack(im, parts, gaps=None):
    """Elements ko upar-se-neeche center me rakho (safe area ke andar, kuch overlap na ho)."""
    gaps = list(gaps or []) + [10] * len(parts)
    total = sum(p.height for p in parts) + sum(gaps[:len(parts) - 1])
    top_lim, bot_lim = SAFE_TOP + 60, SAFE_BOTTOM - 80
    if total > bot_lim - top_lim:  # bada ho gaya → sab chhota karo
        k = (bot_lim - top_lim) / total
        parts = [p.resize((max(1, int(p.width * k)), max(1, int(p.height * k))), Image.LANCZOS) for p in parts]
        gaps = [int(g * k) for g in gaps]
        total = bot_lim - top_lim
    y = int(top_lim + (bot_lim - top_lim - total) / 2)
    for i, p in enumerate(parts):
        im.alpha_composite(p, (int(W / 2 - p.width / 2), y))
        y += p.height + (gaps[i] if i < len(gaps) else 0)


def _wrap(s, n):
    words, lines, cur = s.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return lines + ([cur] if cur else [])


def plan_slot(slot, cfg, date):
    """Kaunse stories aaj is slot me jayengi."""
    sc = cfg.get("stories") or {}
    kinds = list((sc.get("slots") or {}).get(slot) or [])
    o = cfg.get("weekly_offer", {})
    if slot == "lunch" and o.get("enabled", True) and date.strftime("%A") == o.get("weekday") and "offer" not in kinds:
        kinds.append("offer")
    return kinds


def build(slot, cfg, date):
    from .main import load_history
    kinds = plan_slot(slot, cfg, date)
    out_dir = os.path.join(ROOT, "posts", "stories", f"{date.isoformat()}_{slot}")
    os.makedirs(out_dir, exist_ok=True)
    hist = load_history()
    recent_items = [h.get("item") for h in hist[-3:]]
    menu = [m["name"] for m in cfg["menu"] if photos.photos_for(m["name"])[0]] or [m["name"] for m in cfg["menu"]]
    rng = random.Random(f"story-{date}-{slot}")
    files, info = [], []
    for i, kind in enumerate(kinds):
        ctx = {"date": date.isoformat(), "slot": slot, "weekday": date.strftime("%A")}
        if kind in ("special", "mood"):
            ctx["item"] = rng.choice([m for m in menu if m not in recent_items] or menu)
        elif kind == "question":
            ctx["a_item"], ctx["b_item"] = rng.sample(menu, 2)
        elif kind == "offer":
            from . import planner
            it, _ = planner.offer_item(date, cfg)
            ctx["item"] = it["name"]
            ctx["terms"] = cfg["weekly_offer"].get("terms")
        elif kind == "new_post":
            today = os.path.join(ROOT, "posts", date.isoformat())
            pj = os.path.join(today, "post.json")
            if not os.path.exists(pj):
                continue
            m = json.load(open(pj, encoding="utf-8"))
            if not m.get("permalink"):
                continue  # post abhi live nahi hua
            cover = "reel_cover.jpg" if m.get("kind") == "reel" else (m.get("files") or ["slide1.jpg"])[0]
            ctx["post_image"] = os.path.join(today, cover)
            ctx["headline"] = m.get("headline")
        im, used, tx, look = render_story(kind, cfg, date, f"{date}-{slot}-{i}-{kind}", ctx)
        name = f"story{i + 1}_{kind}.jpg"
        im.save(os.path.join(out_dir, name), quality=93, optimize=True)
        photos.record_use(used, "reel", date)
        files.append(name)
        info.append({"file": name, "kind": kind, "text": tx, "item": ctx.get("item") or ctx.get("a_item"),
                     "style": style_mod.describe(look)})
    meta = {"date": date.isoformat(), "slot": slot, "kind": "story", "stories": info, "files": files, "published": []}
    json.dump(meta, open(os.path.join(out_dir, "story.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Stories ({slot}):", files)
    return out_dir


def publish(slot, cfg, date):
    from .instagram import IG
    d = os.path.join(ROOT, "posts", "stories", f"{date.isoformat()}_{slot}")
    pj = os.path.join(d, "story.json")
    if not os.path.exists(pj):
        print("Koi story nahi bani.")
        return
    meta = json.load(open(pj, encoding="utf-8"))
    repo = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    ig = IG(cfg)
    for f in meta["files"]:
        if f in meta["published"]:
            continue
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/posts/stories/{os.path.basename(d)}/{f}"
        try:
            ig.post_story(image_url=url)
            meta["published"].append(f)
        except Exception as e:
            print("Story publish failed:", f, str(e)[:300])
    json.dump(meta, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
