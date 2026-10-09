"""Cover, Album-Art und Thumbnails: Bildmotiv über Nano Banana (Gemini Image), Typografie mit Pillow."""
import base64
import io
import math
import random
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import config, costs

STYLE_SUFFIX = config.IMAGE_STYLE[config.DEFAULT_GENRE]   # Standard: heller, warmer Lounge-Look


def style_for(genre: str | None) -> str:
    """Bildstil je Genre (siehe config.IMAGE_STYLE)."""
    return config.IMAGE_STYLE.get(genre or "", STYLE_SUFFIX)


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


def generate_art(prompt: str, aspect: str = "1:1", pro: bool = False, timeout: int = 180,
                 style: str | None = None, image_size: str | None = None) -> Image.Image:
    """Erzeugt ein Bildmotiv. Ohne API-Key wird ein prozedurales Fallback-Bild erzeugt."""
    if not config.GOOGLE_API_KEY:
        return procedural_art(aspect)
    model = config.IMAGE_MODEL_PRO if pro else config.IMAGE_MODEL
    url = f"{config.GEMINI_BASE}/models/{model}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt + (style if style is not None else STYLE_SUFFIX)}]}],
        "generationConfig": {"responseModalities": ["IMAGE"],
                             "imageConfig": {"aspectRatio": aspect}},
    }
    if image_size and pro:   # hohe Auflösung fürs Hauptbild (Album-Cover 3000×3000 und Thumbnail aus einem Bild)
        body["generationConfig"]["imageConfig"]["imageSize"] = image_size
    last = None
    for attempt in range(3):
        try:
            r = requests.post(url, headers={"x-goog-api-key": config.GOOGLE_API_KEY,
                                            "Content-Type": "application/json"},
                              json=body, timeout=timeout)
            if r.status_code == 400 and "imageSize" in body["generationConfig"]["imageConfig"]:
                print(f"[images] Auflösung {image_size} abgelehnt, ohne Größenangabe neu: {r.text[:160]}")
                body["generationConfig"]["imageConfig"].pop("imageSize")
                r = requests.post(url, headers={"x-goog-api-key": config.GOOGLE_API_KEY,
                                                "Content-Type": "application/json"},
                                  json=body, timeout=timeout)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            data = _find_inline_image(r.json())
            if not data:
                raise RuntimeError(f"kein Bild in Antwort: {r.text[:300]}")
            sized = "imageSize" in body["generationConfig"]["imageConfig"]
            costs.count(("image_pro_4k" if sized and image_size == "4K" else "image_pro") if pro else "image_flash")
            return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"[images] Versuch {attempt + 1} fehlgeschlagen: {e}")
    print(f"[images] Fallback auf prozedurales Bild: {last}")
    costs.count("image_failed")
    return procedural_art(aspect)


def procedural_art(aspect: str = "1:1", seed: int | None = None) -> Image.Image:
    """Ersatzmotiv ohne API (Dry-Run, Notfall): warmer Sonnenuntergangs-Verlauf über Meer, damit der Look stimmt."""
    rnd = random.Random(seed)
    w, h = (1024, 1024) if aspect == "1:1" else (1344, 768)
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    horizon = int(h * rnd.uniform(0.52, 0.62))
    sky = [(255, 196, 120), (246, 128, 92), (122, 92, 150)]
    for y in range(horizon):
        t = y / horizon
        c = [int(sky[2][k] * (1 - t) + sky[1][k] * t) if t < 0.6 else int(sky[1][k] * (1 - (t - .6) / .4) + sky[0][k] * (t - .6) / .4) for k in range(3)]
        d.line([(0, y), (w, y)], fill=tuple(c))
    for y in range(horizon, h):
        t = (y - horizon) / (h - horizon)
        c = (int(40 + 30 * (1 - t)), int(150 - 60 * t), int(170 - 50 * t))
        d.line([(0, y), (w, y)], fill=c)
    sx = int(w * rnd.uniform(0.3, 0.7))
    d.ellipse([sx - w // 14, horizon - w // 9, sx + w // 14, horizon + w // 60], fill=(255, 226, 160))
    for i in range(40):
        y = horizon + int((h - horizon) * (i / 40) ** 1.5)
        d.line([(sx - 10 - i * 3, y), (sx + 10 + i * 3, y)], fill=(255, 210, 150), width=2)
    return img.filter(ImageFilter.GaussianBlur(2))


def _font(path: Path, size: int, weight: str | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(path), max(8, int(size)))
    want = weight or ("Bold" if "Manrope" in str(path) or "Cinzel" in str(path) else
                      "ExtraBold" if "Montserrat" in str(path) else None)
    if want:
        try:
            f.set_variation_by_name(want)
        except Exception:  # noqa: BLE001 – keine Variable Font
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


# ---------------------------------------------------------------- Vorlage (Look ab 08.10.2026)
# Gleich auf Thumbnail, Album-Cover, Track-Cover und Short: helles Motiv ohne dunklen Verlauf, mittig groß der
# Genre-Begriff (Montserrat ExtraBold, gesperrt), darunter der Albumname in Schreibschrift, Lesbarkeit nur über weiche
# Schatten direkt an der Schrift, oben rechts die Dauer, unten links klein „AIX WALKER".

def duration_label(total_min: int | None) -> str:
    if not total_min:
        return ""
    if total_min < 55:
        return f"{total_min} MIN"
    hours = round(total_min / 60 * 2) / 2
    return f"{hours:g} HOUR" + ("" if hours == 1 else "S")


def _tracked_width(draw, text, font, track):
    return sum(draw.textlength(ch, font=font) for ch in text) + track * max(0, len(text) - 1)


def _draw_tracked(draw, xy, text, font, fill, track):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + track


def _fit_tracked(draw, text, path, max_w, start, min_size, track_em, weight=None):
    size = start
    while size > min_size:
        f = _font(path, size, weight)
        if _tracked_width(draw, text, f, f.size * track_em) <= max_w:
            return f
        size -= 4
    return _font(path, min_size, weight)


def _soft_shadow(img: Image.Image, paint, radius: float, alpha: int, offset: tuple[int, int] = (0, 0)) -> None:
    """Weicher Schatten: `paint(draw)` zeichnet die Form weiß auf eine Maske, die verwischt und dunkel aufgelegt wird."""
    m = Image.new("L", img.size, 0)
    paint(ImageDraw.Draw(m))
    m = m.filter(ImageFilter.GaussianBlur(radius))
    if offset != (0, 0):
        m = _shift(m, offset)
    shade = Image.new("RGB", img.size, (8, 10, 14))
    img.paste(shade, (0, 0), m.point(lambda v: v * alpha // 255))


def _shift(m: Image.Image, off: tuple[int, int]) -> Image.Image:
    out = Image.new("L", m.size, 0)
    out.paste(m, off)
    return out


def _title_lines(d, kw: str, max_w: int, start: int, min_size: int):
    """Genre-Begriff in 1 oder 2 Zeilen: lange Begriffe („CHILLOUT LOUNGE MUSIC") werden zweizeilig und dafür groß."""
    one = _fit_tracked(d, kw, config.FONT_HEAD, max_w, start, min_size, 0.03, "Bold")
    words = kw.split()
    if one.size >= start * 0.8 or len(words) < 2:
        return [kw], one
    best = None
    for i in range(1, len(words)):
        l1, l2 = " ".join(words[:i]), " ".join(words[i:])
        longer = l1 if _tracked_width(d, l1, one, 0) >= _tracked_width(d, l2, one, 0) else l2
        f = _fit_tracked(d, longer, config.FONT_HEAD, max_w, int(start * 0.92), min_size, 0.03, "Bold")
        if best is None or f.size > best[1].size:
            best = ([l1, l2], f)
    return best if best[1].size > one.size * 1.15 else ([kw], one)


def _title_block(img: Image.Image, keyword: str, album: str | None, cy: int, max_w: int, scale: float,
                 kw_start: float = 0.16, subline: str | None = None, one_line: bool = False,
                 top_y: int | None = None) -> tuple[int, int]:
    """Zeichnet Genre-Begriff (1–2 Zeilen, Cinzel) + Albumname (Schreibschrift) zentriert um `cy`
    (mit `top_y`: Oberkante des Blocks fest dort). Liefert (oben, unten)."""
    w, h = img.size
    d = ImageDraw.Draw(img)
    if one_line:   # Ibiza-Linie (Rolf 09.10.2026): Genre-Begriff immer auf EINER Zeile
        lines = [keyword.upper()]
        fk = _fit_tracked(d, lines[0], config.FONT_HEAD, max_w, int(h * kw_start), int(h * 0.04), 0.03, "Bold")
    else:
        lines, fk = _title_lines(d, keyword.upper(), max_w, int(h * kw_start), int(h * 0.05))
    tk = fk.size * 0.03
    lh = int(fk.size * 1.02)
    boxes = [d.textbbox((0, 0), ln, font=fk) for ln in lines]
    kw_h = lh * (len(lines) - 1) + (boxes[-1][3] - boxes[0][1])
    fs = None
    sub_h = 0
    if subline:    # Unterzeile (z. B. „CHILLOUT DEEP HOUSE“) in derselben Antiqua, kleiner
        sub_txt = subline.upper()
        fs = _fit_tracked(d, sub_txt, config.FONT_HEAD, int(max_w * 0.80), int(fk.size * 0.48), int(h * 0.025),
                          0.12, "Bold")
        sb = d.textbbox((0, 0), sub_txt, font=fs)
        sub_h = sb[3] - sb[1]
    fa = None
    if album:
        fa = _fit_text(d, album, config.FONT_SCRIPT, int(max_w * 0.95), int(fk.size * 1.45), int(h * 0.06))
        ab = d.textbbox((0, 0), album, font=fa)
        al_w, al_h = ab[2] - ab[0], ab[3] - ab[1]
    gap = int(fk.size * 0.10)
    gap_sub = int(fk.size * 0.18)                    # Luft Titel → Unterzeile
    sub_block = (gap_sub + sub_h + int(fk.size * 0.14)) if subline else 0   # + Luft für Schreibschrift-Oberlängen
    total = kw_h + sub_block + (gap + al_h if album else 0)
    top = cy - total // 2 if top_y is None else top_y
    pos = [((w - _tracked_width(d, ln, fk, tk)) / 2, top - boxes[0][1] + i * lh) for i, ln in enumerate(lines)]
    if subline:
        ts = fs.size * 0.12
        sx, sy = (w - _tracked_width(d, sub_txt, fs, ts)) / 2, top + kw_h + gap_sub - sb[1]
        pos_sub = (sx, sy)
    if album:
        ax, ay = (w - al_w) / 2 - ab[0], top + kw_h + sub_block + gap - ab[1]

    def paint(md):
        for (x, y), ln in zip(pos, lines):
            _draw_tracked(md, (x, y), ln, fk, 255, tk)
        if subline:
            _draw_tracked(md, pos_sub, sub_txt, fs, 255, ts)
        if album:
            md.text((ax, ay), album, font=fa, fill=255)
    # Lesbarkeit auf hellem Himmel (Rolf 08.10.): weicher dunkler Hof + gestufter 3D-Tiefenschatten nach rechts unten
    _soft_shadow(img, paint, radius=max(6, fk.size * 0.30), alpha=150)
    _soft_shadow(img, paint, radius=max(3, fk.size * 0.08), alpha=170, offset=(int(5 * scale), int(6 * scale)))
    d = ImageDraw.Draw(img)
    depth = max(3, int(fk.size * 0.06))
    for i in range(depth, 0, -1):                       # Extrusion: dunkles Warmbraun, nach vorne heller
        t = i / depth
        col = (int(40 + 30 * (1 - t)), int(26 + 20 * (1 - t)), int(18 + 12 * (1 - t)))
        for (x, y), ln in zip(pos, lines):
            _draw_tracked(d, (x + i, y + i), ln, fk, col, tk)
        if album:
            d.text((ax + i * 0.7, ay + i * 0.7), album, font=fa, fill=col)
        if subline:
            _draw_tracked(d, (pos_sub[0] + i * 0.6, pos_sub[1] + i * 0.6), sub_txt, fs, col, ts)
    for (x, y), ln in zip(pos, lines):
        _draw_tracked(d, (x, y), ln, fk, config.WHITE, tk)
    if subline:
        _draw_tracked(d, pos_sub, sub_txt, fs, config.CREAM, ts)
    if album:
        d.text((ax, ay), album, font=fa, fill=config.CREAM)
    return top, top + total


def _corner_labels(img: Image.Image, scale: float, duration: str = "", mark: bool = True,
                   duration_bottom: bool = False) -> None:
    """Dauer oben rechts (bzw. mit `duration_bottom` unten rechts auf Höhe von AIX WALKER), AIX WALKER unten links."""
    w, h = img.size
    m = int(min(w, h) * 0.05)
    d = ImageDraw.Draw(img)
    items = []
    if duration:
        fd = _font(config.FONT_TITLE, h * 0.05, "Bold")
        tw = _tracked_width(d, duration, fd, fd.size * 0.12)
        db = d.textbbox((0, 0), duration, font=fd)
        y = h - m - db[3] if duration_bottom else m
        items.append(((w - m - tw, y), duration, fd, fd.size * 0.12, config.WHITE))
    if mark:
        fm = _font(config.FONT_TITLE, min(w, h) * 0.028, "SemiBold")
        bb = d.textbbox((0, 0), "AIX WALKER", font=fm)
        items.append(((m, h - m - (bb[3] - bb[1]) - bb[1]), "AIX WALKER", fm, fm.size * 0.35, config.WHITE))

    def paint(md):
        for (x, y), t, f, tr, _ in items:
            _draw_tracked(md, (x, y), t, f, 255, tr)
    if items:
        _soft_shadow(img, paint, radius=max(3, h * 0.014), alpha=200)
        d = ImageDraw.Draw(img)
        sh = max(1, int(min(w, h) * 0.003))
        for (x, y), t, f, tr, col in items:
            _draw_tracked(d, (x + sh, y + sh), t, f, (30, 20, 14), tr)   # harter kleiner Schatten → auch auf Weiß lesbar
            _draw_tracked(d, (x, y), t, f, col, tr)


def crop_aspect(img: Image.Image, aw: int, ah: int, bias_y: float = 0.5) -> Image.Image:
    """Größtmöglicher Ausschnitt im Seitenverhältnis aw:ah aus `img`, ohne Skalierung. Damit entstehen
    Album-Cover (1:1) und Thumbnail (16:9) aus DEMSELBEN Hauptbild (Wiedererkennung Video ↔ Stores, Rolf 08.10.)."""
    w, h = img.size
    if w / h > aw / ah:
        nw = int(h * aw / ah)
        x = (w - nw) // 2
        return img.crop((x, 0, x + nw, h))
    nh = int(w * ah / aw)
    y = int((h - nh) * bias_y)
    return img.crop((0, y, w, y + nh))


def _smoothstep(x: np.ndarray, a: float, b: float) -> np.ndarray:
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def orange_teal(img: Image.Image, strength: float = 1.0) -> Image.Image:
    """Kinematografischer Orange-&-Teal-Look: warme, gesättigte Lichter (Sonne, Glühen, Laternen) werden kräftig
    orange-gold, alles Kühle, Neutrale und Dunkle (Himmel oben, Meer, Schatten) wird in Teal/Türkis getaucht."""
    a = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    r, b = a[..., 0], a[..., 2]
    lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
    chroma = a.max(-1) - a.min(-1)
    warm = (_smoothstep(chroma, 0.12, 0.40) * _smoothstep(lum, 0.10, 0.40) * _smoothstep(r - b, 0.05, 0.25))[..., None]
    teal = lum[..., None] * np.array([0.60, 1.06, 1.12], np.float32) + np.array([0.0, 0.025, 0.035], np.float32)
    orange = lum[..., None] + (a - lum[..., None]) * 1.25                       # Sättigung hoch
    orange = orange * np.array([1.06, 1.0, 0.82], np.float32) + np.array([0.0, 0.05, 0.0], np.float32) * warm
    graded = warm * orange + (1 - warm) * (0.25 * a + 0.75 * teal)
    out = np.clip(a + (graded - a) * strength, 0, 1)
    out = out + 0.18 * (out - 0.5) * (1 - np.abs(2 * out - 1))                  # filmische S-Kurve
    return Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8))


def color_grade(img: Image.Image, genre: str | None) -> Image.Image:
    """Farblook je Genre (config.COLOR_GRADE); ohne Eintrag bleibt das Bild unverändert."""
    return orange_teal(img) if genre in config.COLOR_GRADE else img


def master_art(scene: str, genre: str | None) -> Image.Image:
    """Ein Hauptbild je Mix: quadratisch und hoch aufgelöst; Cover nutzt es ganz, Thumbnail einen 16:9-Ausschnitt."""
    img = generate_art(scene + " Square master image: keep the main subject and the calm open area for the title in "
                       "the central horizontal band, so a wide 16:9 crop from the middle shows the same scene.",
                       "1:1", pro=True, style=style_for(genre), image_size="4K")
    img = color_grade(img, genre)
    print(f"[images] Hauptbild {img.size[0]}×{img.size[1]}")
    return img


def _cover_crop(art: Image.Image, w: int, h: int) -> Image.Image:
    aw, ah = art.size
    sc = max(w / aw, h / ah)
    img = art.resize((int(aw * sc) + 1, int(ah * sc) + 1), Image.LANCZOS)
    return img.crop(((img.width - w) // 2, (img.height - h) // 2, (img.width - w) // 2 + w, (img.height - h) // 2 + h))


def make_thumbnail(art: Image.Image, keyword: str, album: str, out: Path, duration: str = "",
                   w: int = 1280, h: int = 720, text_scale: float = 1.0, subline: str | None = None,
                   one_line: bool = False, title_top: bool = False) -> Path:
    """YouTube-Thumbnail im neuen Look: helles Motiv, mittig Genre-Begriff + Albumname, Dauer oben rechts.
    text_scale > 1 macht Genre-Begriff und Albumname größer (config.THUMB_TEXT_SCALE, z. B. Italien-Linie).
    title_top (config.THUMB_TITLE_TOP, Ibiza): Titelblock oben im Himmel, Dauer unten rechts neben AIX WALKER."""
    img = _cover_crop(art, w, h).convert("RGB")
    _title_block(img, keyword, album, cy=int(h * 0.47), max_w=int(w * min(0.94, 0.80 * text_scale)), scale=h / 720,
                 kw_start=0.16 * text_scale, subline=subline, one_line=one_line,
                 top_y=int(h * 0.075) if title_top else None)
    _corner_labels(img, h / 720, duration, duration_bottom=title_top)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=92)
    if out.stat().st_size > 2_000_000:
        img.save(out, "JPEG", quality=80)
    return out


def make_album_cover(art: Image.Image, keyword: str, album: str, out: Path, size: int = 3000,
                     text_scale: float = 1.0, subline: str | None = None, one_line: bool = False,
                     title_top: bool = False) -> Path:
    """Album-Cover (DistroKid, 3000×3000) – gleicher Look und gleicher Name wie das Thumbnail.
    title_top (config.THUMB_TITLE_TOP): Titelblock oben im Himmel statt mittig (Rolf 09.10.)."""
    img = _cover_crop(art, size, size).convert("RGB")
    _title_block(img, keyword, album, cy=int(size * 0.5), max_w=int(size * min(0.94, 0.84 * text_scale)),
                 scale=size / 720, kw_start=0.11 * text_scale, subline=subline, one_line=one_line,
                 top_y=int(size * 0.08) if title_top else None)
    _corner_labels(img, size / 720, "")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    return out


def make_track_cover(art: Image.Image, title: str, track_no: int, album: str, out: Path, size: int = 1400) -> Path:
    """Track-Cover (MP3-Tag und Videobild): gleicher Look – Tracktitel groß, darunter der Albumname in Schreibschrift."""
    img = _cover_crop(art, size, size).convert("RGB")
    _title_block(img, title, album, cy=int(size * 0.5), max_w=int(size * 0.84), scale=size / 720, kw_start=0.10)
    _corner_labels(img, size / 720, "")   # keine Tracknummer mehr im Cover (Rolf 08.10.2026: im Komplettvideo unnötig)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    return out


def remove_track_label(img: Image.Image) -> Image.Image:
    """Ältere Track-Cover (bis 08.10.2026) tragen „TRACK 10“ fest oben rechts. In Zusammenschnitten (Samstags-/Monats-Mix)
    wird diese Nummer entfernt – keine Tracknummern im Komplettvideo (Rolf 08.10.2026). Retusche: die Schriftfläche wird
    aus der Umgebung aufgefüllt (OpenCV-Inpainting) und weich eingeblendet; ohne OpenCV starkes Verwischen."""
    img = img.convert("RGB").copy()
    w, h = img.size
    m = int(min(w, h) * 0.05)
    d = ImageDraw.Draw(img)
    fd = _font(config.FONT_TITLE, h * 0.05, "Bold")
    tw = max(_tracked_width(d, f"TRACK {n}", fd, fd.size * 0.12) for n in ("00", "88", "99", "08", "10"))
    grow = int(max(10, h * 0.02))
    text_box = (int(max(0, w - m - tw - grow)), int(max(0, m - grow)), w, int(min(h, m + fd.size * 1.3 + grow)))
    pad = int(max(14, h * 0.04))
    box = (max(0, text_box[0] - pad), 0, w, min(h, text_box[3] + pad))
    region = img.crop(box)
    tmask = Image.new("L", region.size, 0)
    ImageDraw.Draw(tmask).rectangle([text_box[0] - box[0], text_box[1] - box[1], region.size[0], text_box[3] - box[1]],
                                    fill=255)
    try:
        import cv2
        arr = cv2.cvtColor(np.asarray(region), cv2.COLOR_RGB2BGR)
        fixed = cv2.inpaint(arr, np.asarray(tmask), int(max(6, fd.size * 0.25)), cv2.INPAINT_TELEA)
        filled = Image.fromarray(cv2.cvtColor(fixed, cv2.COLOR_BGR2RGB)).filter(ImageFilter.GaussianBlur(fd.size * 0.45))
    except Exception:  # noqa: BLE001 – Ersatz ohne OpenCV
        filled = region.filter(ImageFilter.GaussianBlur(max(20, fd.size * 1.6)))
    from PIL import ImageChops
    soft = tmask.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(pad * 0.6))
    core = tmask.filter(ImageFilter.MinFilter(2 * (grow // 2) + 1)).filter(ImageFilter.GaussianBlur(grow * 0.7))
    soft = ImageChops.lighter(soft, core)           # Schrift voll deckend, Kanten weich (Rand = Puffer `grow`)
    img.paste(filled, box[:2], soft)
    return img


def add_subscribe_badge(img: Image.Image) -> Image.Image:
    """Dezenter Abo-Hinweis unten rechts (Musik-Zuschauer abonnieren selten von selbst)."""
    w, h = img.size
    s = h / 1080
    d = ImageDraw.Draw(img, "RGBA")
    f = _font(config.FONT_BODY, int(30 * s))
    text = f"SUBSCRIBE  ·  {config.CHANNEL_HANDLE.upper()}"
    tw = d.textlength(text, font=f)
    pad, tri = int(22 * s), int(34 * s)
    bw, bh = int(tw + 2 * pad + tri + 14 * s), int(f.size + 2 * pad * 0.7)
    x1, y1 = w - int(48 * s), h - int(44 * s)
    x0, y0 = x1 - bw, y1 - bh
    d.rounded_rectangle([x0, y0, x1, y1], radius=int(bh / 2), fill=(5, 10, 12, 205), outline=config.TEAL, width=max(2, int(3 * s)))
    cy = (y0 + y1) / 2
    tx = x0 + pad
    d.polygon([(tx, cy - tri * 0.4), (tx, cy + tri * 0.4), (tx + tri * 0.7, cy)], fill=config.TEAL)
    d.text((tx + tri + 14 * s, cy - f.size * 0.6), text, font=f, fill=config.WHITE)
    return img


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
    add_subscribe_badge(bg)
    out.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out, "PNG")
    return out
