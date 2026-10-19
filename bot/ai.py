"""Writes the post text with Gemini (free API). Falls back to a built-in sample bank if no key / API error."""
import json
import os
import random
import re

import requests

from .formats import ALL_FORMATS

STYLE_RULES = """
You are the social media voice of Bhavya Cafe, a cafe near IIT Roorkee (Uttarakhand, India).
Audience: IIT Roorkee students + nearby college students + Roorkee locals (18-28).

VOICE
- Write in natural Hinglish (Roman script), like a funny friend from the hostel, NOT like an ad.
- Desi meme energy: short, punchy, relatable, a little dramatic. Think viral Indian Instagram meme pages.
- Use real student/local life: end-sems, quizzes, attendance, placements, internships, assignments at 11:59 PM,
  hostel mess, late-night hunger, Roorkee ki thand, monsoon, Ganga canal, Haridwar/Dehradun trips, going home on holidays,
  fests, cricket matches, budget at month-end.
- Only use items from the MENU, with their EXACT names. Never invent items or prices; if you mention a price, use the MENU price.

HARD RULES (never break)
- Never make fun of any person, professor, branch, college, state, religion, caste, gender, body or language.
  Self-roast of "student life" is fine. Never name real people.
- No politics, no religion, no double-meaning / adult jokes, no alcohol/smoking.
- Never claim things about IIT Roorkee as an institution (no fake events, no logos).
- On-image text: NO emojis, NO hashtags. Keep it short — it must be readable on a phone in 1 second.
- Do not repeat any joke from RECENT POSTS.

SEO (very important — Instagram search works on keywords)
- "caption_hook" = first caption line, max 12 words, MUST contain the word "Roorkee" and one food keyword
  (e.g. "Best momos in Roorkee near IIT?"), plus 1-2 emojis.
- "caption_body" = 1-3 short lines continuing the joke (emojis ok).
- "cta" = one line that makes people COMMENT, SAVE, SHARE or TAG (questions work best).
- "alt_text" = plain description of the image incl. "Bhavya Cafe Roorkee".
- "extra_hashtags" = exactly 2 picked from the allowed list.
"""

SAMPLES = {
    "meme_card": {"top": "Budget bola sirf ek chai peeni hai", "bottom": "5 min baad: 2 vada pav, 1 cold coffee, 1 momos",
                  "item": "Vada Pav", "caption_hook": "Roorkee me budget plan vs Bhavya ke Vada Pav 🍔😭",
                  "caption_body": "Har mahine ki 20 tareekh ke baad wali feeling 🥲", "cta": "Comment karo: tumhara budget kab tak chalta hai? 👇"},
    "relatable_exam": {"top": "Syllabus: 12 chapters. Dimaag: 0 chapters", "bottom": "Cold coffee: 3 glass. Priorities set hai",
                       "item": "Cold Coffee", "caption_hook": "End-sem season in Roorkee = cold coffee season 🧋📚",
                       "caption_body": "Padhai baad me, pehle caffeine ☕", "cta": "Save karo, exam ke time kaam aayega 😌"},
    "local_roorkee": {"top": "Roorkee ki thand me 2 cheezein garam milti hain", "bottom": "Ek mummy ka gussa, doosri Bhavya ki coffee",
                      "item": "Hot Coffee", "caption_hook": "Roorkee winters + hot coffee near IIT = perfect combo ☕❄️",
                      "caption_body": "Blanket se bahar nikalne ka ek hi reason 🫣", "cta": "Tag karo us dost ko jo har saal bolta hai 'is baar thand kam hai' 😂"},
    "trend_twist": {"top": "2 kachori 1 samosa wala mood", "bottom": "Roorkee version: 2 momos 1 cold coffee",
                    "item": "Veg Momos", "caption_hook": "Roorkee wala trend version, momos ke saath 🥟🔥",
                    "caption_body": "Trend pe chalna zaroori hai, bhook pe bhi 😋", "cta": "Comment karo apna combo 👇"},
    "versus": {"headline": "Hostel dinner vs Bhavya dinner", "left_title": "Mess", "left_line": "Daal ya paani? Aaj bhi pata nahi",
               "left_emoji": "😐", "right_title": "Bhavya", "right_line": "Kulhad Pizza jo dil jod de", "right_item": "Kulhad Pizza",
               "caption_hook": "Mess vs Kulhad Pizza in Roorkee, no contest 🍕🔥", "caption_body": "Mess ne dil toda, hum jod denge 💛",
               "cta": "Share karo apne hostel group me 😂"},
    "comment_battle": {"question": "Raat ke 9 baje ki bhook. Kaun jeetega?", "a_item": "Veg Momos", "a_line": "Garam, juicy, chutney ke saath",
                       "b_item": "Vada Pav", "b_line": "Desi swag, pocket friendly", "caption_hook": "Momos vs Vada Pav, Roorkee decide karega 🥟🆚🍔",
                       "caption_body": "Aaj comments me final hoga 🔥", "cta": "Comment karo A ya B 👇 (majority wala item next week special!)"},
    "tag_friend": {"line": "jo bolta hai bas ek coffee, phir 3 ghante baith jaata hai", "item": "Cold Coffee",
                   "caption_hook": "Roorkee ka har group me ek aisa dost hota hai ☕⏳",
                   "caption_body": "Aur wahi bill ke time washroom chala jaata hai 🫠", "cta": "Tag karo usko abhi 👇"},
    "rate_combo": {"combo_name": "Post-Viva Recovery Kit", "items": ["Potato Twister", "Cold Coffee", "Kesar Pista Kheer"],
                   "line": "Viva me jo bhi hua, yahan sab theek ho jaayega", "caption_hook": "Best student combo in Roorkee? Rate karo 🌪️🧋🍮",
                   "caption_body": "Doctor ne nahi, seniors ne prescribe kiya hai 😌", "cta": "1 se 10 me rate karo comments me 👇"},
    "weekend_plan": {"headline": "Weekend plan", "checklist": ["Assignment khatam karna", "Gym jaana", "Ghar call karna", "Bhavya pe Veg Momos"],
                     "done": [False, False, False, True], "caption_hook": "Roorkee weekend plans be like 🥟✅",
                     "caption_body": "Ek kaam to poora hua na 😎", "cta": "Comment karo, tumhara kitna ✅ hua? 👇"},
    "spot_difference": {"headline": "3 difference dhundo", "caption_hook": "Roorkee ke sabse sharp aankh wale kahan hain? 🔍🍕",
                        "caption_body": "Dono plate same dikh rahi hain... par hain nahi 👀", "cta": "Zoom karo aur comment me batao 👇"},
    "hidden_item": {"headline": "Odd one dhundo", "caption_hook": "Sirf IIT Roorkee wale 10 sec me dhundh payenge 🔍🥟",
                    "caption_body": "Hold karo, zoom karo, dhundo 👀", "cta": "Kitne second lage? Comment karo ⏱️"},
    "count_items": {"headline": "Kitne momos hain?", "caption_hook": "Momos counting challenge, Roorkee edition 🥟🔢",
                    "caption_body": "Galat answer = treat dena padega 😂", "cta": "Answer comment karo 👇 sahi answer kal story pe"},
    "zoom_read": {"headline": "Zoom karke padho", "hidden_message": "Padhai chhodo, momos khane chalo",
                  "caption_hook": "Roorkee walo, zoom karo, ek secret message hai 🔍☕",
                  "caption_body": "Mile to comment me likho 🤫", "cta": "Jo pehle dhundega, uska naam story pe 👑"},
    "swipe_twist": {"slides": [{"big": "Raat ke 11 baje", "small": "Assignment kal submit karna hai"},
                               {"big": "Laptop on", "small": "Word file khuli, ek line likhi"},
                               {"big": "Pet ne awaaz di", "small": "Dimaag bola: focus. Pet bola: momos"},
                               {"big": "Final decision", "small": "Assignment kal dekhenge. Bhavya chalo"}],
                    "caption_hook": "Every IIT Roorkee student at 11 PM, last slide is the truth 🥟😅",
                    "caption_body": "Swipe karo end tak 👉", "cta": "Share karo us dost ko jo aaj bhi assignment pending rakh ke baitha hai 😂"},
    "this_or_that": {"pairs": [{"a": "8 AM class", "a_emoji": "😴", "b": "Sunday ka nashta", "b_emoji": "🍳"},
                               {"a": "Cold Coffee", "a_emoji": "🧋", "b": "Hot Coffee", "b_emoji": "☕"},
                               {"a": "Veg Momos", "a_emoji": "🥟", "b": "Kulhad Pizza", "b_emoji": "🍕"}],
                     "caption_hook": "This or That, Roorkee food edition 🥟☕", "caption_body": "Swipe karo aur choose karo 👉",
                     "cta": "Comment karo apne answers jaise: A B A 👇"},
    "offer_flash_reel": {"headline": "Pause karo, jo aaye wo FREE", "caption_hook": "Roorkee walo, free food ka mauka 🎁🔥",
                         "caption_body": "Reel PAUSE karo, screenshot lo, counter pe dikhao. Jo item aaya, wo FREE 😍",
                         "cta": "Tag karo us dost ko jiske saath aaoge 👇"},
    "offer_zoom_code": {"headline": "Hidden code dhundo", "caption_hook": "Free food in Roorkee? Zoom karo, code dhundo 🔍🎁",
                        "caption_body": "Image me ek secret code chhupa hai. Dhundo aur counter pe dikhao 😍",
                        "cta": "Save karo aur dost ko bhejo 👇"},
}

EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]+")


def strip_emoji(s):
    return EMOJI_RE.sub("", s or "").strip()


def _prompt(fmt_key, cfg, ctx):
    f = ALL_FORMATS[fmt_key]
    menu = ", ".join(f"{m['name']} (₹{m['price']})" if m.get("price") else m["name"] for m in cfg["menu"])
    fields = dict(f["fields"])
    fields.update({"caption_hook": "see SEO rules", "caption_body": "see SEO rules", "cta": "see SEO rules",
                   "alt_text": "see SEO rules", "extra_hashtags": "list of exactly 2"})
    parts = [STYLE_RULES,
             f"MENU: {menu}",
             f"ALLOWED extra_hashtags: {', '.join(cfg['hashtags']['rotate'])}",
             f"TODAY: {ctx['date']:%A, %d %B %Y}. Use the season/day if it helps the joke.",
             f"FORMAT: {fmt_key} — {f['hint']}",
             f"WEEK NUMBER {ctx['week']}: give this format a fresh angle different from earlier weeks."]
    if ctx.get("trends"):
        parts.append("CURRENT TRENDS (from the owner, newest last): " + " | ".join(ctx["trends"]))
    if ctx.get("offer_item"):
        it = ctx["offer_item"]
        parts.append(f"THIS WEEK'S OFFER: free {it['name']} (worth ₹{it['price']}). Terms: {cfg['weekly_offer']['terms']}. "
                     "Mention the offer and terms in caption_body.")
    if ctx.get("idea"):
        parts.append("OWNER'S IDEA FOR THIS POST (follow it closely, keep the same style rules): " + ctx["idea"])
    if ctx.get("focus_item"):
        parts.append(f"FEATURE THIS MENU ITEM in the post: {ctx['focus_item']}")
    if ctx.get("recent"):
        parts.append("RECENT POSTS (do not repeat): " + " || ".join(ctx["recent"][-30:]))
    parts.append("Return ONLY a JSON object with these keys:\n" + json.dumps(fields, ensure_ascii=False, indent=1))
    return "\n\n".join(parts)


def _gemini(prompt, cfg):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    model = cfg.get("ai", {}).get("model", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 1.0}}
    for attempt in range(3):
        try:
            r = requests.post(url, params={"key": key}, json=body, timeout=90)
            r.raise_for_status()
            txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(txt)
        except Exception as e:
            print(f"Gemini attempt {attempt + 1} failed: {e}")
    return None


def write_post(fmt_key, cfg, ctx):
    data = _gemini(_prompt(fmt_key, cfg, ctx), cfg)
    source = "gemini"
    if not data or not _valid(fmt_key, data, cfg):
        print("Using built-in sample text for", fmt_key)
        data = json.loads(json.dumps(SAMPLES[fmt_key], ensure_ascii=False))
        source = "sample"
    data["_source"] = source
    return _finalise(fmt_key, data, cfg, ctx)


def _valid(fmt_key, d, cfg):
    names = {m["name"].lower() for m in cfg["menu"]}
    need = list(ALL_FORMATS[fmt_key]["fields"]) + ["caption_hook", "caption_body", "cta"]
    if any(k not in d or d[k] in ("", None, []) for k in need):
        return False
    for k in ("item", "a_item", "b_item", "right_item"):
        if k in d and str(d[k]).lower() not in names:
            return False
    if "items" in d and any(str(i).lower() not in names for i in d["items"]):
        return False
    if fmt_key == "swipe_twist" and len(d["slides"]) < 3:
        return False
    if fmt_key == "this_or_that" and len(d["pairs"]) < 2:
        return False
    if fmt_key == "weekend_plan" and len(d.get("done", [])) != len(d["checklist"]):
        d["done"] = [False] * (len(d["checklist"]) - 1) + [True]
    return True


def _finalise(fmt_key, d, cfg, ctx):
    # on-image text must have no emojis
    for k in ("top", "bottom", "headline", "line", "question", "a_line", "b_line", "left_title", "left_line",
              "right_title", "right_line", "combo_name", "hidden_message"):
        if k in d:
            d[k] = strip_emoji(d[k])
    for s in d.get("slides", []):
        s["big"], s["small"] = strip_emoji(s.get("big")), strip_emoji(s.get("small"))
    d["checklist"] = [strip_emoji(x) for x in d.get("checklist", [])] or d.get("checklist")

    hook = d["caption_hook"].strip()
    if "roorkee" not in hook.lower():
        hook += " | Roorkee"
    allowed = cfg["hashtags"]["rotate"]
    extra = [h if h.startswith("#") else "#" + h for h in d.get("extra_hashtags", [])]
    extra = [h for h in extra if h in allowed][:2]
    while len(extra) < 2:
        extra.append(random.choice([h for h in allowed if h not in extra]))
    tags = cfg["hashtags"]["always"][:3] + extra
    d["hashtags"] = tags
    d["alt_text"] = d.get("alt_text") or f"{fmt_key.replace('_', ' ')} post by Bhavya Cafe Roorkee"
    if "roorkee" not in d["alt_text"].lower():
        d["alt_text"] += " – Bhavya Cafe Roorkee"
    d["caption"] = "\n\n".join([hook, d["caption_body"].strip(), d["cta"].strip(),
                                cfg["brand"]["location_line"], " ".join(tags)])
    return d
