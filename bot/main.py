"""Bhavya Cafe Instagram bot.

  python -m bot.main generate        # aaj ka post banao (posts/<date>/)
  python -m bot.main publish         # aaj ka post Instagram pe daalo
  python -m bot.main post-now --format auto --idea "..." --item "Kulhad Pizza"   # abhi turant ek extra post
  python -m bot.main plan-calendar   # aage ke 30 din ka content calendar (data/content_calendar.csv)
  python -m bot.main preview-week    # poore hafte ke 7 posts preview/ me (kuch post nahi hota)
  python -m bot.main refresh-token   # Instagram token renew
  python -m bot.main make-photos     # saare menu items ki AI food photos ek saath banao
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil

import yaml
from PIL import Image

from . import ai, calendar_plan, photos, planner, reels, render
from .formats import ALL_FORMATS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
HISTORY = os.path.join(ROOT, "data", "history.json")


def load_cfg():
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def today_ist():
    return dt.datetime.now(IST).date()


def _perf():
    try:
        with open(os.path.join(ROOT, "data", "performance.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def pick_theme(cfg, date, seed):
    import random as _r
    themes = [t for t in (cfg.get("themes") or ["classic_gold"]) if t in render.THEMES] or ["classic_gold"]
    if cfg.get("theme_mode", "rotate") == "fixed":
        return themes[0]
    return themes[(date.toordinal() + _r.Random(seed).randint(0, 0)) % len(themes)]


def load_history():
    if os.path.exists(HISTORY):
        with open(HISTORY, encoding="utf-8") as fh:
            return json.load(fh)
    return []


def build_post(date, cfg, out_dir, history, trends=None, fmt_key=None, idea=None, focus_item=None, seed_extra="",
               as_video=False, theme=None, audit_on=True):
    """Post banao → AI Auditor check → fail ho to naye design/photo se dobara (max 2 baar) → sabse achha version rakho."""
    from . import audit
    ac = cfg.get("audit", {})
    trends = planner.recent_trends(cfg, date) if trends is None else trends
    if not (audit_on and ac.get("enabled", True)):
        return _build_once(date, cfg, out_dir, history, trends, fmt_key, idea, focus_item, seed_extra, as_video, theme)
    tries = 1 + int(ac.get("max_retries", 2))
    results = []
    for a in range(tries):
        d = f"{out_dir}__try{a}"
        shutil.rmtree(d, ignore_errors=True)
        meta = _build_once(date, cfg, d, history, trends, fmt_key, idea, focus_item,
                           seed_extra + (f"-r{a}" if a else ""), as_video, theme, no_cut=(a >= 2))
        rep = audit.post_check(d, meta, cfg, meta.pop("_guard", None))
        audit.log(os.path.basename(out_dir), a + 1, meta, rep)
        meta["audit"] = rep
        print(f"AUDIT try {a + 1}: ok={rep['ok']} score={rep.get('score')} issues={rep.get('issues')}")
        results.append((d, meta))
        if rep["ok"]:
            break
        fmt_key = fmt_key or meta["format"]  # retry me format wahi, design/photo naya
    rank = lambda r: (bool(r[1]["audit"]["ok"]), r[1]["audit"].get("score") or 0, -len(r[1]["audit"].get("issues") or []))
    best_dir, best = max(results, key=rank)
    r = best["audit"]
    hard_min = ac.get("hard_min_score", 5)
    det = r.get("detail") or {}
    if not r["ok"] and ((r.get("score") is not None and r["score"] < hard_min) or det.get("food_fully_visible") is False):
        r["blocked"] = True
        print(f"⛔ AUDITOR: {tries} koshish ke baad bhi post premium level ka nahi bana — publish nahi hoga. "
              f"Wajah: {r.get('issues')}")
    shutil.rmtree(out_dir, ignore_errors=True)
    shutil.move(best_dir, out_dir)
    for d, _ in results:
        shutil.rmtree(d, ignore_errors=True)
    with open(os.path.join(out_dir, "post.json"), "w", encoding="utf-8") as fh:
        json.dump(best, fh, ensure_ascii=False, indent=2)
    return best


def _build_once(date, cfg, out_dir, history, trends, fmt_key=None, idea=None, focus_item=None, seed_extra="",
                as_video=False, theme=None, no_cut=False):
    day = date.strftime("%A")
    fmt_key = fmt_key or planner.week_plan(date, cfg, has_trend=bool(trends))[day]
    fmt = ALL_FORMATS[fmt_key]
    year, week, _ = date.isocalendar()
    ctx = {"date": date, "week": week, "trends": trends, "recent": [h["headline"] for h in history],
           "idea": idea, "focus_item": focus_item}

    offer_item = None
    if fmt_key.startswith("offer_"):
        offer_item, all_items = planner.offer_item(date, cfg)
        ctx["offer_item"] = offer_item

    # ---- Growth brain: 🔥 winner din (jo chal raha hai uska system) ya 🧪 experiment din
    from . import growth
    gperf = growth.load()
    winner = growth.is_winner_day(date, cfg, gperf)
    recipe = gperf.get("recipe", {}) if winner else {}
    ctx["strategy"] = "winner" if winner else "experiment"
    ctx["growth_brief"] = growth.winner_brief(gperf) if winner else growth.avoid_brief(gperf)
    if winner and not focus_item and recipe.get("item") and recipe["item"] not in [h.get("item") for h in history[-3:]]:
        ctx["focus_item"] = focus_item = recipe["item"]
    if winner:
        print("🔥 WINNER DIN — recipe:", recipe)
    card, tctx = None, None
    if fmt_key.startswith("poster"):
        from . import designs
        perf = _perf().get("designs", {})
        card = designs.choose(history, f"{date}{seed_extra}", perf=perf, prefer=recipe.get("design") if not seed_extra.endswith(("-r1", "-r2")) else None)
        if card:
            ctx["design"] = designs.describe(card)
            print("Design (reference style):", ctx["design"])
        else:
            fmt_key, fmt = "product_spotlight", ALL_FORMATS["product_spotlight"]
    post = ai.write_post(fmt_key, cfg, ctx)
    os.makedirs(out_dir, exist_ok=True)
    # AI food photos: pehle aaj ke post ke items, phir baaki menu (library dheere-dheere poori ho jaati hai)
    wanted = [post.get(k) for k in ("item", "right_item", "a_item", "b_item")] + list(post.get("items") or [])
    wanted += [x.get("item") for x in post.get("shots", []) + post.get("scenes", []) if isinstance(x, dict)]
    if offer_item:
        wanted += [i["name"] for i in all_items]
    # sirf is post ke items (poore menu ki library ka kaam "Make AI food photos" karta hai — post fast bane)
    photos.ensure_photos([w for w in wanted if w], cfg, max_new=cfg.get("photos", {}).get("max_new_per_post", 3),
                         allow_stock=False)
    seed = f"{date.isoformat()}-{fmt_key}{seed_extra}"
    files, owner_note = [], ""
    kind = fmt["kind"]
    # ---- AI Art Director: is post ka poora look (colours, fonts, animation, transitions, layouts)
    from . import style as style_mod, motion
    occ = ", ".join(o[0] for o in calendar_plan.occasions_on(date))
    look = style_mod.choose(cfg, seed, dict(format=fmt_key, occasion=occ, idea=idea, date=date.isoformat(),
                                            recent_styles=[h.get("style") for h in history[-6:] if h.get("style")]),
                            use_ai=cfg.get("art_director", {}).get("ai", True) and not recipe,
                            force={k: recipe[k] for k in ("vibe", "harmony", "font_pack", "mode") if recipe.get(k)})
    if theme and theme != "auto" and theme in render.THEMES:  # POST NOW me theme chuna ho to wahi
        look["palette_name"], look["palette"] = theme, render.THEMES[theme]
    style_mod.apply(look)
    if card:  # designer poster: poore reel (logo card samet) me reference wale hi colours
        from .templates import C as _C
        cp = card["palette"]
        render.set_theme_dict("card-" + card["id"], dict(
            bg=_C(cp["bg"]), card=_C(cp.get("panel", cp["bg"])), panel=_C(cp.get("panel", cp["bg"])),
            line=_C(cp.get("panel", cp["bg"])), alt=_C(cp.get("panel", cp["bg"])), gold=_C(cp.get("word", cp["text"])),
            stops=[(0, _C(cp.get("word", cp["text"]))), (1, _C(cp.get("word", cp["text"])))],
            cream=_C(cp["text"]), muted=_C(cp.get("text2", cp["text"])), light=bool(card.get("light"))))
        look["palette_name"] = "card-" + card["id"]
    theme = look["palette_name"]
    motion.STYLE_POOL.update(anims=look["text_anims"], transitions=look["transitions"], layouts=look["layouts"],
                             backgrounds=look["backgrounds"], mood=(card or {}).get("mood") or look["mood"],
                             vibe=(card or {}).get("vibe") or look["vibe"], used=[],
                             recent_music=[h.get("music") for h in history[-4:] if h.get("music")],
                             left_align=0.35 if look["font_pack"] in ("editorial", "minimal", "luxe") else 0.12)
    print("Art Director:", style_mod.describe(look))

    if fmt_key.startswith("offer_"):
        valid_till = date + dt.timedelta(days=cfg["weekly_offer"].get("valid_days", 7) - 1)
        terms = f"🎁 Valid till {valid_till:%d %b}. {cfg['weekly_offer']['terms']}"
        post["caption"] = post["caption"].replace(cfg["brand"]["location_line"],
                                                  terms + "\n\n" + cfg["brand"]["location_line"])
    if fmt_key == "offer_flash_reel":
        post["_all_free_items"] = all_items
        path = reels.render_reel("offer_flash_reel", post, cfg, os.path.join(out_dir, "reel.mp4"), seed)
        files = [os.path.basename(path), "reel_cover.jpg"]
        owner_note = (f"FLASH OFFER: jo bhi item ka screenshot dikhaye ({', '.join(i['name'] for i in all_items)}) "
                      f"wo free — valid till {valid_till:%d %b}. Terms: {cfg['weekly_offer']['terms']}")
    elif card is not None:  # ---- Pinterest-style designer poster (image / reel)
        from . import templates as TT
        tctx = dict(seed=seed, cfg=cfg, today=date, used=[], guard_log=[], no_cut=no_cut)
        content = dict(post, handle=cfg["brand"].get("handle", "@bhavya_cafe"),
                       price=next((m.get("price") for m in cfg["menu"] if m["name"] == post["item"]), None))
        if kind == "image" and not as_video:
            tctx["mode"] = "image"
            im = TT.compose(TT.layout(card, content, 1080, 1350, tctx), 1080, 1350).convert("RGB")
            im.save(os.path.join(out_dir, "slide1.jpg"), quality=94, optimize=True)
            files = ["slide1.jpg"]
            photos.record_use(tctx["used"], "image", date)
        else:
            tctx["mode"] = "reel"
            slides = (post.get("items") or [post["item"]]) if fmt_key == "poster_reel" else [post["item"]]
            has_ph = lambda n: bool(photos.photos_for(n)[0])
            slides = [x for x in slides if has_ph(x)] or slides  # jinki photo hai wahi slides me
            if fmt_key == "poster_reel" and len(slides) < 3:
                slides += [m["name"] for m in cfg["menu"] if has_ph(m["name"]) and m["name"] not in slides][:3 - len(slides)]
            slides = slides[:3]
            spec = []
            for i, it in enumerate(slides):
                ci = dict(content, item=it, word=(post["word"] if i == 0 else it.split()[-1].upper()[:10]),
                          price=next((m.get("price") for m in cfg["menu"] if m["name"] == it), None))
                if i:
                    for k in ("note_lines", "notes", "title_lines"):
                        ci.pop(k, None)
                spec.append(dict(type="tpl", size=(1080, 1350),
                                 layers=TT.layout(card, ci, 1080, 1350, {**tctx, "seed": f"{seed}{i}"}),
                                 beats=8 if len(slides) > 1 else 12))
            spec.append(dict(type="logo", cta=post.get("button") or "Visit Today"))
            reels.motion.render(spec, cfg, os.path.join(out_dir, "reel.mp4"), seed, (card or {}).get("mood"))
            photos.record_use(tctx["used"], "reel", date)
            files, kind = ["reel.mp4", "reel_cover.jpg"], "reel"
    elif kind == "reel":
        path = reels.render_reel(fmt["renderer"], post, cfg, os.path.join(out_dir, "reel.mp4"), seed)
        files = ["reel.mp4", "reel_cover.jpg"]
        photos.record_use(motion.STYLE_POOL.get("used", []), "reel", date)
    else:
        if fmt_key == "offer_zoom_code":
            post["_offer_item"] = offer_item
            post["_code"] = f"BH{week:02d}-{re.sub('[^A-Z]', '', offer_item['name'].upper())[:6]}"
            owner_note = (f"ZOOM OFFER CODE: {post['_code']} = FREE {offer_item['name']} "
                          f"(valid till {valid_till:%d %b}). Terms: {cfg['weekly_offer']['terms']}")
        images = render.render_images(fmt, post, cfg, seed)
        for i, im in enumerate(images, 1):
            name = f"slide{i}.jpg"
            im.convert("RGB").save(os.path.join(out_dir, name), quality=93, optimize=True)
            files.append(name)
        if post.get("_answer"):
            owner_note = f"Puzzle answer: {post['_answer']}"
        if as_video:  # image/carousel post → music wala video
            reels.images_to_reel(images, cfg, os.path.join(out_dir, "reel.mp4"), seed)
            files, kind = ["reel.mp4", "reel_cover.jpg"], "reel"

    headline = (post.get("top") or post.get("hook") or post.get("concept_title") or post.get("title")
                or post.get("tagline") or post.get("quote") or post.get("opening_line")
                or (post.get("pov_lines") or [None])[0] or post.get("headline") or post.get("line") or post.get("question")
                or post.get("combo_name") or (post.get("slides") or [{}])[0].get("big") or fmt_key)
    featured = (focus_item or post.get("item") or post.get("right_item") or post.get("a_item")
                or (post.get("items") or [None])[0] or (offer_item or {}).get("name") or "")
    meta = {"date": date.isoformat(), "format": fmt_key, "kind": kind, "theme": theme, "style": style_mod.describe(look), "design": (card or {}).get("id"),
            "music": motion.STYLE_POOL.get("last_music") if kind == "reel" else None, "files": files, "featured_item": featured,
            "caption": post["caption"], "alt_text": post["alt_text"], "headline": headline,
            "owner_note": owner_note, "text_source": post["_source"], "trends_used": trends,
            "strategy": ctx.get("strategy")}
    with open(os.path.join(out_dir, "post.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    print(f"[{date} {day}] {fmt_key} → {out_dir}  ({post['_source']})")
    if owner_note:
        print("OWNER NOTE:", owner_note)
    meta["_guard"] = (tctx or {}).get("guard_log") if card is not None else None
    return meta


def cmd_generate(date, cfg):
    history = load_history()
    calendar_plan.plan_calendar(cfg, date, 30)          # calendar hamesha 30 din aage tak bhara rahe
    tp = calendar_plan.today_plan(date, cfg) or {}
    if tp:
        print("Calendar se aaj ka plan:", tp)
    meta = build_post(date, cfg, os.path.join(ROOT, "posts", date.isoformat()), history,
                      fmt_key=tp.get("format"), idea=tp.get("idea"), focus_item=tp.get("item"))
    _save_history(history, meta)
    calendar_plan.log_post(date.isoformat(), meta, "daily", "generated")


def _save_history(history, meta):
    history.append({"date": meta["date"], "format": meta["format"], "headline": meta["headline"],
                    "style": "{vibe}/{mode}/{accent}/{font_pack}".format(**meta["style"]) if meta.get("style") else None,
                    "design": meta.get("design"), "music": meta.get("music"), "item": meta.get("featured_item"),
                    "strategy": meta.get("strategy")})
    os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
    with open(HISTORY, "w", encoding="utf-8") as fh:
        json.dump(history[-120:], fh, ensure_ascii=False, indent=1)


def _match_item(cfg, name):
    if not name:
        return None
    n = name.strip().lower()
    for m in cfg["menu"]:
        if m["name"].lower() == n:
            return m["name"]
    for m in cfg["menu"]:
        if n in m["name"].lower() or m["name"].lower() in n:
            return m["name"]
    print(f"Item '{name}' menu me nahi mila — AI khud item chunega.")
    return None


def cmd_post_now(cfg, fmt_key=None, idea=None, item=None, post_type="auto", theme=None):
    """Abhi ke abhi ek extra post banao (daily post se alag). post_type: auto | image | video"""
    import random as _r
    now = dt.datetime.now(IST)
    history = load_history()
    post_type = (post_type or "auto").lower()
    if not fmt_key or fmt_key == "auto":
        recent = {h.get("format") for h in history[-7:]}
        pool = [k for k, f in planner.FORMATS.items() if not f.get("needs_trend")]
        if post_type == "video":
            pool = [k for k in pool if planner.FORMATS[k]["kind"] == "reel"]
        elif post_type == "image":
            pool = [k for k in pool if planner.FORMATS[k]["kind"] != "reel"]
        if idea or item:  # idea/item diya hai → wahi formats jisme text aur item dikh sake
            pool = [k for k in pool if k in ("reel_freestyle", "reel_showcase", "reel_meme", "reel_pov", "product_spotlight",
                                             "mood_quote", "meme_card", "local_roorkee", "versus", "tag_friend")] or pool
        choices = [k for k in pool if k not in recent] or pool
        fmt_key = _r.choice(choices)
    if fmt_key not in ALL_FORMATS:
        raise SystemExit(f"Format '{fmt_key}' nahi mila. Options: {', '.join(ALL_FORMATS)}")
    as_video = post_type == "video" and ALL_FORMATS[fmt_key]["kind"] != "reel"
    name = f"{now.date().isoformat()}_now_{now:%H%M}"
    meta = build_post(now.date(), cfg, os.path.join(ROOT, "posts", name), history, fmt_key=fmt_key,
                      idea=(idea or "").strip() or None, focus_item=_match_item(cfg, item), seed_extra=name,
                      as_video=as_video, theme=theme)
    _save_history(history, meta)
    calendar_plan.log_post(name, meta, "post-now", "generated")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as fh:
            fh.write(f"post_dir={name}\n")
    print("POST_DIR", name)
    return name


def cmd_publish(date, cfg, dirname=None):
    from .instagram import IG
    dirname = dirname or date.isoformat()
    d = os.path.join(ROOT, "posts", dirname)
    with open(os.path.join(d, "post.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    if meta.get("permalink"):
        print("Already published:", meta["permalink"])
        return
    if (meta.get("audit") or {}).get("blocked"):
        print("⛔ AI Auditor ne is post ko rok diya (quality kam thi):", meta["audit"].get("issues"))
        print("   POST NOW se dobara banwa lo, ya assets/photos me achhi asli photos daal do.")
        calendar_plan.log_post(dirname, meta, "audit", "blocked")
        return
    repo = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    url = lambda f: f"https://raw.githubusercontent.com/{repo}/{branch}/posts/{dirname}/{f}"
    ig = IG(cfg)
    if meta["kind"] == "reel":
        import subprocess
        try:
            sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
        except Exception:
            sha = ""
        ref = sha or branch
        vids = [f"https://cdn.jsdelivr.net/gh/{repo}@{ref}/posts/{dirname}/reel.mp4",   # sahi video/mp4 type
                f"https://raw.githubusercontent.com/{repo}/{ref}/posts/{dirname}/reel.mp4"]
        link = ig.post_reel(vids, meta["caption"], cover_url=url("reel_cover.jpg"))
    elif meta["kind"] == "carousel":
        link = ig.post_carousel([url(f) for f in meta["files"]], meta["caption"], meta["alt_text"])
    else:
        link = ig.post_image(url(meta["files"][0]), meta["caption"], meta["alt_text"])
    meta["permalink"] = link
    meta["media_id"] = getattr(ig, "last_media_id", None)
    with open(os.path.join(d, "post.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    calendar_plan.log_post(dirname, meta, "post-now" if "_now_" in dirname else "daily", "published", link)
    if "_now_" not in dirname:
        calendar_plan.mark_posted(dirname, link)


def cmd_learn(cfg):
    """Pichhle posts ki reach/saves/shares padho → data/performance.json (AI Director isse seekhta hai)."""
    import glob as _g
    from .instagram import IG
    try:
        ig = IG(cfg)
    except Exception as e:
        print("Learn skip:", e)
        return
    today = today_ist()
    rows = []
    for pj in sorted(_g.glob(os.path.join(ROOT, "posts", "*", "post.json")))[-60:]:
        with open(pj, encoding="utf-8") as fh:
            m = json.load(fh)
        if not m.get("media_id"):
            continue
        age = (today - dt.date.fromisoformat(m["date"])).days
        if age < 1:
            continue
        if age <= 14 or "stats" not in m:  # 2 hafte tak roz update, phir freeze
            st = ig.insights(m["media_id"])
            if st:
                m["stats"] = st
                with open(pj, "w", encoding="utf-8") as fh:
                    json.dump(m, fh, ensure_ascii=False, indent=2)
                calendar_plan.log_stats(os.path.basename(os.path.dirname(pj)), st)
        if m.get("stats"):
            m["_dir"] = os.path.basename(os.path.dirname(pj))
            rows.append(m)
    if not rows:
        print("Abhi seekhne layak data nahi hai.")
        return
    from . import growth
    growth.learn(rows, cfg)


def cmd_preview_week(date, cfg, trends=None):
    out = os.path.join(ROOT, "preview")
    shutil.rmtree(out, ignore_errors=True)
    monday = date - dt.timedelta(days=date.weekday())
    history, thumbs = [], []
    for i in range(7):
        d = monday + dt.timedelta(days=i)
        meta = build_post(d, cfg, os.path.join(out, f"{i + 1}_{d:%a}_{d.isoformat()}"), history, trends=trends,
                          audit_on=False)
        history.append({"headline": meta["headline"]})
        first = os.path.join(out, f"{i + 1}_{d:%a}_{d.isoformat()}",
                             "reel_cover.jpg" if meta["kind"] == "reel" else meta["files"][0])
        thumbs.append((d, meta, Image.open(first).convert("RGB")))
    # contact sheet
    tw, th = 360, 450
    sheet = Image.new("RGB", (tw * 4 + 50, (th + 70) * 2 + 30), (30, 28, 24))
    for i, (d, meta, im) in enumerate(thumbs):
        im = im.copy()
        im.thumbnail((tw, th))
        x, y = 10 + (i % 4) * (tw + 10), 10 + (i // 4) * (th + 80)
        sheet.paste(im, (x + (tw - im.width) // 2, y))
        render.text(sheet, (x + tw / 2, y + th + 28), f"{d:%a} · {meta['format']}", render.F("med", 22),
                    render.CREAM)
    sheet.save(os.path.join(out, "week_overview.jpg"), quality=90)
    print("Preview ready in", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["generate", "publish", "post-now", "plan-calendar", "preview-week", "refresh-token", "make-photos", "learn", "references",
                                        "story", "publish-story", "replies"])
    ap.add_argument("--slot", default="lunch", help="story: lunch | night")
    ap.add_argument("--date", help="YYYY-MM-DD (default: today IST)")
    ap.add_argument("--trend", action="append", help="preview ke liye trend test karna ho to")
    ap.add_argument("--format", help="post-now: format ka naam ya 'auto'")
    ap.add_argument("--idea", help="post-now: aapka idea / offer / announcement")
    ap.add_argument("--item", help="post-now: kaunsa menu item feature karna hai")
    ap.add_argument("--type", default="auto", help="post-now: auto | image | video")
    ap.add_argument("--theme", default="auto", help="colour theme ka naam ya auto")
    ap.add_argument("--dir", help="publish: posts/ ke andar folder ka naam")
    ap.add_argument("--days", type=int, default=30, help="plan-calendar: kitne din aage")
    a = ap.parse_args()
    cfg = load_cfg()
    date = dt.date.fromisoformat(a.date) if a.date else today_ist()
    if a.command == "generate":
        cmd_generate(date, cfg)
    elif a.command == "publish":
        cmd_publish(date, cfg, a.dir)
    elif a.command == "learn":
        cmd_learn(cfg)
    elif a.command == "story":
        from . import stories
        if (cfg.get("stories") or {}).get("enabled", True):
            stories.build(a.slot, cfg, date)
    elif a.command == "publish-story":
        from . import stories
        stories.publish(a.slot, cfg, date)
    elif a.command == "replies":
        from . import replies
        replies.run(cfg)
    elif a.command == "references":
        from . import designs, audio
        print("Naye references:", designs.analyze_new_references(cfg))
        audio.index()
    elif a.command == "plan-calendar":
        calendar_plan.plan_calendar(cfg, date, a.days)
    elif a.command == "post-now":
        cmd_post_now(cfg, a.format, a.idea, a.item, a.type, a.theme)
    elif a.command == "make-photos":
        from . import audit
        audit.audit_library(cfg)  # purani blur/galat/watermark wali photos hatao (asli photos kabhi nahi)
        made = photos.ensure_photos([m["name"] for m in cfg["menu"]] + [i["name"] for i in cfg["weekly_offer"]["free_items"]],
                                    cfg, max_new=200)
        print(f"{made} nayi photos bani.")
        print("Background videos:", photos.fetch_bg_videos())
        for m in cfg["menu"]:  # cut-outs pehle se bana ke rakho (reels fast banenge)
            for pth in photos.photos_for(m["name"])[0][:5]:
                photos.cutout(pth)
        if not made and not any(photos.photos_for(m["name"])[0] for m in cfg["menu"]):
            raise SystemExit("❌ Ek bhi photo nahi bani. Upar ka error dekho (CF_ACCOUNT_ID / CF_API_TOKEN secrets check karo).")
    elif a.command == "preview-week":
        cmd_preview_week(date, cfg, trends=a.trend)
    else:
        from .instagram import refresh_token
        print(refresh_token())


if __name__ == "__main__":
    main()
