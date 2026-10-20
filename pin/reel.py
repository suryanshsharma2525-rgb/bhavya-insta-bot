"""Usi Pinterest design ki REEL (9:16) — designer-style, sasta "uchhalta" effect nahi.

Timeline (~10 sec):
  0.0s  background + shapes (patti, circle) smooth slide/scale ke saath
  0.5s  khane ki photo halke zoom-out ke saath aati hai, phir poori reel me dheere-dheere zoom (Ken Burns)
  0.9s+ text ek-ek karke (padhne ke order me) halka upar uthte hue fade-in
  ...   design hold (log padh sakein)
  8.4s  end card: Bhavya logo + handle + location
Music: aapke music folder se design ke mood ke hisaab se; halke whoosh/pop sound sahi moment pe.
"""
import math
import os
import random
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw

from . import render as RD

FPS = 30
RW, RH = 1080, 1920


def _ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _ease_back(t, s=1.4):
    t = max(0.0, min(1.0, t)) - 1
    return t * t * ((s + 1) * t + s) + 1


def plan(layers):
    """Har layer ka entry time + animation type."""
    shapes = [l for l in layers if l[0]["type"] == "shape"]
    photos = [l for l in layers if l[0]["type"] == "photo"]
    texts = [l for l in layers if l[0]["type"] == "text"]
    icons = [l for l in layers if l[0]["type"] == "icon"]
    sched = {}
    for i, l in enumerate(shapes):
        big = l[1].width * l[1].height > RW * RH * 0.25
        sched[id(l)] = (0.05 + i * 0.08, 0.7, "wipe" if big else "scale")
    for i, l in enumerate(photos):
        sched[id(l)] = (0.45 + i * 0.15, 0.8, "photo")
    order = sorted(texts, key=lambda l: (round(l[2][1] / 60), l[2][0]))  # upar se neeche, left se right
    for i, l in enumerate(order):
        giant = l[0].get("role") in ("giant_word", "headline") and l[1].height > RH * 0.07
        sched[id(l)] = (0.9 + i * 0.16, 0.6, "giant" if giant else "rise")
    t_last = 0.9 + len(order) * 0.16
    for i, l in enumerate(icons):
        sched[id(l)] = (t_last + 0.1 + i * 0.1, 0.5, "fade")
    return sched


def _place(fr, img, x, y, alpha=1.0, scale=1.0):
    if alpha <= 0.01:
        return
    if abs(scale - 1) > 0.003:
        nw, nh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
        x += (img.width - nw) / 2
        y += (img.height - nh) / 2
        img = img.resize((nw, nh), Image.BICUBIC)
    if alpha < 0.99:
        img = img.copy()
        img.putalpha(img.getchannel("A").point(lambda v: int(v * alpha)))
    x, y = int(round(x)), int(round(y))
    l, t = max(0, -x), max(0, -y)
    r, b = min(img.width, fr.width - x), min(img.height, fr.height - y)
    if r > l and b > t:
        fr.alpha_composite(img.crop((l, t, r, b)), (x + l, y + t))


def frame(bg, layers, sched, T, total_design):
    fr = bg.convert("RGBA")
    for l in layers:
        e, img, (x, y) = l
        start, dur, kind = sched[id(l)]
        k = (T - start) / dur
        if k <= 0:
            continue
        p = _ease(k)
        if kind == "wipe":  # left se khulta hua
            cw = max(1, int(img.width * p))
            _place(fr, img.crop((0, 0, cw, img.height)), x, y)
        elif kind == "scale":
            _place(fr, img, x, y, alpha=min(1, k * 2), scale=0.85 + 0.15 * _ease_back(k))
        elif kind == "photo":
            kb = 1.0 + 0.03 * min(1.0, max(0.0, (T - start) / max(1.0, total_design - start)))  # dheere zoom
            # 1.05 → 0.97, phir dheere 1.0 tak: kabhi asli size se bada nahi (text pe na chadhe)
            _place(fr, img, x, y + (1 - p) * 40, alpha=min(1, k * 1.6), scale=(1.05 - 0.08 * p) * kb)
        elif kind == "giant":
            _place(fr, img, x, y, alpha=min(1, k * 1.8), scale=1.12 - 0.12 * p)
        elif kind == "rise":
            _place(fr, img, x, y + (1 - p) * 46, alpha=p)
        else:
            _place(fr, img, x, y, alpha=p)
    return fr.convert("RGB")


# ---------------------------------------------------------------- logo sting: bada logo + whoosh + dhuan
STING = 2.8


class Sting:
    """Dark premium background, dhuan (smoke) center se uthta hai, bada gold Bhavya logo whoosh ke saath aata hai."""

    def __init__(self, cfg, seed="bhavya"):
        import numpy as np
        from PIL import ImageFilter
        self.cfg = cfg
        rng = np.random.default_rng(abs(hash(seed)) % (2 ** 32))
        # warm dark background + halki roshni center me
        bg = Image.new("RGB", (RW, RH), (18, 12, 9))
        glow = Image.radial_gradient("L").resize((RW, RW)).point(lambda v: int(max(0, 255 - v) * 0.55))
        layer = Image.new("RGB", (RW, RW), (92, 58, 26))
        bg.paste(layer, (0, int(RH * 0.40 - RW / 2)), glow)
        self.bg = bg.filter(ImageFilter.GaussianBlur(30))
        # dhuen ka texture (fractal noise, chhote size pe → smooth)
        sw, sh = RW // 4, int(RH // 4 * 1.6)
        field = np.zeros((sh, sw), np.float32)
        for cells, amp in ((5, 1.0), (10, 0.5), (20, 0.25), (40, 0.12)):  # bade gubbare zyada, chhote detail kam
            n = rng.random((max(2, int(sh / sw * cells)), cells)).astype(np.float32)
            im = Image.fromarray((n * 255).astype("uint8")).resize((sw, sh), Image.BICUBIC)
            field += amp * np.asarray(im.filter(ImageFilter.GaussianBlur(sw / cells / 2.5)), np.float32) / 255.0
        field = (field - field.min()) / (field.max() - field.min() + 1e-6)
        sm = np.clip((field - 0.30) * 1.7, 0, 1)
        self.smoke = np.asarray(Image.fromarray((sm * 255).astype("uint8")).filter(ImageFilter.GaussianBlur(2)),
                                np.float32) / 255.0
        logo = Image.open(os.path.join(RD.ROOT, "assets", "brand", "logo.png")).convert("RGBA")
        k = int(RW * 0.50) / logo.width
        self.logo = logo.resize((int(logo.width * k), int(logo.height * k)), Image.LANCZOS)
        from PIL import ImageFilter as F2
        self.logo = self.logo.filter(F2.UnsharpMask(2, 60, 2))
        wm = Image.open(os.path.join(RD.ROOT, "assets", "brand", "wordmark.png")).convert("RGBA")
        wm.thumbnail((int(RW * 0.62), 600), Image.LANCZOS)
        self.wm = wm
        from . import fonts as FN
        f = FN.font(FN.LOCAL["sans"], 40)
        line = f"{cfg['brand'].get('handle', '@bhavya_cafe')}   ·   Near IIT Roorkee"
        t = Image.new("RGBA", (RW, 80), (0, 0, 0, 0))
        ImageDraw.Draw(t).text((RW / 2, 40), line, font=f, fill=(226, 196, 140, 255), anchor="mm")
        self.line = t

    def _smoke_layer(self, T):
        import numpy as np
        sh, sw = self.smoke.shape
        h = RH // 4
        off = int((T * 38) % (sh - h))  # dhuan upar ki taraf
        tex = self.smoke[sh - h - off: sh - off]
        yy, xx = np.mgrid[0:h, 0:sw].astype(np.float32)
        cx, cy = sw / 2 + np.sin(T * 1.3) * 6, h * 0.38
        puff = min(1.0, 0.25 + T / 0.9)  # landing ke saath failta hai
        r = (sw * 0.52) * puff
        mask = np.clip(1 - np.sqrt(((xx - cx) / r) ** 2 + ((yy - cy) / (r * 1.6)) ** 2), 0, 1) ** 1.4
        fade = min(1.0, T / 0.5) * (1 - max(0.0, (T - 2.2) / 0.6) * 0.5)
        a = np.clip(tex * mask * 1.05 * fade, 0, 0.9)
        al = Image.fromarray((a * 255).astype("uint8")).resize((RW, RH), Image.BICUBIC)
        lay = Image.new("RGBA", (RW, RH), (236, 222, 200, 0))
        lay.putalpha(al)
        return lay

    def frame(self, T):
        fr = self.bg.convert("RGBA")
        fr.alpha_composite(self._smoke_layer(T))
        # logo: door se whoosh ke saath (bada + dhundhla) → apni jagah halke bounce ke saath
        k = (T - 0.05) / 0.45
        if k > 0:
            p = _ease_back(k, 1.2)
            sc = 2.2 - 1.2 * p
            al = min(1.0, k * 2.2)
            lg = self.logo
            if k < 1:  # tez aate waqt motion blur
                from PIL import ImageFilter
                lg = lg.filter(ImageFilter.GaussianBlur(max(0.0, (1 - k) * 10)))
            _place(fr, lg, (RW - self.logo.width) / 2, RH * 0.36 - self.logo.height / 2, alpha=al, scale=sc)
        q = _ease((T - 0.6) / 0.5)
        _place(fr, self.wm, (RW - self.wm.width) / 2, RH * 0.36 + self.logo.height / 2 + 30 + (1 - q) * 40, alpha=q)
        r = _ease((T - 1.0) / 0.5)
        _place(fr, self.line, 0, RH * 0.36 + self.logo.height / 2 + self.wm.height + 70 + (1 - r) * 24, alpha=r)
        return fr.convert("RGB")


def _mood(spec):
    m = (spec.get("mood") or "").lower()
    if any(w in m for w in ("bold", "retro", "energetic", "pop", "vibrant", "fun", "street")):
        return "upbeat"
    if any(w in m for w in ("festive", "desi", "indian", "traditional")):
        return "desi"
    if any(w in m for w in ("luxury", "elegant", "premium", "dark", "cinematic")):
        return "cinematic"
    return "lofi"


def make(spec, texts, photo, cutout, cfg, out_path, seed="", design_seconds=8.4, end_seconds=STING):
    from bot import audio, render as OLD
    s9 = RD.expand_to(spec)
    old = (RD.W, RD.H)
    RD.set_size(RW, RH)
    try:
        bg, layers = RD.render_layers(s9, texts, photo, cutout)
    finally:
        RD.set_size(*old)
    sched = plan(layers)
    last_in = max([v[0] + v[1] for v in sched.values()] or [2.0])
    design_seconds = max(design_seconds, last_in + 4.0)  # sab aane ke baad kam se kam 4 sec padhne ko
    total = design_seconds + end_seconds
    tmp = tempfile.mkdtemp()
    sting = Sting(cfg, seed)
    n = int(total * FPS)
    for i in range(n):
        T = i / FPS
        if T < design_seconds:
            fr = frame(bg, layers, sched, T, design_seconds)
            if T > design_seconds - 0.25:  # design se logo tak tez dissolve
                a = (T - (design_seconds - 0.25)) / 0.25
                fr = Image.blend(fr, sting.frame(0), a)
        else:
            fr = sting.frame(T - design_seconds)
        fr.save(os.path.join(tmp, f"{i:05d}.jpg"), quality=93)
    # music + sound effects
    mood = _mood(spec)
    music, bpm, start, secs = audio.pick(mood, None, seed)
    if music and secs:
        start = min(start, max(0.0, secs - total - 2))
    events = [(0.45, "whoosh")]
    for l in layers:
        st, du, kind = sched[id(l)]
        if l[0].get("role") in ("price", "offer"):
            events.append((st + 0.1, "pop"))
        elif kind == "giant":
            events.append((st, "whoosh"))
    events += [(design_seconds - 0.1, "whoosh"), (design_seconds + 0.42, "boom"), (design_seconds + 0.75, "shimmer")]
    events = sorted(events[:6] + events[-3:])
    events = [(t, k) for t, k in events if t < total]
    wav = os.path.join(tmp, "a.wav")
    audio.mix(total, music, start, events, wav, music_vol=0.8, sfx_vol=0.35)
    cmd = [OLD.ffmpeg_bin(), "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(tmp, "%05d.jpg"),
           "-i", wav, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high", "-crf", "19", "-preset", "medium",
           "-maxrate", "5M", "-bufsize", "10M", "-g", "60", "-r", str(FPS), "-movflags", "+faststart",
           "-t", f"{total:.3f}", out_path]
    subprocess.run(cmd, check=True)
    # cover = poora design (sab aa chuka ho)
    frame(bg, layers, sched, design_seconds - 0.5, design_seconds).save(
        os.path.join(os.path.dirname(out_path), "reel_cover.jpg"), quality=92)
    shutil.rmtree(tmp, ignore_errors=True)
    return out_path, os.path.basename(music) if music else None
