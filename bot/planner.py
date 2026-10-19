"""Decides which format goes on which day. Formats rotate every week so the page never feels repetitive."""
import csv
import datetime as dt
import io
import random

import requests

from .formats import FORMATS

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _pool(year):
    pool = sorted(FORMATS)
    random.Random(f"bhavya-{year}").shuffle(pool)
    return pool


def week_plan(date, cfg, has_trend=False):
    """Returns {weekday_name: format_key} for the ISO week containing `date`."""
    year, week, _ = date.isocalendar()
    offer = cfg.get("weekly_offer", {})
    offer_day = offer.get("weekday", "Wednesday") if offer.get("enabled", True) else None
    normal_days = [d for d in DAYS if d != offer_day]

    pool = _pool(year)
    if not has_trend:
        pool = [p for p in pool if not FORMATS[p].get("needs_trend")]
    n = len(normal_days)
    start = (week * n) % len(pool)
    picks = [pool[(start + i) % len(pool)] for i in range(n)]

    plan = dict(zip(normal_days, picks))
    if has_trend and "trend_twist" not in picks:
        plan[normal_days[-2]] = "trend_twist"  # Saturday-ish: trend post gets the weekend reach
    if offer_day:
        plan[offer_day] = "offer_flash_reel" if week % 2 else "offer_zoom_code"
    return {d: plan[d] for d in DAYS}


def offer_item(date, cfg):
    """Free item of the week (rotates; never above max_item_price)."""
    o = cfg["weekly_offer"]
    items = [i for i in o["free_items"] if i["price"] <= o.get("max_item_price", 30)]
    if not items:
        raise SystemExit("config.yaml: weekly_offer.free_items me koi ₹30 tak ka item nahi hai.")
    _, week, _ = date.isocalendar()
    return items[week % len(items)], items


def recent_trends(cfg, today):
    url = cfg.get("trend_sheet_csv_url")
    if not url:
        return []
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    except Exception as e:  # sheet down → just skip trends
        print("Trend sheet read failed:", e)
        return []
    out = []
    for row in rows:
        if len(row) < 2 or not row[1].strip():
            continue
        try:
            d = dt.date.fromisoformat(row[0].strip())
        except ValueError:
            continue  # header or bad date
        if 0 <= (today - d).days <= 14:
            out.append(row[1].strip())
    return out[-5:]
