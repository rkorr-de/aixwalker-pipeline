"""Bilder der Winter-Cabin-Linie (Rolf 09.10.2026): Thumbnail „C“ (Streaming-Look, Text oben links, großes goldenes
„4K UHD“-Etikett) und die Text-Ebene der Shorts „S1 v2“ (Genre groß oben, Frage-Pille, „4K UHD“-Etikett unten).
Kein Album-Cover, keine Track-Cover (kein DistroKid für diese Linie)."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from . import config

TITLE_1, TITLE_2 = "COZY WINTER", "CABIN"
SUBLINE = "RELAXING FIREPLACE CHILLOUT"
GOLD = (255, 200, 120)
CABIN_GOLD = (255, 196, 110)
INK = (20, 14, 6)
# Fragen für die Shorts (Recherche 09.10.: virale Nischen-Shorts arbeiten mit einer Frage als Haken), wechseln je Short
SHORT_QUESTIONS = ["Would you stay here tonight?", "Could you sleep here?", "Rate this cabin 1–10",
                   "Where would you sit first?", "Would you spend winter here?", "Is this your dream cabin?"]


def font(size: float, weight: str = "Black") -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(config.FONT_TITLE), int(size))
    f.set_variation_by_name(weight)
    return f


def _tw(text: str, f, track: float) -> float:
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    return sum(d.textlength(c, font=f) for c in text) + track * (len(text) - 1)


def _draw(d, xy, text, f, fill, track=0.0):
    x, y = xy
    for c in text:
        d.text((x, y), c, font=f, fill=fill)
        x += d.textlength(c, font=f) + track


def _shadow_text(img, xy, text, f, fill, blur=28, alpha=210, track=0.0, glow=None):
    m = Image.new("L", img.size, 0)
    _draw(ImageDraw.Draw(m), xy, text, f, 255, track)
    img.paste(Image.new("RGB", img.size, (6, 8, 14)), (0, 0),
              m.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: v * alpha // 255))
    if glow:
        img.paste(Image.new("RGB", img.size, glow), (0, 0),
                  m.filter(ImageFilter.GaussianBlur(blur * 1.6)).point(lambda v: v * 120 // 255))
    _draw(ImageDraw.Draw(img), xy, text, f, fill, track)


def grade(img: Image.Image) -> Image.Image:
    """Thumbnail-Look: Schatten anheben, warme Lichter wärmer, satter, Leuchten um Feuer/Kerzen, leichte Vignette."""
    a = np.asarray(img.convert("RGB")).astype(np.float32) / 255
    lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
    a = np.clip(a * (np.power(np.clip(lum, 1e-4, 1), 0.82) / np.clip(lum, 1e-4, 1))[..., None], 0, 1)
    warm = np.clip((lum - 0.25) / 0.5, 0, 1)[..., None]
    a = a * (1 + warm * np.array([0.10, 0.03, -0.08], np.float32))
    out = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    out = ImageEnhance.Contrast(ImageEnhance.Color(out).enhance(1.18)).enhance(1.06)
    blur = max(8, out.width // 85)
    hi = out.point(lambda v: max(0, v - 170) * 3).filter(ImageFilter.GaussianBlur(blur))
    out = Image.fromarray(np.clip(np.asarray(out).astype(np.int16) + (np.asarray(hi) * 0.55).astype(np.int16), 0, 255)
                          .astype(np.uint8))
    yy, xx = np.mgrid[0:out.height, 0:out.width]
    r = np.sqrt(((xx - out.width / 2) / (out.width / 2)) ** 2 + ((yy - out.height / 2) / (out.height / 2)) ** 2)
    vig = np.clip(1 - 0.28 * np.clip(r - 0.55, 0, 1) ** 1.5, 0, 1)
    return Image.fromarray((np.asarray(out) * vig[..., None]).astype(np.uint8))


def _chip(img, x, y, text, s):
    """Halbtransparente Pille mit weißer Schrift (z. B. „2 HOURS“)."""
    f = font(64 * s, "Bold")
    tr = 8 * s
    w, h = _tw(text, f, tr) + 70 * s, 110 * s
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle([x, y, x + w, y + h], h / 2, fill=(0, 0, 0, 120))
    img.paste(ov.convert("RGB"), (0, 0), ov.split()[3])
    _draw(ImageDraw.Draw(img), (x + 35 * s, y + 20 * s), text, f, (255, 255, 255), tr)


def fire_x(frame: Image.Image) -> float:
    """Horizontale Lage des Kaminfeuers (0–1): helle, stark orange Bereiche."""
    a = np.asarray(frame.convert("RGB").resize((480, 270))).astype(np.float32)
    warm = np.clip((a[..., 0] - 190) / 65, 0, 1) * np.clip((a[..., 0] - a[..., 2] - 70) / 80, 0, 1)
    return 0.5 if warm.sum() < 5 else float((warm.sum(axis=0) * np.arange(480)).sum() / warm.sum() / 480)


def fire_right(frame: Image.Image) -> Image.Image:
    """Rolf 09.10.: Steht der Kamin links, wird das Hauptbild gespiegelt (vor den Veo-Clips, also kostenlos) – so ist
    der Kamin immer rechts und der Thumbnail-Text immer oben links. Das Grundbild enthält keine Schrift."""
    return ImageOps.mirror(frame) if fire_x(frame) < 0.5 else frame


def make_thumbnail(frame: Image.Image, duration: str, out: Path, side: str = "left") -> Path:
    """Thumbnail C (Rolf 09.10.): Textblock oben links über den Fenstern (Kamin rechts, siehe fire_right), großes
    „4K UHD“ + Dauer, 1280×720 JPEG. side="right" nur als Ausnahme."""
    W, H = 3840, 2160
    C = grade(frame.convert("RGB").resize((W, H), Image.LANCZOS))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    xr = xx if side == "left" else (W - 1 - xx)
    m = np.clip(1.15 - yy / (H * 0.62), 0, 1) ** 1.3 * np.clip(1.25 - xr / (W * 0.62), 0, 1) ** 1.1
    C.paste(Image.new("RGB", C.size, (6, 5, 4)), (0, 0), Image.fromarray((m * 175).astype(np.uint8)))
    f4, f1, fs = font(118, "Black"), font(270), font(84, "Bold")
    cw = _tw("4K UHD", f4, 6) + 100
    chip_w = (_tw(duration, font(64 * 1.18, "Bold"), 8 * 1.18) + 70 * 1.18 + 50) if duration else 0
    block_w = max(cw + chip_w, _tw(TITLE_1, f1, 4), _tw(SUBLINE, fs, 18) + 10)

    def x_of(w):   # linksbündig bzw. rechtsbündig im Block
        return 150 if side == "left" else W - 150 - w

    y = 140
    xc = x_of(cw + chip_w)
    ImageDraw.Draw(C).rounded_rectangle([xc, y, xc + cw, y + 185], 26, fill=GOLD)
    _draw(ImageDraw.Draw(C), (xc + 50, y + 26), "4K UHD", f4, INK, 6)
    if duration:
        _chip(C, xc + cw + 50, y + 28, duration, 1.18)
    y += 250
    _shadow_text(C, (x_of(_tw(TITLE_1, f1, 4)), y), TITLE_1, f1, (255, 255, 255), blur=30, track=4)
    _shadow_text(C, (x_of(_tw(TITLE_2, f1, 4)), y + 290), TITLE_2, f1, CABIN_GOLD, blur=30, track=4, glow=(255, 130, 40))
    _shadow_text(C, (x_of(_tw(SUBLINE, fs, 18)) + (10 if side == "left" else 0), y + 620), SUBLINE, fs,
                 (240, 240, 240), blur=16, track=18)
    del block_w
    out.parent.mkdir(parents=True, exist_ok=True)
    C.resize((1280, 720), Image.LANCZOS).save(out, "JPEG", quality=92)
    if out.stat().st_size > 2_000_000:
        C.resize((1280, 720), Image.LANCZOS).save(out, "JPEG", quality=82)
    return out


def short_overlay(question: str, out: Path, size: tuple[int, int] = (1080, 1920)) -> Path:
    """Text-Ebene (transparent) für einen Short im Design S1 v2."""
    SW, SH = size
    lines = [(250, TITLE_1, font(118), (255, 255, 255, 255), None),
             (385, TITLE_2, font(118), CABIN_GOLD + (255,), (255, 130, 40)),
             (1640, SUBLINE, font(38, "Bold"), (255, 236, 210, 255), None)]
    shadow = Image.new("L", (SW, SH), 0)
    glow = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    top = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    for y, t, f, fill, g in lines:
        ImageDraw.Draw(shadow).text((SW / 2, y), t, font=f, fill=255, anchor="ma")
        ImageDraw.Draw(top).text((SW / 2, y), t, font=f, fill=fill, anchor="ma")
        if g:
            gm = Image.new("L", (SW, SH), 0)
            ImageDraw.Draw(gm).text((SW / 2, y), t, font=f, fill=255, anchor="ma")
            gm = gm.filter(ImageFilter.GaussianBlur(30)).point(lambda v: v * 110 // 255)
            glow = Image.alpha_composite(glow, Image.merge("RGBA", [*(Image.new("L", (SW, SH), c) for c in g), gm]))
    sh = shadow.filter(ImageFilter.GaussianBlur(20)).point(lambda v: v * 200 // 255)
    lay = Image.alpha_composite(Image.alpha_composite(Image.merge("RGBA", [Image.new("L", (SW, SH), 6)] * 3 + [sh]), glow), top)
    d = ImageDraw.Draw(lay)
    fq = font(54, "Bold")
    w = d.textlength(question, font=fq)
    d.rounded_rectangle([SW / 2 - w / 2 - 40, 560, SW / 2 + w / 2 + 40, 560 + 98], 26, fill=(255, 255, 255, 235))
    d.text((SW / 2, 560 + 22 + 54 * 0.42), question, font=fq, fill=INK + (255,), anchor="mm")
    f4 = font(76)
    w4 = d.textlength("4K UHD", font=f4) + 80
    d.rounded_rectangle([SW / 2 - w4 / 2, 1500, SW / 2 + w4 / 2, 1618], 20, fill=GOLD + (255,))
    d.text((SW / 2, 1559), "4K UHD", font=f4, fill=INK + (255,), anchor="mm")
    out.parent.mkdir(parents=True, exist_ok=True)
    lay.save(out)
    return out
