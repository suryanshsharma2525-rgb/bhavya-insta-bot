"""Post presets — POST NOW me choose karo, ya calendar khud din ke hisaab se chunta hai.

offer / combo ka text aap khud likh sakte ho (POST NOW → "offer" box). Na likho to:
  offer → config.yaml ka approved weekly_offer
  combo → menu ke 2 items ka asli total (koi nakli discount nahi)
"""

PRESETS = {
    "auto": ("Auto", ""),
    "offer": ("Offer", "OFFER POST. Show this exact owner-approved offer clearly in the biggest/most prominent text "
                       "blocks (headline / giant_word / offer / price roles): «{offer}». Never change or add to the offer. "
                       "CTA like 'Visit Now' / 'Aaj hi aao'."),
    "combo": ("Combo", "COMBO POST. Show this combo exactly: «{offer}». If it is empty, create ONE combo of the featured "
                       "item + one matching menu item and show their real total (sum of menu prices, no discount). "
                       "Combo name catchy, prices exact."),
    "visit_now": ("Visit Now", "VISIT NOW post: warm invitation to come to the cafe today. Mention near IIT Roorkee"
                               "{hours}. Strong CTA 'Visit Now'."),
    "new_item": ("Naya Item", "NEW ON MENU announcement for the featured item — excitement, 'Now serving'."),
    "weekend": ("Weekend", "WEEKEND SPECIAL vibe — friends, hangout, relax. CTA to plan the weekend at Bhavya."),
    "rainy": ("Baarish", "RAINY DAY / baarish vibe — garma garam, cosy, comfort food."),
    "exam": ("Exam Fuel", "EXAM SEASON for IIT Roorkee students — study-break fuel, relatable, light humour."),
    "festival": ("Tyohaar", "FESTIVAL greeting for {occasion}: warm wishes + the featured item. Respectful, festive."),
    "late_night": ("Late Night", "LATE NIGHT cravings / after-class hunger vibe."),
}


def label(p):
    return PRESETS.get(p or "auto", PRESETS["auto"])[0]


def instruction(preset, cfg, offer="", occasion=""):
    p = PRESETS.get(preset or "auto", PRESETS["auto"])[1]
    if not p:
        return ""
    hours = (cfg.get("brand") or {}).get("hours") or ""
    return p.format(offer=offer or "", occasion=occasion or "festival", hours=(", open " + hours) if hours else "")


def offer_item(cfg, date):
    """Is hafte ka free item — pehle wo jinki asli photo hai (photo aur offer ek hi item ke hon)."""
    from . import photos
    o = cfg.get("weekly_offer") or {}
    items = [i["name"] for i in o.get("free_items", []) if i.get("price", 0) <= o.get("max_item_price", 30)]
    if not items:
        return None
    have = photos.items_with_photos(cfg["menu"])
    with_photo = [i for i in items if i in have]
    pool = with_photo or items
    return pool[date.isocalendar()[1] % len(pool)]


def weekly_offer_text(cfg, date, name=None):
    """config.yaml ka approved weekly offer → ek line."""
    o = cfg.get("weekly_offer") or {}
    if not o.get("enabled", True) or not o.get("free_items"):
        return ""
    name = name or offer_item(cfg, date) or o["free_items"][0]["name"]
    terms = (o.get("terms") or "").strip()
    return f"FREE {name}" + (f" · {terms}" if terms else "")
