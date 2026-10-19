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
               as_video=False, theme=None):
    trends = planner.recent_trends(cfg, date) if trends is None else trends
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

    post = ai.write_post(fmt_key, cfg, ctx)
    os.makedirs(out_dir, exist_ok=True)
    # AI food photos: pehle aaj ke post ke items, phir baaki menu (library dheere-dheere poori ho jaati hai)
    wanted = [post.get(k) for k in ("item", "right_item", "a_item", "b_item")] + list(post.get("items") or [])
    wanted += [x.get("item") for x in post.get("shots", []) + post.get("scenes", []) if isinstance(x, dict)]
    if offer_item:
        wanted += [i["name"] for i in all_items]
    wanted += [m["name"] for m in cfg["menu"]]
    photos.ensure_photos([w for w in wanted if w], cfg)
    seed = f"{date.isoformat()}-{fmt_key}{seed_extra}"
    files, owner_note = [], ""
    theme = render.set_theme(theme if theme and theme != "auto" else pick_theme(cfg, date, seed))
    kind = fmt["kind"]

    if fmt_key.startswith("offer_"):
        valid_till = date + dt.timedelta(days=cfg["weekly_offer"].get("valid_days", 7) - 1)
        terms = f"🎁 Valid till {valid_till:%d %b}. {cfg['weekly_offer']['terms']}"
        post["caption"] = post["caption"].replace(cfg["brand"]["location_line"],
                                                  terms + "\n\n" + cfg["brand"]["location_line"])
    if fmt_key == "offer_flash_reel":
        post["_all_free_items"] = all_items
        path = render.render_reel(post, cfg, os.path.join(out_dir, "reel.mp4"), seed)
        files = [os.path.basename(path), "reel_cover.jpg"]
        owner_note = (f"FLASH OFFER: jo bhi item ka screenshot dikhaye ({', '.join(i['name'] for i in all_items)}) "
                      f"wo free — valid till {valid_till:%d %b}. Terms: {cfg['weekly_offer']['terms']}")
    elif kind == "reel":
        path = reels.render_reel(fmt["renderer"], post, cfg, os.path.join(out_dir, "reel.mp4"), seed)
        files = ["reel.mp4", "reel_cover.jpg"]
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
    meta = {"date": date.isoformat(), "format": fmt_key, "kind": kind, "theme": theme, "files": files, "featured_item": featured,
            "caption": post["caption"], "alt_text": post["alt_text"], "headline": headline,
            "owner_note": owner_note, "text_source": post["_source"], "trends_used": trends}
    with open(os.path.join(out_dir, "post.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    print(f"[{date} {day}] {fmt_key} → {out_dir}  ({post['_source']})")
    if owner_note:
        print("OWNER NOTE:", owner_note)
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
    history.append({"date": meta["date"], "format": meta["format"], "headline": meta["headline"]})
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
    repo = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    url = lambda f: f"https://raw.githubusercontent.com/{repo}/{branch}/posts/{dirname}/{f}"
    ig = IG(cfg)
    if meta["kind"] == "reel":
        link = ig.post_reel(os.path.join(d, "reel.mp4"), meta["caption"], cover_url=url("reel_cover.jpg"))
    elif meta["kind"] == "carousel":
        link = ig.post_carousel([url(f) for f in meta["files"]], meta["caption"], meta["alt_text"])
    else:
        link = ig.post_image(url(meta["files"][0]), meta["caption"], meta["alt_text"])
    meta["permalink"] = link
    with open(os.path.join(d, "post.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    calendar_plan.log_post(dirname, meta, "post-now" if "_now_" in dirname else "daily", "published", link)
    if "_now_" not in dirname:
        calendar_plan.mark_posted(dirname, link)


def cmd_preview_week(date, cfg, trends=None):
    out = os.path.join(ROOT, "preview")
    shutil.rmtree(out, ignore_errors=True)
    monday = date - dt.timedelta(days=date.weekday())
    history, thumbs = [], []
    for i in range(7):
        d = monday + dt.timedelta(days=i)
        meta = build_post(d, cfg, os.path.join(out, f"{i + 1}_{d:%a}_{d.isoformat()}"), history, trends=trends)
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
    ap.add_argument("command", choices=["generate", "publish", "post-now", "plan-calendar", "preview-week", "refresh-token", "make-photos"])
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
    elif a.command == "plan-calendar":
        calendar_plan.plan_calendar(cfg, date, a.days)
    elif a.command == "post-now":
        cmd_post_now(cfg, a.format, a.idea, a.item, a.type, a.theme)
    elif a.command == "make-photos":
        made = photos.ensure_photos([m["name"] for m in cfg["menu"]] + [i["name"] for i in cfg["weekly_offer"]["free_items"]],
                                    cfg, max_new=200)
        print(f"{made} nayi photos bani.")
        if not made and not any(photos.photos_for(m["name"])[0] for m in cfg["menu"]):
            raise SystemExit("❌ Ek bhi photo nahi bani. Upar ka error dekho (CF_ACCOUNT_ID / CF_API_TOKEN secrets check karo).")
    elif a.command == "preview-week":
        cmd_preview_week(date, cfg, trends=a.trend)
    else:
        from .instagram import refresh_token
        print(refresh_token())


if __name__ == "__main__":
    main()
