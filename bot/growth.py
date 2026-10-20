"""Growth brain — Instagram insights padh ke 'jo chal raha hai uska system' nikaalta hai.

Har post ka DNA: format, design, vibe, colour-wheel harmony, font pack, music mood, item, din, post/reel.
Har DNA-hisse ka 'lift' (average se kitna behtar) nikalta hai → WINNING RECIPE.
- ~35% din (config: growth.exploit_share) = 🔥 WINNER din: recipe follow (same type ka content, naya content)
- baaki ~65% = 🧪 EXPERIMENT: naye formats/designs try (taaki naya winner mile, feed boring na ho)
Gemini top vs bottom posts compare karke likhta hai: kya kaam karta hai, kya avoid karna hai.
"""
import datetime as dt
import json
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERF = os.path.join(ROOT, "data", "performance.json")
FEATURES = ["format", "category", "kind", "design", "vibe", "harmony", "font_pack", "mode", "music_mood", "item", "weekday"]


def load():
    try:
        with open(PERF, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def dna(meta):
    from .formats import ALL_FORMATS
    st = meta.get("style") or {}
    mood = None
    if meta.get("music"):
        try:
            idx = json.load(open(os.path.join(ROOT, "data", "music_index.json"), encoding="utf-8"))
            mood = (idx.get(os.path.basename(meta["music"])) or {}).get("mood")
        except Exception:
            pass
    d = dt.date.fromisoformat(meta["date"])
    return {"format": meta.get("format"), "category": (ALL_FORMATS.get(meta.get("format")) or {}).get("cat"),
            "kind": meta.get("kind"), "design": meta.get("design"), "vibe": st.get("vibe"), "harmony": st.get("harmony"),
            "font_pack": st.get("font_pack"), "mode": st.get("mode"), "music_mood": mood,
            "item": meta.get("featured_item"), "weekday": d.strftime("%A")}


def score(st):
    """Reach + engagement (saves/shares sabse keemti — algorithm inhe sabse zyada push karta hai)."""
    return (st.get("reach", 0) + 0.3 * st.get("views", 0) + 3 * st.get("likes", 0) + 6 * st.get("comments", 0)
            + 10 * st.get("saved", 0) + 12 * st.get("shares", 0))


def quality(st):
    r = max(1, st.get("reach", 0))
    return (st.get("saved", 0) * 3 + st.get("shares", 0) * 3 + st.get("comments", 0) * 2 + st.get("likes", 0)) / r


def learn(rows, cfg):
    """rows = post.json metas jinke paas 'stats' hai. performance.json likhta hai."""
    if not rows:
        return None
    s_avg = sum(score(r["stats"]) for r in rows) / len(rows) or 1
    q_avg = sum(quality(r["stats"]) for r in rows) / len(rows) or 1e-6
    rel = [0.65 * score(r["stats"]) / s_avg + 0.35 * quality(r["stats"]) / q_avg for r in rows]  # 1.0 = average
    # format ka asar bahut bada hota hai — baaki cheezon (item, design, colours...) ko format ke andar compare karo
    by_fmt = {}
    for r, v in zip(rows, rel):
        by_fmt.setdefault(r.get("format"), []).append(v)
    fmt_mean = {k: sum(v) / len(v) for k, v in by_fmt.items()}
    feats = {f: {} for f in FEATURES}
    for r, v in zip(rows, rel):
        resid = v / fmt_mean[r.get("format")] if len(by_fmt[r.get("format")]) >= 2 else v
        for f, val in dna(r).items():
            if val:
                feats[f].setdefault(val, []).append(v if f in ("format", "category", "kind") else resid)
    k = 2.0  # chhote sample pe zyada bharosa nahi (2 post viral = winner nahi)
    lifts = {f: {val: round((sum(vs) / len(vs) - 1) * len(vs) / (len(vs) + k), 3) for val, vs in d.items()}
             for f, d in feats.items()}
    counts = {f: {val: len(vs) for val, vs in d.items()} for f, d in feats.items()}
    recipe = {}
    for f, d in lifts.items():
        good = [(v, l) for v, l in d.items() if l > 0.03 and counts[f][v] >= 2]
        if good:
            recipe[f] = max(good, key=lambda x: x[1])[0]
    ranked = sorted(zip(rows, rel), key=lambda x: -x[1])
    top = [{"post": r.get("_dir"), "rel": round(v, 2), **dna(r), "headline": r.get("headline"),
            "hook": (r.get("caption") or "").split("\n")[0][:140], "link": r.get("permalink"), "stats": r["stats"]}
           for r, v in ranked[:5]]
    bottom = [{"rel": round(v, 2), **dna(r), "headline": r.get("headline"),
               "hook": (r.get("caption") or "").split("\n")[0][:140]} for r, v in ranked[-5:]] if len(ranked) >= 8 else []
    perf = {
        # purane keys (planner/designs inhe padhte hain)
        "formats": lifts["format"], "designs": lifts["design"], "vibes": lifts["vibe"], "kinds": lifts["kind"],
        "features": lifts, "counts": counts, "recipe": recipe, "top_posts": top,
        "updated": dt.date.today().isoformat(), "posts_measured": len(rows),
    }
    notes = _ai_notes(top, bottom, cfg) if len(rows) >= 6 else None
    if notes:
        perf["notes"] = notes
    os.makedirs(os.path.dirname(PERF), exist_ok=True)
    with open(PERF, "w", encoding="utf-8") as fh:
        json.dump(perf, fh, indent=1, ensure_ascii=False)
    print("🔥 Winning recipe:", recipe)
    if notes:
        print("AI growth notes:", notes)
    return perf


def _ai_notes(top, bottom, cfg):
    from . import ai
    prompt = (
        "You are the growth strategist for Bhavya Cafe's Instagram (premium cafe near IIT Roorkee; audience: IIT "
        "students + Roorkee locals). Compare our BEST posts with our WORST and find the SYSTEM behind the winners "
        "(hook style, humour type, format, item, design/colour, timing). Be concrete.\n"
        f"BEST: {json.dumps(top, ensure_ascii=False)}\nWORST: {json.dumps(bottom, ensure_ascii=False)}\n"
        'Return JSON: {"what_works": [3-5 short rules], "avoid": [2-4 short rules], "next_ideas": [3 specific post ideas '
        'that follow the winning system but are NEW content]}'
    )
    d = ai._gemini(prompt, cfg)
    return d if isinstance(d, dict) and d.get("what_works") else None


# ---------------------------------------------------------------- planner hooks
def exploit_share(cfg):
    return float((cfg.get("growth") or {}).get("exploit_share", 0.35))


def is_winner_day(date, cfg, perf=None):
    perf = load() if perf is None else perf
    if not perf.get("recipe"):
        return False
    return random.Random(f"winner-{date.isoformat()}").random() < exploit_share(cfg)


def winner_brief(perf=None):
    """AI prompt ke liye: 'hamare audience ko kya pasand hai'."""
    perf = load() if perf is None else perf
    n = perf.get("notes") or {}
    parts = []
    if n.get("what_works"):
        parts.append("WHAT WORKS FOR OUR AUDIENCE (follow this system, but write NEW content): " + " | ".join(n["what_works"]))
    if perf.get("top_posts"):
        parts.append("OUR TOP POSTS (same TYPE, never copy text): " + " || ".join(
            f"{t.get('format')}/{t.get('item')}: {t.get('headline')}" for t in perf["top_posts"][:3]))
    if n.get("next_ideas"):
        parts.append("Idea seeds: " + " | ".join(n["next_ideas"]))
    return "\n".join(parts)


def avoid_brief(perf=None):
    n = (load() if perf is None else perf).get("notes") or {}
    return ("AVOID (didn't work for us): " + " | ".join(n["avoid"])) if n.get("avoid") else ""
