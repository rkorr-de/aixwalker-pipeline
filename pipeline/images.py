"""Cover, Album-Art und Thumbnails: Bildmotiv über Nano Banana (Gemini Image), Typografie mit Pillow."""
import base64
import io
import math
import random
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import config

STYLE_SUFFIX = (
    " Cinematic, moody, dark teal and charcoal palette with a single warm highlight, "
    "high contrast, photorealistic, shallow depth of field, no text, no letters, no watermark, no logos."
)


def _find_inline_image(obj):
    if isinstance(obj, dict):
        for key in ("inlineData", "inline_data"):
            d = obj.get(key)
            if isinstance(d, dict) and d.get("data"):
                mime = d.get("mimeType") or d.get("mime_type") or ""
                if mime.startswith("image") or not mime:
                    return d["data"]
        for v in obj.values():
            r = _find_inline_image(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_inline_image(v)
            if r:
                return r
    return None


def generate_art(prompt: str, aspect: str = "1:1", pro: bool = False, timeout: int = 180) -> Image.Image:
    """Erzeugt ein Bildmotiv. Ohne API-Key wird ein prozedurales Fallback-Bild erzeugt."""
    if not config.GOOGLE_API_KEY:
        return procedural_art(aspect)
    model = config.IMAGE_MODEL_PRO if pro else config.IMAGE_MODEL
    url = f"{config.GEMINI_BASE}/models/{model}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt + STYLE_SUFFIX}]}],
        "generationConfig": {"responseModalities": ["IMAGE"],
                             "imageConfig": {"aspectRatio": aspect}},
    }
    last = None
    for attempt in range(3):
        try:
            r = requests.post(url, headers={"x-goog-api-key": config.GOOGLE_API_KEY,
                                            "Content-Type": "application/json"},
                              json=body, timeout=timeout)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            data = _find_inline_image(r.json())
            if not data:
                raise RuntimeError(f"kein Bild in Antwort: {r.text[:300]}")
            return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"[images] Versuch {attempt + 1} fehlgeschlagen: {e}")
    # Kein stilles Platzhalter-Bild in einem echten Lauf: lieber abbrechen, als ein falsches Thumbnail/Cover zu veröffentlichen.
    raise RuntimeError(f"Bildgenerierung fehlgeschlagen (kein Fallback in echten Läufen): {last}")


def procedural_art(aspect: str = "1:1", seed: int | None = None) -> Image.Image:
    """Dunkles Verlaufsbild mit Lichtflecken, als Notfall-Motiv und für Dry-Runs."""
    rnd = random.Random(seed)
    w, h = (1024, 1024) if aspect == "1:1" else (1344, 768)
    img = Image.new("RGB", (w, h), config.BG)
    d = ImageDraw.Draw(img)
    for _ in range(6):
        cx, cy = rnd.randint(0, w), rnd.randint(0, h)
        r = rnd.randint(w // 4, w // 2)
        col = rnd.choice([config.BG2, (20, 48, 52), (30, 70, 72), (90, 60, 40)])
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    img = img.filter(ImageFilter.GaussianBlur(w // 8))
    d = ImageDraw.Draw(img)
    for i in range(0, w, 64):
        d.line([(i, 0), (i, h)], fill=(20, 40, 44), width=1)
    for j in range(0, h, 64):
        d.line([(0, j), (w, j)], fill=(20, 40, 44), width=1)
    return img


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(path), size)
    if "Manrope" in str(path):
        try:
            f.set_variation_by_name("Bold")
        except Exception:  # noqa: BLE001
            pass
    return f


def _fit_text(draw, text, font_path, max_w, start_size, min_size=40):
    size = start_size
    while size > min_size:
        f = _font(font_path, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return _font(font_path, min_size)


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def _darken_bottom(img: Image.Image, strength: float = 0.75) -> Image.Image:
    w, h = img.size
    overlay = Image.new("L", (w, h), 0)
    od = ImageDraw.Draw(overlay)
    for y in range(h // 2, h):
        a = int(255 * strength * ((y - h / 2) / (h / 2)) ** 1.3)
        od.line([(0, y), (w, y)], fill=a)
    black = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(black, img, overlay)


def make_track_cover(art: Image.Image, title: str, track_no: int, album: str, out: Path, size: int = 1400) -> Path:
    img = art.resize((size, size), Image.LANCZOS)
    img = _darken_bottom(img, 0.85)
    d = ImageDraw.Draw(img)
    m = int(size * 0.07)
    small = _font(config.FONT_BODY, int(size * 0.026))
    d.text((m, m), f"{config.ARTIST.upper()}  ·  {album.upper()}", font=small, fill=config.TEAL)
    d.text((m, m + int(size * 0.04)), f"TRACK {track_no:02d}", font=small, fill=config.GREY)
    f = _fit_text(d, title.upper(), config.FONT_DISPLAY, size - 2 * m, int(size * 0.16), int(size * 0.08))
    lines = _wrap(d, title.upper(), f, size - 2 * m)
    lh = int(f.size * 0.95)
    y = size - m - lh * len(lines)
    for ln in lines:
        d.text((m, y), ln, font=f, fill=config.WHITE)
        y += lh
    d.rectangle([m, size - m + int(size * 0.02), m + int(size * 0.08), size - m + int(size * 0.026)], fill=config.TEAL)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    return out


def make_album_cover(art: Image.Image, album: str, subtitle: str, out: Path, size: int = 3000) -> Path:
    img = art.resize((size, size), Image.LANCZOS)
    img = _darken_bottom(img, 0.8)
    d = ImageDraw.Draw(img)
    m = int(size * 0.07)
    small = _font(config.FONT_BODY, int(size * 0.028))
    d.text((m, m), config.ARTIST.upper(), font=small, fill=config.TEAL)
    f = _fit_text(d, album.upper(), config.FONT_DISPLAY, size - 2 * m, int(size * 0.17), int(size * 0.08))
    lines = _wrap(d, album.upper(), f, size - 2 * m)
    lh = int(f.size * 0.95)
    sub = _font(config.FONT_BODY, int(size * 0.03))
    y = size - m - lh * len(lines) - int(size * 0.05)
    for ln in lines:
        d.text((m, y), ln, font=f, fill=config.WHITE)
        y += lh
    d.text((m, y + int(size * 0.01)), subtitle.upper(), font=sub, fill=config.GREY)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    return out


def make_thumbnail(art: Image.Image, headline: str, sub: str, out: Path, w: int = 1280, h: int = 720) -> Path:
    """YouTube-Thumbnail: Motiv rechts, Textblock links, hoher Kontrast, max. 3 Wörter Headline."""
    aw, ah = art.size
    scale = max(w / aw, h / ah)
    img = art.resize((int(aw * scale), int(ah * scale)), Image.LANCZOS)
    img = img.crop(((img.width - w) // 2, (img.height - h) // 2, (img.width - w) // 2 + w, (img.height - h) // 2 + h))
    # linke Seite abdunkeln
    overlay = Image.new("L", (w, h), 0)
    od = ImageDraw.Draw(overlay)
    for x in range(int(w * 0.65)):
        a = int(210 * (1 - x / (w * 0.65)) ** 1.2)
        od.line([(x, 0), (x, h)], fill=a)
    img = Image.composite(Image.new("RGB", (w, h), (5, 10, 12)), img, overlay)
    d = ImageDraw.Draw(img)
    m = 64
    f = _fit_text(d, headline.upper(), config.FONT_DISPLAY, int(w * 0.6), 190, 90)
    lines = _wrap(d, headline.upper(), f, int(w * 0.6))
    lh = int(f.size * 0.92)
    subf = _font(config.FONT_BODY, 44)
    total = lh * len(lines) + 70
    y = (h - total) // 2
    for ln in lines:
        # Schatten
        d.text((m + 6, y + 6), ln, font=f, fill=(0, 0, 0))
        d.text((m, y), ln, font=f, fill=config.WHITE)
        y += lh
    d.rectangle([m, y + 14, m + 120, y + 22], fill=config.TEAL)
    d.text((m + 140, y + 2), sub.upper(), font=subf, fill=config.TEAL)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=92)
    if out.stat().st_size > 2_000_000:
        img.save(out, "JPEG", quality=80)
    return out


def make_video_frame(cover_png: Path, out: Path, w: int = 1920, h: int = 1080) -> Path:
    """Videobild pro Track: unscharfer Hintergrund aus dem Cover, Cover mittig."""
    cover = Image.open(cover_png).convert("RGB")
    bg = cover.resize((w, w), Image.LANCZOS).crop((0, (w - h) // 2, w, (w - h) // 2 + h))
    bg = bg.filter(ImageFilter.GaussianBlur(40))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    bg = Image.blend(bg, dark, 0.45)
    side = int(h * 0.78)
    c = cover.resize((side, side), Image.LANCZOS)
    shadow = Image.new("RGBA", (side + 80, side + 80), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([40, 40, side + 40, side + 40], fill=(0, 0, 0, 180))
    shadow = shadow.filter(ImageFilter.GaussianBlur(30))
    x, y = (w - side) // 2, (h - side) // 2
    bg.paste(shadow, (x - 40, y - 30), shadow)
    bg.paste(c, (x, y))
    out.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out, "PNG")
    return out
