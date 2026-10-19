"""Animated vertical reels (1080x1920) in the Bhavya black-gold theme.

Har reel = scenes ki list. Har scene ek function hai jo (t = 0..1 progress) pe ek frame banata hai.
Frames → ffmpeg → mp4 (+ assets/music ka random gaana).
"""
import glob
import os
import random
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw

from . import render as R

W, H = 1080, 1920
FPS = 24


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _bg(footer="Near IIT Roorkee"):
    return R.canvas(W, H, footer=footer)


def text_layer(s, kind, box, gold=False, fill=None, start=110, minimum=40):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    R.block(layer, s, kind, box, gold=gold, fill=fill, start=start, minimum=minimum)
    return layer


def put(frame, layer, alpha=1.0, dy=0, scale=None):
    """Layer ko frame pe chipkao, fade (alpha) aur slide (dy) ke saath."""
    if alpha <= 0:
        return
    l = layer
    if alpha < 1:
        l = layer.copy()
        l.putalpha(l.split()[3].point(lambda v: int(v * alpha)))
    if dy:
        moved = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        moved.paste(l, (0, int(dy)), l)
        l = moved
    frame.alpha_composite(l)


def item(frame, cfg, name, cx, cy, size, seed):
    tmp = frame.convert("RGB")
    R.item_visual(tmp, cfg, name, cx, cy, int(size), random.Random(seed))
    frame.paste(tmp)


def price_of(cfg, name):
    for m in cfg["menu"]:
        if m["name"].lower() == str(name).lower():
            return m.get("price")
    return None


def end_card(cfg, line="Comment karo apna answer"):
    base = _bg(footer=None)
    wm = R._brand("wordmark.png").copy()
    wm.thumbnail((620, 360), Image.LANCZOS)
    big = text_layer(line, "bold", (90, 1130, 990, 1330), start=64)
    loc = text_layer("Near IIT Roorkee", "med", (90, 1380, 990, 1460), gold=True, start=52)
    logo = R._brand("logo.png").copy()
    logo.thumbnail((300, 300), Image.LANCZOS)

    def f(t):
        fr = base.copy().convert("RGBA")
        a = ease(t * 3)
        lg = logo.copy()
        lg.putalpha(lg.split()[3].point(lambda v: int(v * a)))
        fr.alpha_composite(lg, (int(W / 2 - logo.width / 2), 330))
        w2 = wm.copy()
        w2.putalpha(w2.split()[3].point(lambda v: int(v * a)))
        fr.alpha_composite(w2, (int(W / 2 - wm.width / 2), 690))
        put(fr, big, ease(t * 3 - 0.4), 30 * (1 - ease(t * 3 - 0.4)))
        put(fr, loc, ease(t * 3 - 0.8))
        return fr
    return f


# ---------------------------------------------------------------- formats
def reel_meme(p, cfg, seed):
    base = _bg()
    hook = text_layer(p["hook"], "bold", (80, 260, 1000, 640), start=86)
    punch = text_layer(p["punchline"], "bold", (80, 1330, 1000, 1700), gold=True, start=96)

    def s1(t):
        fr = base.copy().convert("RGBA")
        put(fr, hook, ease(t * 4), -40 * (1 - ease(t * 4)))
        item(fr, cfg, p["item"], W / 2, 990, 560 + 60 * t, seed)
        return fr

    def s2(t):
        fr = base.copy().convert("RGBA")
        put(fr, hook, 0.55)
        item(fr, cfg, p["item"], W / 2, 990, 620 + 50 * t, seed)
        k = ease(t * 5)
        put(fr, punch, k, 60 * (1 - k))
        return fr
    return [(3.0, s1), (3.6, s2), (2.0, end_card(cfg, p.get("cta_short") or "Tag karo us dost ko"))]


def reel_pov(p, cfg, seed):
    base = _bg()
    pov = text_layer("POV:", "impact", (80, 230, 1000, 400), gold=True, start=150)
    lines = [text_layer(l, "bold", (90, 450 + i * 210, 990, 640 + i * 210), start=68, minimum=36)
             for i, l in enumerate(p["pov_lines"][:3])]
    n = len(lines)
    per = 2.0

    def scene(t):
        fr = base.copy().convert("RGBA")
        put(fr, pov, ease(t * n * 3))
        now = t * (n * per + 1.2)
        for i, l in enumerate(lines):
            k = ease((now - i * per) / 0.5)
            put(fr, l, k * (1 if i == n - 1 or now < (i + 1) * per else 0.6), 40 * (1 - k))
        z = 430 + 120 * t
        item(fr, cfg, p["item"], W / 2, 1420, z, seed)
        return fr
    return [(n * per + 1.2, scene), (2.0, end_card(cfg, "Relatable? Share karo"))]


def reel_top5(p, cfg, seed):
    base = _bg()
    title = text_layer(p["title"], "serif", (80, 600, 1000, 1100), gold=True, start=120)
    sub = text_layer("Countdown shuru", "med", (80, 1150, 1000, 1240), start=48)

    def intro(t):
        fr = base.copy().convert("RGBA")
        k = ease(t * 2.5)
        put(fr, title, k, 50 * (1 - k))
        put(fr, sub, ease(t * 2.5 - 0.5))
        return fr
    scenes = [(1.8, intro)]
    items = p["items"][:5]
    for i, name in enumerate(items):
        rank = len(items) - i
        num = text_layer(f"#{rank}", "impact", (80, 230, 1000, 470), gold=True, start=210)
        nm = text_layer(name.upper(), "impact", (80, 1290, 1000, 1470), start=120, minimum=60)
        price = price_of(cfg, name)
        pr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        if price:
            R.pill(pr, W / 2, 1560, f"₹{price}", R.F("bold", 64))

        def sc(t, num=num, nm=nm, pr=pr, name=name, i=i):
            fr = base.copy().convert("RGBA")
            k = ease(t * 4)
            put(fr, num, k, -50 * (1 - k))
            item(fr, cfg, name, W / 2 + 300 * (1 - k), 860, 560, f"{seed}{i}")
            put(fr, nm, ease(t * 4 - 0.3))
            put(fr, pr, ease(t * 4 - 0.6))
            return fr
        scenes.append((1.7, sc))
    scenes.append((2.0, end_card(cfg, "Tumhara #1 kaunsa? Comment karo")))
    return scenes


def reel_this_or_that(p, cfg, seed):
    base = _bg()
    head = text_layer("THIS or THAT", "impact", (80, 220, 1000, 380), gold=True, start=120)
    sub = text_layer("3 second me choose karo", "med", (80, 380, 1000, 460), start=44)
    scenes = []
    pairs = p["pairs"][:3]
    for r, pr in enumerate(pairs):
        cards = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for k, (key, y) in enumerate((("a", 520), ("b", 1130))):
            R.rrect(cards, (90, y, 990, y + 520))
            d = ImageDraw.Draw(cards)
            d.ellipse((115, y + 25, 225, y + 135), fill=R.GOLD)
            R.text(cards, (170, y + 82), key.upper(), R.F("impact", 66), R.BG)
            R.paste_c(cards, R.emoji(pr.get(f"{key}_emoji") or "✨", 230), 330, y + 270)
            f, lines, size = R.fit(pr[key], "bold", 500, 360, 84, 44)
            yy = y + 270 - size * 1.18 * (len(lines) - 1) / 2
            for l in lines:
                R.gold_text(cards, (480, yy), l, f, anchor="lm")
                yy += size * 1.18
        R.text(cards, (W / 2, 1090), "VS", R.F("impact", 70), R.CREAM)
        rnd = text_layer(f"Round {r + 1}/{len(pairs)}", "bold", (80, 460, 1000, 510), fill=R.MUTED, start=34)

        def sc(t, cards=cards, rnd=rnd):
            fr = base.copy().convert("RGBA")
            put(fr, head)
            put(fr, rnd)
            k = ease(t * 5)
            put(fr, cards, k, 80 * (1 - k))
            d = ImageDraw.Draw(fr)
            d.rounded_rectangle((90, 1700, 990, 1724), 12, fill=R.CARD)
            d.rounded_rectangle((90, 1700, 90 + 900 * (1 - t), 1724), 12, fill=R.GOLD)  # timer bar
            return fr
        scenes.append((3.0, sc))

    def intro(t):
        fr = base.copy().convert("RGBA")
        put(fr, head, ease(t * 3))
        put(fr, sub, ease(t * 3 - 0.4))
        return fr
    return [(1.3, intro)] + scenes + [(2.0, end_card(cfg, "Comment karo: A B A"))]


def reel_pause_game(p, cfg, seed):
    rng = random.Random(seed)
    names = [m["name"] for m in cfg["menu"]]
    rng.shuffle(names)
    names = names[:8]
    head = text_layer("PAUSE KARO", "impact", (80, 620, 1000, 860), gold=True, start=190)
    sub = text_layer(p["headline"], "bold", (80, 900, 1000, 1150), start=70)
    base = _bg()

    def intro(t):
        fr = base.copy().convert("RGBA")
        put(fr, head, ease(t * 3), -40 * (1 - ease(t * 3)))
        put(fr, sub, ease(t * 3 - 0.4))
        return fr

    cards = []
    for i, n in enumerate(names):
        c = Image.new("RGB", (W, H), R.BG if i % 2 else R.ALT)
        R.glow(c, W / 2, H / 2, 520, 50)
        R.item_visual(c, cfg, n, W / 2, 900, 560, random.Random(f"{seed}{n}"))
        R.text(c, (W / 2, 1360), n.upper(), R.fit(n.upper(), "impact", 940, 200, 150)[0], R.CREAM)
        pz = price_of(cfg, n)
        if pz:
            R.pill(c, W / 2, 1520, f"₹{pz}", R.F("bold", 56))
        R.text(c, (W / 2, 1720), "PAUSE KARO", R.F("bold", 56), R.GOLD)
        cards.append(c)

    def flash(t):
        idx = int(t * 8 * FPS / 3) % len(cards)  # har 3 frame pe naya item
        return cards[idx].convert("RGBA")
    return [(1.6, intro), (8.0, flash), (2.2, end_card(cfg, "Kya aaya? Comment karo"))]


def reel_freestyle(p, cfg, seed):
    """UNLIMITED reels: AI har baar naya concept + scenes likhta hai, ye unhe animate karta hai."""
    base = _bg()
    scenes = []
    title = p.get("concept_title")
    if title:
        tl = text_layer(title, "serif", (80, 640, 1000, 1100), gold=True, start=120)

        def intro(t, tl=tl):
            fr = base.copy().convert("RGBA")
            k = ease(t * 2.5)
            put(fr, tl, k, 60 * (1 - k))
            return fr
        scenes.append((1.6, intro))
    sc_list = p["scenes"][:6]
    for i, sc in enumerate(sc_list):
        style = sc.get("style", "hook")
        it, em = sc.get("item"), sc.get("emoji")
        has_visual = bool(it or em)
        box = (80, 250, 1000, 760) if has_visual else (80, 520, 1000, 1300)
        kind = {"punch": "impact", "reveal": "impact", "question": "bold", "list": "med"}.get(style, "bold")
        gold = style in ("punch", "reveal", "question")
        tl = text_layer(sc["text"], kind, box, gold=gold, start=120 if not has_visual else 92, minimum=44)
        step = text_layer(f"{i + 1}/{len(sc_list)}", "bold", (860, 120, 1010, 180), fill=R.MUTED, start=34) \
            if p.get("numbered") else None

        def f(t, tl=tl, it=it, em=em, style=style, step=step, i=i):
            fr = base.copy().convert("RGBA")
            k = ease(t * 4)
            if style == "reveal":
                put(fr, tl, ease(t * 3 - 0.6))
            elif style == "punch":
                put(fr, tl, k, 0)
            else:
                put(fr, tl, k, 50 * (1 - k))
            if step:
                put(fr, step)
            if it:
                item(fr, cfg, it, W / 2 + (220 * (1 - k) if i % 2 else -220 * (1 - k)), 1240, 560 + 70 * t, f"{seed}{i}")
            elif em:
                e = R.emoji(em, int(380 + 60 * t))
                fr.alpha_composite(e, (int(W / 2 - e.width / 2), int(1240 - e.height / 2)))
            return fr
        scenes.append((2.4 if style != "list" else 2.0, f))
    scenes.append((2.2, end_card(cfg, p.get("end_line") or "Comment karo")))
    return scenes


def images_to_reel(images, cfg, out_path, seed):
    """Koi bhi image / carousel post → music wala video (slow zoom + slide transition)."""
    base = _bg(footer=None)
    slides = [im.convert("RGB") for im in images]
    per = 6.5 if len(slides) == 1 else 2.8

    def mk(sl, i):
        def f(t):
            fr = base.copy()
            z = 1.0 + 0.06 * t
            w, h = int(1000 * z), int(1250 * z)
            im = sl.resize((w, h), Image.LANCZOS)
            k = ease(t * 5) if len(slides) > 1 else 1
            x = int(W / 2 - w / 2 + (1 - k) * 600)
            fr.paste(im, (x, int(H / 2 - h / 2)))
            return fr.convert("RGBA")
        return f
    scenes = [(per, mk(sl, i)) for i, sl in enumerate(slides)]
    scenes.append((1.8, end_card(cfg, "Follow karo, roz naya post")))
    return _encode(scenes, out_path, seed)


def reel_showcase(p, cfg, seed):
    """Cinematic product reel: slow zoom, elegant serif lines."""
    base = _bg()
    open_l = text_layer(p["opening_line"], "serif", (80, 700, 1000, 1150), gold=True, start=120)

    def intro(t):
        fr = base.copy().convert("RGBA")
        put(fr, open_l, ease(t * 2), 30 * (1 - ease(t * 2)))
        return fr
    scenes = [(2.0, intro)]
    for i, sh in enumerate(p["shots"][:3]):
        nm = text_layer(sh["item"], "serif", (80, 1290, 1000, 1430), gold=True, start=96, minimum=56)
        ln = text_layer(sh["line"], "reg", (110, 1440, 970, 1560), start=48, minimum=32)

        def f(t, sh=sh, nm=nm, ln=ln, i=i):
            fr = base.copy().convert("RGBA")
            item(fr, cfg, sh["item"], W / 2, 820, 700 + 120 * t, f"{seed}{i}")  # slow push-in
            put(fr, nm, ease(t * 2.5 - 0.2))
            put(fr, ln, ease(t * 2.5 - 0.6))
            return fr
        scenes.append((3.0, f))
    scenes.append((2.4, end_card(cfg, p.get("closing_line") or "Your table is waiting")))
    return scenes


REELS = {k: v for k, v in globals().items() if k.startswith("reel_")}


def pick_music(seed, mood=None):
    files = sorted(glob.glob(R.A("music", "*.mp3")) + glob.glob(R.A("music", "*.m4a")))
    if mood:
        m = [f for f in files if mood in os.path.basename(f).lower()]
        files = m or files
    return random.Random(seed).choice(files) if files else None


def _encode(scenes, out_path, seed, mood=None):
    tmp = tempfile.mkdtemp()
    i = 0
    cover = None
    for dur, fn in scenes:
        n = max(1, int(dur * FPS))
        for k in range(n):
            fr = fn(k / max(1, n - 1)).convert("RGB")
            if cover is None and i == int(1.2 * FPS):
                cover = fr.copy()
            fr.save(os.path.join(tmp, f"{i:05d}.jpg"), quality=90)
            i += 1
    total = i / FPS
    music = pick_music(seed, mood)
    cmd = [R.ffmpeg_bin(), "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(tmp, "%05d.jpg")]
    if music:
        cmd += ["-stream_loop", "-1", "-i", music, "-map", "0:v", "-map", "1:a",
                "-af", f"afade=t=in:d=0.4,afade=t=out:st={max(0, total - 1.5)}:d=1.5", "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high", "-crf", "20",
            "-movflags", "+faststart", "-t", f"{total}", out_path]
    subprocess.run(cmd, check=True)
    (cover or Image.open(os.path.join(tmp, "00000.jpg"))).save(out_path.replace(".mp4", "_cover.jpg"), quality=92)
    shutil.rmtree(tmp)
    return out_path


def render_reel(fmt_renderer, post, cfg, out_path, seed):
    scenes = REELS[fmt_renderer](post, cfg, seed)
    mood = {"reel_pause_game": "game", "reel_showcase": "lofi", "reel_top5": "upbeat"}.get(fmt_renderer)
    return _encode(scenes, out_path, seed, mood)
