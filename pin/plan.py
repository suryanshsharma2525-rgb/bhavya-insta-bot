"""Content calendar (aane wale 30 din) — naye Pinterest-design system ke liye.

Har din ki row: occasion, type (reel/image), preset (offer/combo/visit_now/weekend/exam/festival/...),
offer text, item (sirf wahi jinki asli photo hai), idea.
Data: data/content_calendar.csv (+ .ics → phone ke Google Calendar me dikhta hai).
Aap CSV me koi bhi row edit kar sakte ho — bot aapka likha hi follow karega.
"""
import datetime as dt
import json
import random

from . import photos, presets

ROTATE = ["visit_now", "auto", "combo", "auto", "new_item", "late_night", "auto"]


def _preset_for(d, occ, cfg):
    names = " ".join(o[0].lower() for o in occ)
    o = cfg.get("weekly_offer") or {}
    if o.get("enabled", True) and d.strftime("%A") == o.get("weekday"):
        return "offer"
    if "exam" in names:
        return "exam"
    if occ and any(w in names for w in ("diwali", "holi", "eid", "christmas", "festival", "lohri", "navratri", "dussehra",
                                        "rakhi", "new year", "independence", "republic", "janmashtami", "teej")):
        return "festival"
    if d.weekday() >= 5:
        return "weekend"
    return ROTATE[d.toordinal() % len(ROTATE)]


def plan(cfg, start=None, days=30):
    from bot import calendar_plan as CP
    start = start or dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date()
    cal = CP.load_calendar()
    have = sorted(photos.items_with_photos(cfg["menu"]))
    menu = have or [m["name"] for m in cfg["menu"]]
    recent = []
    todo = []
    pcfg = cfg.get("pin") or {}
    for i in range(days):
        d = start + dt.timedelta(days=i)
        key = d.isoformat()
        r = cal.get(key) or {"date": key, "day": d.strftime("%a"), "status": "planned", "instagram_link": ""}
        if r.get("status") == "posted":
            recent.append(r.get("featured_item"))
            continue
        occ = CP.occasions_on(d)
        r.setdefault("occasion", " + ".join(o[0] for o in occ))
        if not r.get("preset"):
            r["preset"] = _preset_for(d, occ, cfg)
        if not r.get("type"):
            t = pcfg.get("daily_type") or ""
            r["type"] = t if t in ("reel", "image", "both") else ("reel" if (d.toordinal() % 2 == 0 or r["preset"] == "offer") else "image")
        if r["preset"] == "offer" and not r.get("offer"):
            oi = presets.offer_item(cfg, d)
            r["offer"] = presets.weekly_offer_text(cfg, d, oi)
            if oi and (not have or oi in have):
                r["featured_item"] = oi
                r["idea"] = ""
        item = r.get("featured_item")
        if not item or (have and item not in have):  # sirf asli photo wale items
            rng = random.Random("item" + key)
            r["featured_item"] = rng.choice([m for m in menu if m not in recent[-4:]] or menu)
            r["idea"] = ""  # item badla → idea naya
        recent.append(r["featured_item"])
        r["format"] = r.get("format") or "pinterest"
        if not r.get("idea"):
            todo.append((r, occ))
        cal[key] = r
    if todo:
        _ideas(todo, cfg)
    CP.save_calendar(cal)
    print(f"Calendar: {days} din tayaar ({len(todo)} naye idea)")
    return cal


def _ideas(rows, cfg):
    from . import ai
    spec = [{"date": r["date"], "day": r["day"], "occasion": r.get("occasion"), "hint": "; ".join(o[1] for o in occ if o[1]),
             "type": r["type"], "preset": presets.label(r["preset"]), "item": r["featured_item"], "offer": r.get("offer", "")}
            for r, occ in rows]
    prompt = (
        "You plan Instagram content for BHAVYA CAFE (premium cafe near IIT Roorkee; IIT students + Roorkee locals). "
        "For EACH day write ONE short, specific, fresh post idea (max 14 words, Hinglish ok, no emojis) that fits the "
        "preset, the occasion and the featured item. Classy, witty, never cringe. Never invent discounts — only use the "
        "given offer text if any. Make every idea different.\n"
        f"DAYS: {json.dumps(spec, ensure_ascii=False)}\n"
        'Return JSON: {"ideas": [{"date": "...", "idea": "..."}]}'
    )
    d = ai.text(prompt, cfg, 0.9)
    got = {}
    if isinstance(d, dict):
        for x in d.get("ideas") or []:
            if isinstance(x, dict) and x.get("date") and x.get("idea"):
                got[x["date"]] = str(x["idea"])[:200]
    for r, occ in rows:
        r["idea"] = got.get(r["date"]) or _fallback(r)


def _fallback(r):
    p, it = r["preset"], r["featured_item"]
    return {"offer": f"Offer day: {r.get('offer') or it}", "combo": f"{it} combo for two",
            "visit_now": f"Aaj shaam {it} ke saath Bhavya pe milo", "weekend": f"Weekend plan: friends + {it}",
            "exam": f"Exam break? {it} is the fuel", "festival": f"{r.get('occasion')} ki shubhkamnayein, {it} ke saath",
            "new_item": f"Now serving: {it}", "late_night": f"Late night cravings? {it}"}.get(p, f"{it}, made fresh today")


def today(cfg, date=None):
    from bot import calendar_plan as CP
    date = date or dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date()
    cal = plan(cfg, date, 30)
    return cal.get(date.isoformat()) or {}
