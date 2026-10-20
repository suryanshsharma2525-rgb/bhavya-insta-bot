"""AI Art Director — har post/reel ka poora LOOK tay karta hai.

Colours (unlimited, procedurally generated), font pack, background styles, text animations,
transitions, product layouts aur vibe. Gemini se poochta hai; na mile to smart random.
"""
import colorsys
import json
import random

from . import render as R

FONT_PACKS = {
    # role: (file, variation)
    "classic":  {"display": ("Anton.ttf", None), "head": ("Poppins-Bold.ttf", None), "serif": ("PlayfairDisplay.ttf", "Bold"),
                 "italic": ("LoraItalic.ttf", "Italic"), "body": ("Poppins-Medium.ttf", None), "body2": ("Poppins-Regular.ttf", None)},
    "editorial": {"display": ("AbrilFatface.ttf", None), "head": ("Montserrat.ttf", "Bold"), "serif": ("Cormorant.ttf", "Bold"),
                  "italic": ("PlayfairItalic.ttf", "Italic"), "body": ("Montserrat.ttf", "Medium"), "body2": ("Montserrat.ttf", "Regular")},
    "modern":   {"display": ("ArchivoBlack.ttf", None), "head": ("Montserrat.ttf", "ExtraBold"), "serif": ("DMSerifDisplay.ttf", None),
                 "italic": ("LoraItalic.ttf", "Italic"), "body": ("Montserrat.ttf", "SemiBold"), "body2": ("Montserrat.ttf", "Regular")},
    "street":   {"display": ("BebasNeue.ttf", None), "head": ("Oswald.ttf", "Bold"), "serif": ("DMSerifDisplay.ttf", None),
                 "italic": ("Caveat.ttf", "Bold"), "body": ("Oswald.ttf", "Medium"), "body2": ("Oswald.ttf", "Regular")},
    "luxe":     {"display": ("Cormorant.ttf", "Bold"), "head": ("Syne.ttf", "Bold"), "serif": ("Cormorant.ttf", "SemiBold"),
                 "italic": ("PlayfairItalic.ttf", "Italic"), "body": ("Syne.ttf", "Medium"), "body2": ("Syne.ttf", "Regular")},
    "pop":      {"display": ("Anton.ttf", None), "head": ("Syne.ttf", "ExtraBold"), "serif": ("AbrilFatface.ttf", None),
                 "italic": ("Caveat.ttf", "Bold"), "body": ("Syne.ttf", "SemiBold"), "body2": ("Syne.ttf", "Regular")},
    "minimal":  {"display": ("Montserrat.ttf", "Black"), "head": ("Montserrat.ttf", "SemiBold"), "serif": ("DMSerifDisplay.ttf", None),
                 "italic": ("LoraItalic.ttf", "Italic"), "body": ("Montserrat.ttf", "Medium"), "body2": ("Montserrat.ttf", "Light")},
    "boutique": {"display": ("Fraunces.ttf", "Black"), "head": ("Bricolage.ttf", "Bold"), "serif": ("Fraunces.ttf", "SemiBold"),
                 "italic": ("Sacramento.ttf", None), "body": ("Outfit.ttf", "Medium"), "body2": ("Outfit.ttf", "Light")},
    "bold_modern": {"display": ("Unbounded.ttf", "Black"), "head": ("SpaceGrotesk.ttf", "Bold"), "serif": ("YesevaOne.ttf", None),
                    "italic": ("Lobster.ttf", None), "body": ("SpaceGrotesk.ttf", "Medium"), "body2": ("SpaceGrotesk.ttf", "Regular")},
    "retro_diner": {"display": ("Shrikhand.ttf", None), "head": ("Righteous.ttf", None), "serif": ("YesevaOne.ttf", None),
                    "italic": ("Lobster.ttf", None), "body": ("JosefinSans.ttf", "SemiBold"), "body2": ("JosefinSans.ttf", "Regular")},
    "desi_bold": {"display": ("RozhaOne.ttf", None), "head": ("Baloo2.ttf", "ExtraBold"), "serif": ("RozhaOne.ttf", None),
                  "italic": ("Caveat.ttf", "Bold"), "body": ("Baloo2.ttf", "Medium"), "body2": ("Baloo2.ttf", "Regular")},
    "royal": {"display": ("YesevaOne.ttf", None), "head": ("Marcellus.ttf", None), "serif": ("Fraunces.ttf", "Bold"),
              "italic": ("Sacramento.ttf", None), "body": ("JosefinSans.ttf", "Medium"), "body2": ("JosefinSans.ttf", "Light")},
    "retro":    {"display": ("AbrilFatface.ttf", None), "head": ("Oswald.ttf", "SemiBold"), "serif": ("PlayfairDisplay.ttf", "Black"),
                 "italic": ("Caveat.ttf", "Bold"), "body": ("Oswald.ttf", "Regular"), "body2": ("Oswald.ttf", "Light")},
}

ACCENTS = {  # name: base accent RGB
    "gold": (214, 166, 80), "champagne": (236, 208, 150), "rose_gold": (226, 150, 132), "copper": (206, 116, 62),
    "saffron": (246, 168, 44), "pistachio": (178, 204, 112), "ivory": (240, 230, 205), "coral": (240, 120, 96),
}
MODES = ["dark", "dark", "rich", "light"]
BG_STYLES = ["rays", "bokeh", "blobs", "grid", "stripes", "spotlight", "grain", "rings"]
TEXT_ANIMS = ["rise", "scale", "blur", "words", "split", "typewriter", "mask", "letters", "bounce", "track"]
TRANSITIONS = ["cut", "flash", "push", "zoom", "sweep", "fade", "circle", "blinds", "whip", "leak", "slide_up"]
LAYOUTS = ["circle", "fullbleed", "card", "editorial", "polaroid", "split"]
VIBES = {
    "calm_luxury": dict(modes=["dark", "rich"], accents=["gold", "champagne", "ivory"], fonts=["luxe", "editorial", "classic", "royal", "boutique"],
                        bgs=["spotlight", "bokeh", "grain", "rays"], anims=["blur", "mask", "rise", "track"],
                        trans=["fade", "sweep", "zoom", "leak"], mood="lofi"),
    "energetic": dict(modes=["dark", "rich"], accents=["saffron", "coral", "gold"], fonts=["pop", "street", "modern", "bold_modern"],
                      bgs=["rays", "stripes", "rings", "bokeh"], anims=["scale", "bounce", "words", "letters", "split"],
                      trans=["flash", "whip", "push", "circle", "blinds"], mood="upbeat"),
    "cosy": dict(modes=["rich", "dark"], accents=["copper", "saffron", "champagne"], fonts=["editorial", "retro", "classic", "boutique"],
                 bgs=["blobs", "bokeh", "grain", "spotlight"], anims=["typewriter", "rise", "mask", "blur"],
                 trans=["leak", "fade", "slide_up", "zoom"], mood="lofi"),
    "festive": dict(modes=["rich", "dark"], accents=["gold", "saffron", "rose_gold"], fonts=["classic", "editorial", "retro", "desi_bold", "royal"],
                    bgs=["rays", "bokeh", "rings", "spotlight"], anims=["scale", "letters", "words", "bounce"],
                    trans=["sweep", "flash", "circle", "leak"], mood="desi"),
    "fresh_day": dict(modes=["light"], accents=["pistachio", "coral", "saffron", "gold"], fonts=["minimal", "modern", "editorial", "boutique", "bold_modern"],
                      bgs=["blobs", "grid", "grain"], anims=["rise", "split", "typewriter", "track"],
                      trans=["slide_up", "push", "circle", "blinds"], mood="upbeat"),
    "playful": dict(modes=["dark", "light", "rich"], accents=["coral", "saffron", "pistachio"], fonts=["pop", "street", "retro", "retro_diner", "bold_modern"],
                    bgs=["stripes", "rings", "grid", "blobs"], anims=["bounce", "letters", "words", "split"],
                    trans=["whip", "circle", "blinds", "flash"], mood="upbeat"),
    "desi_warm": dict(modes=["rich", "dark"], accents=["saffron", "copper", "gold"], fonts=["retro", "classic", "street", "desi_bold"],
                      bgs=["rays", "blobs", "bokeh", "grain"], anims=["words", "scale", "rise", "typewriter"],
                      trans=["leak", "sweep", "push", "zoom"], mood="desi"),
}


# ---------------------------------------------------------------- palettes
def _hls(rgb):
    return colorsys.rgb_to_hls(*[c / 255 for c in rgb])


def _rgb(h, l, s):
    return tuple(int(max(0, min(1, c)) * 255) for c in colorsys.hls_to_rgb(h % 1, l, s))


# ---------------------------------------------------------------- colour wheel (colour theory)
# accent (gold/coral...) ke hue se background aur doosra accent colour-wheel ke niyam se:
HARMONIES = {
    "complementary": (0.5, 0.5),             # bilkul opposite: gold ↔ navy, coral ↔ teal (sabse zyada pop)
    "split": (150 / 360, 210 / 360),         # opposite ke dono padosi: contrast + thoda soft
    "triadic": (1 / 3, 2 / 3),               # 120° door teen rang: playful, energetic
    "analogous": (30 / 360, -30 / 360),      # paas-paas ke rang: calm, cosy, warm
    "monochrome": (0.0, 0.0),                # ek hi rang ke shades: luxury, minimal
}
VIBE_HARMONY = {"calm_luxury": ["monochrome", "complementary", "analogous"], "cosy": ["analogous", "monochrome", "split"],
                "energetic": ["complementary", "triadic", "split"], "festive": ["split", "triadic", "complementary"],
                "fresh_day": ["analogous", "split", "triadic"], "playful": ["triadic", "complementary", "split"],
                "desi_warm": ["analogous", "split", "complementary"]}


def _lum(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = c[:3]
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _ensure(fg, bg, target, darker):
    """fg ki lightness tab tak badlo jab tak bg pe padhne layak contrast na aa jaye."""
    h, l, s_ = _hls(fg)
    for _ in range(30):
        if contrast(fg, bg) >= target:
            break
        l = max(0.0, l - 0.03) if darker else min(1.0, l + 0.03)
        fg = _rgb(h, l, s_)
    return fg


def make_palette(rng, mode, accent_name, harmony=None):
    ah, al, as_ = _hls(ACCENTS[accent_name])
    stops = [(0, _rgb(ah, min(0.86, al + 0.22), as_ * 0.9)), (0.45, _rgb(ah, al, as_)),
             (0.8, _rgb(ah, max(0.18, al - 0.2), as_)), (1, _rgb(ah, min(0.8, al + 0.12), as_))]
    off_bg, off_2 = HARMONIES.get(harmony, (None, None))
    bh = rng.random() if off_bg is None else (ah + off_bg + rng.uniform(-0.02, 0.02)) % 1
    h2 = (ah + off_2) % 1 if off_2 is not None else (bh + 0.5) % 1
    pal = _palette(rng, mode, accent_name, ah, al, as_, stops, bh)
    acc2 = _rgb(h2, 0.38 if pal["light"] else 0.66, 0.5 if pal["light"] else 0.42)  # soft, premium (neon nahi)
    if harmony == "monochrome":
        acc2 = _rgb(ah, 0.75 if not pal["light"] else 0.3, as_ * 0.5)
    pal["accent2"] = acc2
    pal["harmony"] = harmony or "free"
    # padhne layak contrast ki guarantee (WCAG): text ≥ 7:1, accent ≥ 3:1
    pal["cream"] = _ensure(pal["cream"], pal["bg"], 7.0, darker=pal["light"])
    pal["gold"] = _ensure(pal["gold"], pal["bg"], 3.0, darker=pal["light"])
    pal["accent2"] = _ensure(pal["accent2"], pal["bg"], 3.0, darker=pal["light"])
    return pal


def _palette(rng, mode, accent_name, ah, al, as_, stops, bh):
    if mode == "light":
        bg = _rgb(bh, rng.uniform(0.9, 0.95), rng.uniform(0.25, 0.55))
        acc = _rgb(ah, 0.32, min(1, as_ + 0.15))
        stops = [(0, _rgb(ah, 0.36, min(1, as_ + 0.1))), (0.5, _rgb(ah, 0.27, as_)), (1, _rgb(ah, 0.33, as_))]
        return dict(bg=bg, card=_rgb(bh, 0.86, 0.35), panel=_rgb(bh, 0.88, 0.3), line=_rgb(ah, 0.7, 0.3),
                    alt=_rgb(bh, 0.82, 0.4), gold=acc, stops=stops, cream=_rgb(bh, 0.13, 0.35),
                    muted=_rgb(bh, 0.4, 0.15), light=True)
    l = rng.uniform(0.04, 0.08) if mode == "dark" else rng.uniform(0.11, 0.17)
    sat = rng.uniform(0.15, 0.45) if mode == "dark" else rng.uniform(0.45, 0.75)
    return dict(bg=_rgb(bh, l, sat), card=_rgb(bh, l + 0.05, sat), panel=_rgb(bh, l + 0.03, sat),
                line=_rgb(ah, 0.38, as_ * 0.6), alt=_rgb(bh, l + 0.08, sat), gold=ACCENTS[accent_name], stops=stops,
                cream=_rgb(ah, 0.94, 0.4), muted=_rgb(bh, 0.62, 0.15), light=False)


def apply(style):
    R.set_theme_dict(style["palette_name"], style["palette"])
    R.FONTPACK = FONT_PACKS.get(style["font_pack"], FONT_PACKS["classic"])
    R.font.cache_clear()


# ---------------------------------------------------------------- director
def _ai_pick(cfg, ctx):
    from . import ai
    prompt = (
        "You are the art director for Bhavya Cafe's Instagram (premium cafe near IIT Roorkee). "
        "Choose a fresh visual style for today's post so the feed never looks repetitive.\n"
        f"Post format: {ctx.get('format')}\nOccasion: {ctx.get('occasion') or 'none'}\nIdea: {ctx.get('idea') or '-'}\n"
        f"Date: {ctx.get('date')}\nLast styles used (avoid repeating): {ctx.get('recent_styles')}\n\n"
        f"Pick ONLY from these options and return JSON:\n"
        f'{{"vibe": one of {list(VIBES)}, "mode": one of {sorted(set(MODES))}, "accent": one of {list(ACCENTS)}, '
        f'"font_pack": one of {list(FONT_PACKS)}, "harmony": one of {list(HARMONIES)} (colour-wheel rule for background vs accent), '
        f'"backgrounds": 1-2 of {BG_STYLES}, '
        f'"text_anims": 2-3 of {TEXT_ANIMS}, "transitions": 2-4 of {TRANSITIONS}, "layouts": 1-3 of {LAYOUTS}}}'
    )
    d = ai._gemini(prompt, cfg)
    return d if isinstance(d, dict) else None


def choose(cfg, seed, ctx=None, use_ai=True, force=None):
    ctx = ctx or {}
    rng = random.Random(f"style-{seed}")
    d = _ai_pick(cfg, ctx) if use_ai else None
    if force:  # winner din: jo look chala tha wahi (vibe / colour harmony / fonts)
        d = {**(d or {}), **force}
    vibe = (d or {}).get("vibe") if (d or {}).get("vibe") in VIBES else rng.choice(list(VIBES))
    v = VIBES[vibe]

    def pick(key, allowed, pool, k):
        got = [x for x in ((d or {}).get(key) or []) if x in allowed]
        return got[:k[1]] if len(got) >= k[0] else rng.sample(pool, min(len(pool), rng.randint(*k)))
    mode = (d or {}).get("mode") if (d or {}).get("mode") in MODES else rng.choice(v["modes"])
    harmony = (d or {}).get("harmony") if (d or {}).get("harmony") in HARMONIES else rng.choice(VIBE_HARMONY[vibe])
    accent = (d or {}).get("accent") if (d or {}).get("accent") in ACCENTS else rng.choice(v["accents"])
    fonts = (d or {}).get("font_pack") if (d or {}).get("font_pack") in FONT_PACKS else rng.choice(v["fonts"])
    style = dict(
        vibe=vibe, mode=mode, accent=accent, font_pack=fonts, harmony=harmony,
        backgrounds=pick("backgrounds", BG_STYLES, v["bgs"], (1, 2)),
        text_anims=pick("text_anims", TEXT_ANIMS, v["anims"], (2, 3)),
        transitions=pick("transitions", TRANSITIONS, v["trans"], (2, 4)),
        layouts=pick("layouts", LAYOUTS, LAYOUTS, (1, 3)),
        mood=v["mood"], source="gemini" if d else "random",
    )
    style["palette_name"] = f"{mode}-{accent}-{harmony}-{abs(hash(seed)) % 10000}"
    style["palette"] = make_palette(rng, mode, accent, harmony)
    return style


def describe(style):
    return {k: style.get(k) for k in ("vibe", "mode", "accent", "harmony", "font_pack", "backgrounds", "text_anims",
                                      "transitions", "layouts", "source")}
