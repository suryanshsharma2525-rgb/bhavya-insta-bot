"""AI Auditor — publish se pehle har cheez ki quality check.

1) PHOTO AUDIT (library me aane se pehle): HD hai? blur to nahi? sahi dish hai? watermark/logo/text to nahi?
   tasty lag rahi hai? — fail to photo rakhi hi nahi jaati.
2) POST AUDIT (har post/reel ke baad): khana poora dikh raha hai? kahin kata/chhupa/gayab to nahi?
   cut-out saaf hai? text padhne layak + spelling sahi? price menu se match? overall premium lag raha hai?
   Fail → bot naya design/photo leke dobara banata hai (max 2 baar), aur sabse achha version hi post hota hai.

Gemini key na ho to sirf machine checks (resolution, sharpness, layout guard) chalte hain.
Har audit ka record: data/audit_log.csv
"""
import base64
import csv
import datetime as dt
import io
import json
import os
import subprocess

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "data", "audit_log.csv")
PHOTO_CACHE = os.path.join(ROOT, "data", "photo_audit.json")


# ---------------------------------------------------------------- machine checks
def sharpness(im):
    """Laplacian variance (512px grayscale pe). Zyada = zyada sharp. ~100 se kam = blur."""
    g = im.convert("L")
    g.thumbnail((512, 512))
    g = np.asarray(g, np.float32)
    lap = g[1:-1, :-2] + g[1:-1, 2:] + g[:-2, 1:-1] + g[2:, 1:-1] - 4 * g[1:-1, 1:-1]
    return float(lap.var())


def machine_photo_check(im, min_side=900, min_sharp=100.0):
    issues = []
    if min(im.size) < min_side:
        issues.append(f"low resolution {im.size[0]}x{im.size[1]} (HD chahiye, min {min_side}px)")
    sh = sharpness(im)
    if sh < min_sharp:
        issues.append(f"blurry (sharpness {sh:.0f} < {min_sharp:.0f})")
    return issues, sh


# ---------------------------------------------------------------- Gemini vision
def _vision(parts, cfg):
    from . import ai
    d = ai.call(parts, cfg, temperature=0.1, timeout=150)
    return d if isinstance(d, dict) else (d[0] if isinstance(d, list) and d and isinstance(d[0], dict) else None)


def _img_part(im, maxside=1280, q=88):
    im = im.convert("RGB").copy()
    im.thumbnail((maxside, maxside), Image.LANCZOS)
    b = io.BytesIO()
    im.save(b, "JPEG", quality=q)
    return {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(b.getvalue()).decode()}}


def photo_check(im, item, cfg, source="stock"):
    """Library me photo aane se pehle. Return (ok, report)."""
    # AI photos me background jaan-boojh ke soft (bokeh) hota hai → unke liye blur limit kam
    issues, sh = machine_photo_check(im, min_side=820 if source != "ai" else 800,
                                     min_sharp={"ai": 55.0, "stock": 80.0}.get(source, 0.0))
    rep = {"sharpness": round(sh), "issues": issues, "source": source, "ai_checked": False}
    if issues:
        return False, rep
    prompt = (
        "You are the strict photo editor of a PREMIUM cafe's Instagram. Judge this photo for use as a hero food shot of "
        f"'{item}' (Indian cafe menu item).\n"
        "Return JSON: {\"is_item\": true/false (is this clearly that dish or a very close match?), "
        "\"sharp_hd\": true/false (crisp focus on the food, no blur/noise/compression blocks), "
        "\"clean\": true/false (NO watermark, NO logo, NO written text/price tags/stickers, NO other brand's packaging), "
        "\"whole_dish\": true/false (the dish is fully in frame, not cropped awkwardly), "
        "\"appetizing\": 1-10, \"premium_look\": 1-10, \"problems\": [short strings]}"
    )
    d = _vision([{"text": prompt}, _img_part(im, 1024)], cfg)
    if not d:
        return True, rep  # AI nahi chala → sirf machine check (baad me AI se dobara check hogi)
    rep["ai_checked"] = True
    rep.update({k: d.get(k) for k in ("is_item", "sharp_hd", "clean", "whole_dish", "appetizing", "premium_look", "problems")})
    ok = (d.get("is_item") is not False and d.get("sharp_hd") is not False and d.get("clean") is not False
          and (d.get("appetizing") or 0) >= 7 and (d.get("premium_look") or 0) >= 6)
    return ok, rep


def _photo_cache():
    try:
        return json.load(open(PHOTO_CACHE, encoding="utf-8"))
    except Exception:
        return {}


def remember_photo(path, ok, rep):
    c = _photo_cache()
    c[os.path.relpath(path, ROOT)] = {"ok": ok, **{k: v for k, v in rep.items() if k != "source"}}
    os.makedirs(os.path.dirname(PHOTO_CACHE), exist_ok=True)
    json.dump(c, open(PHOTO_CACHE, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


def audit_library(cfg, delete_bad=True):
    """Pehle se pade stock/AI photos ek baar check karo. Kharab wale hata do (aapki asli photos kabhi delete nahi hoti)."""
    from . import photos as P
    cache = _photo_cache()
    removed = flagged = 0
    ai_budget = int(cfg.get("audit", {}).get("library_ai_per_run", 20))  # free limit bachao: ek run me itni hi
    for folder, src in ((P.STOCK_DIR, "stock"), (P.AI_DIR, "ai"), (P.REAL_DIR, "real")):
        if not os.path.isdir(folder):
            continue
        for f in sorted(os.listdir(folder)):
            if not f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                continue
            path = os.path.join(folder, f)
            rel = os.path.relpath(path, ROOT)
            if rel in cache:
                continue
            if ai_budget <= 0:
                break
            item = P.item_from_file(f, cfg)
            ok, rep = photo_check(Image.open(path).convert("RGB"), item, cfg, src)
            if rep.get("ai_checked"):
                ai_budget -= 1
                remember_photo(path, ok, rep)  # sirf poori tarah check hui photo yaad rakho
            elif ok:
                continue  # AI busy tha → agle run me check hogi
            if ok:
                continue
            if src == "real":
                flagged += 1
                print(f"⚠️ Aapki photo {rel} weak hai: {rep.get('issues') or rep.get('problems')} (delete nahi ki)")
            elif delete_bad:
                os.remove(path)
                removed += 1
                print(f"Auditor ne hatayi: {rel} → {rep.get('issues') or rep.get('problems')}")
    print(f"Photo audit: {removed} hataayi, {flagged} asli photos weak")
    return removed


# ---------------------------------------------------------------- post / reel audit
def video_sheet(video, out_jpg, n=6):
    from . import render as R
    dur = 15.0
    try:
        o = subprocess.run([R.ffmpeg_bin(), "-i", video], capture_output=True, text=True).stderr
        import re
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", o)
        if m:
            dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        pass
    frames = []
    for k in range(n):
        t = dur * (0.12 + 0.76 * k / max(1, n - 1))
        raw = subprocess.run([R.ffmpeg_bin(), "-v", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                              "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
        if raw:
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            im.thumbnail((432, 768))
            frames.append(im)
    if not frames:
        return None
    w, h = frames[0].size
    cols = 3
    sheet = Image.new("RGB", (w * cols, h * ((len(frames) + cols - 1) // cols)), (0, 0, 0))
    for i, f in enumerate(frames):
        sheet.paste(f, ((i % cols) * w, (i // cols) * h))
    sheet.save(out_jpg, quality=88)
    return out_jpg


def post_check(out_dir, meta, cfg, guard_log=None):
    """Final post ko designer ki nazar se dekho. Return dict(ok, score, issues, source)."""
    guard_log = guard_log or []
    machine = []
    for rep in guard_log:
        for r in rep:
            a = r.get("after", {})
            if a.get("occluded", 0) > 0.05:
                machine.append(f"dish {int(a['occluded'] * 100)}% dhaki hui (layout)")
            if a.get("outside", 0) > 0.04:
                machine.append(f"dish {int(a['outside'] * 100)}% frame se bahar")
    files = meta.get("files") or []
    if meta.get("kind") == "reel":
        img_path = video_sheet(os.path.join(out_dir, "reel.mp4"), os.path.join(out_dir, "_audit_sheet.jpg"))
        what = "an Instagram REEL (contact sheet of frames in time order, mid-animation frames may look partial)"
    else:
        img_path = os.path.join(out_dir, files[0]) if files else None
        what = "an Instagram post (4:5)"
    rep = {"ok": not machine, "score": None, "issues": machine, "source": "machine"}
    if not img_path or not os.path.exists(img_path):
        return rep
    im = Image.open(img_path).convert("RGB")
    if meta.get("kind") != "reel":
        _, sh = machine_photo_check(im, 0, 0)
        if sh < 50:
            rep["issues"].append(f"poora post blurry lag raha hai (sharpness {sh:.0f})")
    menu = {m["name"]: m.get("price") for m in cfg["menu"]}
    prompt = (
        f"You are the creative director auditing {what} for BHAVYA CAFE, a premium cafe near IIT Roorkee. "
        "Be strict — only truly professional, appetizing work may be published.\n"
        f"Featured item: {meta.get('featured_item')}\nCorrect menu prices: {json.dumps(menu, ensure_ascii=False)}\n"
        "Check:\n"
        "1. FOOD FULLY VISIBLE: is every dish/drink shown completely? FAIL if any part is cut off by the frame edge, hidden "
        "behind a text box/panel/badge, missing/see-through/holes (bad background removal), or text sits on top of the food.\n"
        "2. CUT-OUT QUALITY: clean edges, no leftover background chunks, no missing pieces of glass/plate.\n"
        "3. PHOTO QUALITY: sharp, HD, appetizing, correct dish for its label, no watermark or other brand's logo/text.\n"
        "4. TEXT: readable contrast, no overlapping texts, nothing cut at the edges, spelling correct, prices match the menu.\n"
        "5. DESIGN: balanced, premium, on-brand. Not cluttered.\n"
        "Return JSON: {\"food_fully_visible\": bool, \"cutout_clean\": bool, \"photo_quality\": 1-10, \"text_ok\": bool, "
        "\"prices_ok\": bool, \"design\": 1-10, \"overall\": 1-10, \"issues\": [short specific strings, which frame/where]}"
    )
    d = _vision([{"text": prompt}, _img_part(im, 1536)], cfg)
    if d:
        rep["source"] = "gemini+machine"
        rep["score"] = d.get("overall")
        rep["issues"] += [str(x) for x in (d.get("issues") or [])][:8]
        rep["detail"] = {k: d.get(k) for k in ("food_fully_visible", "cutout_clean", "photo_quality", "text_ok",
                                                 "prices_ok", "design", "overall")}
        min_score = cfg.get("audit", {}).get("min_score", 7)
        rep["ok"] = (not machine and d.get("food_fully_visible") is not False and d.get("cutout_clean") is not False
                     and d.get("text_ok") is not False and d.get("prices_ok") is not False
                     and (d.get("photo_quality") or 0) >= 6 and (d.get("overall") or 0) >= min_score)
    return rep


def log(post_name, attempt, meta, rep):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["time", "post", "attempt", "format", "design", "item", "ok", "score", "issues"])
        w.writerow([dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M"), post_name, attempt, meta.get("format"),
                    meta.get("design"), meta.get("featured_item"), rep.get("ok"), rep.get("score"),
                    " | ".join(rep.get("issues") or [])[:500]])
