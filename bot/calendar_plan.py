"""Content calendar + upload log.

data/content_calendar.csv  – aage ke 30 din ka plan (date, occasion, format, item, idea, status, link)
data/content_calendar.ics  – wahi plan Google Calendar / phone calendar ke liye
data/posts_log.csv         – jo-jo upload hua uska record
data/occasions.csv         – tyohaar, IITR exams/holidays (tum isme apni dates jod sakte ho)
"""
import csv
import datetime as dt
import json
import os
import random

from . import ai
from .formats import ALL_FORMATS, FORMATS
from . import planner

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CAL_CSV = os.path.join(DATA, "content_calendar.csv")
CAL_ICS = os.path.join(DATA, "content_calendar.ics")
LOG_CSV = os.path.join(DATA, "posts_log.csv")
OCC_CSV = os.path.join(DATA, "occasions.csv")

CAL_COLS = ["date", "day", "occasion", "type", "preset", "offer", "featured_item", "idea", "strategy", "format", "status",
            "instagram_link"]
LOG_COLS = ["post_id", "date", "time_ist", "source", "format", "type", "featured_item", "headline",
            "caption_first_line", "hashtags", "owner_note", "status", "instagram_link",
            "reach", "views", "likes", "comments", "saved", "shares"]

FORMAT_LABEL = {
    "meme_card": "Meme", "relatable_exam": "Exam/IIT life meme", "local_roorkee": "Roorkee local meme",
    "trend_twist": "Trend meme", "versus": "Mess vs Bhavya", "comment_battle": "A ya B battle",
    "tag_friend": "Tag your friend", "rate_combo": "Rate the combo", "weekend_plan": "Weekend checklist",
    "spot_difference": "Spot the difference", "hidden_item": "Odd one dhundo", "count_items": "Momos gino",
    "zoom_read": "Zoom karke padho", "swipe_twist": "Swipe-till-end carousel", "this_or_that": "This or That",
    "offer_flash_reel": "OFFER: Pause karo reel", "offer_zoom_code": "OFFER: Zoom code",
    "reel_meme": "Meme reel", "reel_pov": "POV reel", "reel_top5": "Top 5 reel", "reel_this_or_that": "This or That reel",
    "reel_pause_game": "Pause game reel", "reel_freestyle": "AI concept reel (new idea)", "reel_showcase": "Cinematic food reel",
    "product_spotlight": "Product spotlight", "poster": "Designer poster (reference style)",
    "poster_reel": "Designer poster reel (reference style)", "mood_quote": "Mood / aesthetic post", "fact_carousel": "Did-you-know carousel",
}
# occasions pe kaunse formats best hain
FESTIVE = ["poster", "poster_reel", "reel_showcase", "product_spotlight", "mood_quote", "reel_freestyle", "local_roorkee", "tag_friend", "reel_pov"]
EXAM = ["poster", "poster_reel", "relatable_exam", "reel_pov", "reel_top5", "mood_quote", "zoom_read", "reel_freestyle", "product_spotlight"]


# ---------------------------------------------------------------- csv helpers
def _read(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _write(path, rows, cols):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:  # utf-8-sig → Excel me emoji/₹ sahi dikhte hain
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def occasions_on(date):
    out = []
    for r in _read(OCC_CSV):
        try:
            s = dt.date.fromisoformat(r["start"].strip())
            e = dt.date.fromisoformat((r.get("end") or r["start"]).strip())
        except (ValueError, KeyError):
            continue
        if s <= date <= e:
            out.append((r["occasion"].strip(), (r.get("hint") or "").strip()))
    return out


# ---------------------------------------------------------------- calendar
def load_calendar():
    return {r["date"]: r for r in _read(CAL_CSV)}


def save_calendar(cal):
    rows = [cal[k] for k in sorted(cal)]
    _write(CAL_CSV, rows, CAL_COLS)
    _write_ics(rows)


def plan_calendar(cfg, start, days=30):
    """Aage ke din plan karo. Jo din pehle se plan hain (ya tumne edit kiye) unhe chhoda jaata hai."""
    from . import growth
    gperf = growth.load()
    cal = load_calendar()
    menu = [m["name"] for m in cfg["menu"]]
    recent_items = [r.get("featured_item") for k, r in sorted(cal.items())][-10:]
    new = []
    for i in range(days):
        d = start + dt.timedelta(days=i)
        key = d.isoformat()
        if key in cal:
            continue
        occ = occasions_on(d)
        fmt = planner.week_plan(d, cfg)[d.strftime("%A")]
        names = " ".join(o[0].lower() for o in occ)
        prev = cal.get((d - dt.timedelta(days=1)).isoformat(), {}).get("format")
        if not fmt.startswith("offer_") and occ:
            pool = EXAM if "exam" in names else FESTIVE
            if fmt not in pool or fmt == prev:
                fmt = random.Random(key).choice([p for p in pool if p != prev])
        elif fmt == prev and not fmt.startswith("offer_"):
            fmt = random.Random(key).choice([p for p in FORMATS if p != prev and not FORMATS[p].get("needs_trend")])
        rng = random.Random("item" + key)
        item = rng.choice([m for m in menu if m not in recent_items] or menu)
        win = growth.is_winner_day(d, cfg, gperf)
        rec = gperf.get("recipe", {})
        if win and rec.get("item") in menu and rec["item"] not in recent_items[-3:]:
            item = rec["item"]
        if fmt.startswith("offer_"):
            item, _ = planner.offer_item(d, cfg)
            item = item["name"]
        recent_items = (recent_items + [item])[-10:]
        row = {"date": key, "day": d.strftime("%a"), "occasion": " + ".join(o[0] for o in occ),
               "strategy": "🔥 winner" if win else "🧪 experiment",
               "format": fmt, "featured_item": item, "idea": "", "status": "planned", "instagram_link": "",
               "_hints": "; ".join(o[1] for o in occ if o[1])}
        cal[key] = row
        new.append(row)
    if new:
        _fill_ideas(new, cfg)
        for r in new:
            r.pop("_hints", None)
    save_calendar(cal)
    print(f"Calendar: {len(new)} naye din plan kiye, total {len(cal)} din.")
    return cal


def _fill_ideas(rows, cfg):
    """Gemini se har din ka idea (batch me, ek hi call). Key na ho to simple template idea."""
    menu = ", ".join(f"{m['name']} (₹{m['price']})" for m in cfg["menu"] if m.get("price"))
    spec = [{"date": r["date"], "day": r["day"], "occasion": r["occasion"], "occasion_hint": r["_hints"],
             "format": r["format"], "format_hint": ALL_FORMATS[r["format"]]["hint"], "featured_item": r["featured_item"],
             "strategy": r.get("strategy", "")}
            for r in rows]
    from . import growth
    gp = growth.load()
    brief = growth.winner_brief(gp)
    brief = ("\n\nFor days with strategy '🔥 winner' follow this proven system (new content, same type):\n" + brief +
             "\nFor '🧪 experiment' days try something genuinely new. " + growth.avoid_brief(gp)) if brief else ""
    prompt = (ai.STYLE_RULES + f"\n\nMENU: {menu}\n\nYou are planning the Instagram content calendar. For EACH day below "
              "write one specific, funny, ready-to-execute post idea in Hinglish (max 25 words) that fits the format, "
              "the occasion (if any) and features the item. Think like a viral Indian meme page for IIT Roorkee students "
              "and Roorkee locals. During UG winter vacation target locals and families. Make every idea different." + brief + "\n\n"
              "DAYS:\n" + json.dumps(spec, ensure_ascii=False, indent=1) +
              '\n\nReturn ONLY JSON: {"ideas": [{"date": "...", "idea": "..."}]}')
    data = ai._gemini(prompt, cfg)
    ideas = {}
    if isinstance(data, dict):
        for x in data.get("ideas", []):
            if isinstance(x, dict) and x.get("date") and x.get("idea"):
                ideas[x["date"]] = ai.strip_emoji(str(x["idea"]))[:300]
    for r in rows:
        if r["date"] in ideas:
            r["idea"] = ideas[r["date"]]
        else:
            base = FORMAT_LABEL[r["format"]]
            r["idea"] = (f"{r['occasion']} special: " if r["occasion"] else "") + f"{base} featuring {r['featured_item']}"


def today_plan(date, cfg):
    """Daily post ke liye aaj ki row (format, idea, item). Tumhare edits yahin se lagte hain."""
    r = load_calendar().get(date.isoformat())
    if not r or r.get("status") == "posted":
        return None
    fmt = (r.get("format") or "").strip()
    if fmt not in ALL_FORMATS:
        fmt = None
    items = {m["name"].lower(): m["name"] for m in cfg["menu"]}
    item = items.get((r.get("featured_item") or "").strip().lower())
    occ = r.get("occasion") or ""
    idea = (r.get("idea") or "").strip()
    if occ:
        idea = f"[{occ}] {idea}"
    return {"format": fmt, "idea": idea or None, "item": item}


def mark_posted(date_key, link):
    cal = load_calendar()
    if date_key in cal:
        cal[date_key]["status"] = "posted"
        cal[date_key]["instagram_link"] = link or ""
        save_calendar(cal)


def _ics_escape(s):
    return str(s).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _write_ics(rows):
    now = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Bhavya Cafe//Insta Bot//EN", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", "X-WR-CALNAME:Bhavya Cafe – Instagram Plan", "X-WR-TIMEZONE:Asia/Kolkata"]
    for r in rows:
        d = dt.date.fromisoformat(r["date"])
        tick = ("✅ " if r.get("status") == "posted" else "📸 ") + ("🔥 " if "winner" in (r.get("strategy") or "") else "")
        if r.get("type"):  # naya Pinterest-design system: Reel/Post + preset
            kind = "🎬 Reel" if r["type"] == "reel" else ("🎬+🖼 Dono" if r["type"] == "both" else "🖼 Post")
            pre = (r.get("preset") or "auto").replace("_", " ").title()
            title = tick + f"{kind} · {pre} – {r.get('featured_item', '')}"
        else:
            title = tick + FORMAT_LABEL.get(r.get("format"), r.get("format", "Post")) + f" – {r.get('featured_item', '')}"
        if r.get("occasion"):
            title += f" ({r['occasion']})"
        desc = f"Idea: {r.get('idea', '')}\nStatus: {r.get('status', '')}" + (f"\nOffer: {r['offer']}" if r.get("offer") else "")
        if r.get("instagram_link"):
            desc += f"\nPost: {r['instagram_link']}"
        lines += ["BEGIN:VEVENT", f"UID:bhavya-{r['date']}@instabot", f"DTSTAMP:{now}",
                  f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{d + dt.timedelta(days=1):%Y%m%d}",
                  f"SUMMARY:{_ics_escape(title)}", f"DESCRIPTION:{_ics_escape(desc)}", "TRANSP:TRANSPARENT",
                  "END:VEVENT"]
    lines.append("END:VCALENDAR")
    with open(CAL_ICS, "w", encoding="utf-8", newline="") as fh:
        fh.write("\r\n".join(lines) + "\r\n")


# ---------------------------------------------------------------- upload log
def log_post(post_id, meta, source, status, link=""):
    rows = _read(LOG_CSV)
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))
    row = next((r for r in rows if r["post_id"] == post_id), None)
    if row is None:
        row = {"post_id": post_id, "date": meta["date"], "time_ist": now.strftime("%H:%M"), "source": source,
               "format": FORMAT_LABEL.get(meta["format"], meta["format"]), "type": meta["kind"],
               "featured_item": meta.get("featured_item", ""), "headline": meta["headline"],
               "caption_first_line": meta["caption"].split("\n")[0],
               "hashtags": meta["caption"].strip().split("\n")[-1], "owner_note": meta.get("owner_note", "")}
        rows.append(row)
    row["status"] = status
    if link:
        row["instagram_link"] = link
        row["time_ist"] = now.strftime("%H:%M")
    _write(LOG_CSV, rows, LOG_COLS)


def log_stats(post_id, st):
    rows = _read(LOG_CSV)
    for r in rows:
        if r["post_id"] == post_id:
            for k in ("reach", "views", "likes", "comments", "saved", "shares"):
                if k in st:
                    r[k] = st[k]
    _write(LOG_CSV, rows, LOG_COLS)
