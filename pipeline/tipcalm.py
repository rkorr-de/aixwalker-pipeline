"""Ruhiger Wellness-Look für Tipp-Shorts (Rolf 15.10.2026, 21:57):

„So schnell kann keiner lesen, der sich entspannen möchte … das Ganze soll chillig sein, wir machen hier Wellness, es
soll schön sein und zum Betrachten einladen.“

Prinzipien (wie erfolgreiche Relax-/Sleep-Kanäle):
- immer nur EIN Text im Bild, sanft ein- und ausgeblendet, je 6 s stehen lassen (genug Zeit zum Lesen und Atmen)
- elegante Typo: Kennzeile fein gesperrt (Manrope), Überschrift Cinzel Regular, Text Manrope Regular in Satzschreibung,
  Albumname in der Schreibschrift der Mix-Cover (GreatVibes) – keine Boxen, keine Badges, nichts blinkt
- Bild zum Versinken: sehr langsame Kamerafahrt (Zoom 1,00 → 1,06, leichter Schwenk), warmes Licht, das langsam durchs
  Bild wandert, weiche Vignette und ein dezenter Lichthof hinter dem Text
- Box-Atmung (entry["visual"] == "box_breathing"): ein feiner Kreis atmet 4 s ein · 4 s halten · 4 s aus · 4 s halten
- Schluss: „listen to the full mix“ + Albumname in Schreibschrift + „link in description“
Jedes Bild wird in Python sub-pixel-genau berechnet (kein Ruckeln) und roh an ffmpeg gegeben.
"""
import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from . import config, shorts
from .images import _draw_tracked, _font, _tracked_width, _wrap, crop_aspect

W, H = 1080, 1920
CREAM = (255, 244, 228)
TEXT_Y = 780                      # Mitte der Textzone (oberhalb der App-Knöpfe, unten rechts bleibt frei)
HOOK_SEC, LINE_SEC, END_SEC = 6.0, 6.4, 6.5
FADE_IN, FADE_OUT = 1.3, 1.0
BREATH = [("breathe in", 4.0), ("hold", 4.0), ("breathe out", 4.0), ("hold", 4.0)]
END_TEXT = {   # Genre des Ziel-Mixes → (große Zeile in Schreibschrift, ruhige Einladung)
    "Mediterranean Spa Lounge": ("Chillout Lounge Mix", "and let the day drift away"),
    "Dark Ambient Spa": ("Spa & Relaxation Mix", "breathe slowly and unwind"),
    "Chillout Sleep": ("Sleep Music Mix", "and drift into deep, calm sleep"),
    "Italian Chillout": ("Italian Chillout Mix", "for a slow, golden Italian evening"),
}
LABELS = {"SLEEP TIP": "SLEEP RITUAL", "RELAX TIP": "A MOMENT OF CALM", "DOLCE VITA": "DOLCE VITA"}


def _layer() -> Image.Image:
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def _glow_text(img: Image.Image, paint, blur: float = 16, alpha: int = 150) -> None:
    """Weicher, dunkler Hof hinter dem Text (lesbar auf hellen Fotos, ohne harte Kanten)."""
    m = Image.new("L", img.size, 0)
    paint(ImageDraw.Draw(m), 255)
    m = m.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(blur))
    m = m.point(lambda v: int(v * alpha / 255))
    shadow = Image.new("RGBA", img.size, (8, 10, 14, 0))
    shadow.putalpha(m)
    img.alpha_composite(shadow)


def _centered_block(lines: list[str], font, cy: int, lh: float, d: ImageDraw.ImageDraw):
    total = lh * len(lines)
    pos = []
    for i, ln in enumerate(lines):
        b = d.textbbox((0, 0), ln, font=font)
        x = (W - (b[2] - b[0])) / 2 - b[0]
        y = cy - total / 2 + i * lh + (lh - (b[3] - b[1])) / 2 - b[1]
        pos.append((x, y, ln))
    return pos


def _balanced_lines(d, text: str, font, max_w: int, max_lines: int = 3) -> list[str]:
    if d.textlength(text, font=font) <= max_w:
        return [text]
    words = text.split()
    best = None
    for k in range(1, len(words)):
        a, b = " ".join(words[:k]), " ".join(words[k:])
        wmax = max(d.textlength(a, font=font), d.textlength(b, font=font))
        if best is None or wmax < best[0]:
            best = (wmax, [a, b])
    if best and best[0] <= max_w:
        return best[1]
    return _wrap(d, text, font, max_w)[:max_lines]


def _text_sprite(lines: list[str], font, lh: float, cy: int = TEXT_Y, color=CREAM, glow=150) -> Image.Image:
    img = _layer()
    d = ImageDraw.Draw(img)
    pos = _centered_block(lines, font, cy, lh, d)
    _glow_text(img, lambda md, f: [md.text((x, y), s, font=font, fill=f) for x, y, s in pos], alpha=glow)
    d = ImageDraw.Draw(img)
    for x, y, s in pos:
        d.text((x, y), s, font=font, fill=color + (255,))
    return img


def _bbox_ok(img: Image.Image) -> tuple[int, int, int, int]:
    """Prüft den sicheren Bereich (ohne den weichen Hof): Text zwischen SAFE_TOP und SAFE_BOTTOM, unten rechts frei."""
    a = img.getchannel("A").point(lambda v: 255 if v > 200 else 0)
    bb = a.getbbox() or (0, 0, 0, 0)
    if bb[1] < shorts.SAFE_TOP - 10 or bb[3] > shorts.SAFE_BOTTOM + 10:
        raise ValueError(f"Text außerhalb des sicheren Bereichs: {bb}")
    corner = a.crop((925, 950, W, H)).getbbox()          # Like-/Kommentar-Spalte unten rechts muss frei bleiben
    if corner:
        raise ValueError(f"Text ragt in die Knopf-Spalte: {corner}")
    return bb


def build(art: Image.Image, entry: dict, out_dir: Path, album: str | None = None) -> dict:
    """Erzeugt Hintergrund, Lichteffekte und Text-Ebenen samt Zeitplan. Liefert ein dict für render()."""
    out_dir.mkdir(parents=True, exist_ok=True)
    a = art.convert("RGB")
    if abs(a.width / a.height - W / H) > 0.01:
        if a.width / a.height > W / H:
            cw = int(a.height * W / H)
            cx = int((a.width - cw) * (0.68 if entry.get("kind") == "dolcevita" else 0.5))
            a = a.crop((cx, 0, cx + cw, a.height))
        else:
            a = crop_aspect(a, 9, 16)
    zw, zh = int(W * 1.08) // 2 * 2, int(H * 1.08) // 2 * 2
    bg = a.resize((zw, zh), Image.LANCZOS)
    bg = ImageEnhance.Color(bg).enhance(1.05)
    bg = ImageEnhance.Brightness(bg).enhance(0.88)          # ein Hauch dunkler: ruhiger, Text lesbar
    bg.save(out_dir / "bg.jpg", quality=95)

    # Vignette + weicher Lichthof (dunkel) hinter der Textzone + Abdunklung unten (App-Bereich)
    shade = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shade)
    sd.ellipse((W / 2 - 620, TEXT_Y - 520, W / 2 + 620, TEXT_Y + 520), fill=110)
    shade = shade.filter(ImageFilter.GaussianBlur(170))
    # Vignette als weicher elliptischer Verlauf (numpy, ohne Stufen/Streifen)
    import numpy as np
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dist = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H * 0.46) / (H * 0.60)) ** 2)
    vmask = np.clip((dist - 0.62) / 0.55, 0, 1) ** 1.6 * 150
    vmask += np.random.default_rng(1).uniform(-1.5, 1.5, vmask.shape)       # Dither gegen Banding
    vig = Image.fromarray(np.clip(vmask, 0, 255).astype(np.uint8), "L")
    bottom = Image.new("L", (W, H), 0)
    bd = ImageDraw.Draw(bottom)
    for y in range(1250, H):
        bd.line([(0, y), (W, y)], fill=int(170 * ((y - 1250) / (H - 1250)) ** 1.4))
    from PIL import ImageChops
    m = ImageChops.lighter(ImageChops.lighter(shade, vig), bottom)
    overlay = Image.new("RGBA", (W, H), (6, 8, 12, 0))
    overlay.putalpha(m)
    overlay.save(out_dir / "overlay.png")

    # Warmes Licht, das langsam durchs Bild wandert
    lr = 520
    light = Image.new("L", (2 * lr, 2 * lr), 0)
    ImageDraw.Draw(light).ellipse((0, 0, 2 * lr, 2 * lr), fill=70)
    light = light.filter(ImageFilter.GaussianBlur(150))
    warm = Image.new("RGBA", light.size, (255, 196, 130, 0))
    warm.putalpha(light)
    warm.save(out_dir / "light.png")

    probe = ImageDraw.Draw(_layer())
    sprites = []        # (Datei, Start, Ende, Typ)

    # Kennzeile oben (bleibt die ganze Zeit, gibt Spät-Einsteigern Kontext)
    lab = LABELS.get(entry["label"].upper(), entry["label"].upper())
    fl = _font(config.FONT_BODY, 28, "SemiBold")
    tl = fl.size * 0.38
    lw = _tracked_width(probe, lab, fl, tl)
    label = _layer()
    ld = ImageDraw.Draw(label)
    ly = 330
    lx = (W - lw) / 2
    _glow_text(label, lambda md, f: _draw_tracked(md, (lx, ly), lab, fl, f, tl), blur=10, alpha=120)
    ld = ImageDraw.Draw(label)
    _draw_tracked(ld, (lx, ly), lab, fl, CREAM + (235,), tl)
    lb = ld.textbbox((0, 0), lab, font=fl)
    my = ly + (lb[1] + lb[3]) / 2
    for x0, x1 in ((lx - 26 - 70, lx - 26), (lx + lw + 26, lx + lw + 26 + 70)):
        ld.line([(x0, my), (x1, my)], fill=CREAM + (200,), width=2)
    label.save(out_dir / "label.png")
    _bbox_ok(label)

    # Überschrift (Cinzel Regular, elegant, Versalien)
    hook = entry["hook"].upper()
    size = 78
    while True:
        fh = _font(config.FONT_HEAD, size, "Regular")
        hl = _balanced_lines(probe, hook, fh, 860)
        if len(hl) <= 3 and all(probe.textlength(x, font=fh) <= 880 for x in hl) or size <= 52:
            break
        size -= 2
    hook_img = _text_sprite(hl, fh, fh.size * 1.28)
    hook_img.save(out_dir / "hook.png")
    _bbox_ok(hook_img)
    t = 0.0
    sprites.append(("hook.png", t, t + HOOK_SEC, "hook"))
    t += HOOK_SEC

    # Inhalt: Box-Atmung als atmender Kreis – sonst eine Aussage nach der anderen
    breath = None
    if entry.get("visual") == "box_breathing":
        fb = _font(config.FONT_BODY, 46, "Light")
        for i, (word, sec) in enumerate(BREATH):
            img = _layer()
            d = ImageDraw.Draw(img)
            tw = _tracked_width(d, word, fb, fb.size * 0.12)
            bb = d.textbbox((0, 0), word, font=fb)
            pos = ((W - tw) / 2, TEXT_Y - (bb[1] + bb[3]) / 2)
            _glow_text(img, lambda md, f: _draw_tracked(md, pos, word, fb, f, fb.size * 0.12), blur=12, alpha=140)
            d = ImageDraw.Draw(img)
            _draw_tracked(d, pos, word, fb, CREAM + (255,), fb.size * 0.12)
            img.save(out_dir / f"breath{i}.png")
            sprites.append((f"breath{i}.png", t, t + sec, "breath"))
            t += sec
        breath = {"start": HOOK_SEC, "phases": [s for _, s in BREATH]}
        t += 0.6
    else:
        fb = _font(config.FONT_BODY, 56, "Regular")
        for i, line in enumerate(entry["lines"]):
            ls = _balanced_lines(probe, line, fb, 820)
            img = _text_sprite(ls, fb, fb.size * 1.36)
            _bbox_ok(img)
            img.save(out_dir / f"line{i}.png")
            sprites.append((f"line{i}.png", t, t + LINE_SEC, "line"))
            t += LINE_SEC

    # Schluss (Rolf 15.10.2026, 22:13): nicht der Albumname groß, sondern WORAUF man hinaus will – das Genre des Mixes,
    # mit einer ruhigen Einladung. Der Albumname ist zweitrangig und steht nicht im Bild.
    phrase, invite = END_TEXT.get(entry.get("music_genre"), ("Chillout Mix", "and simply relax"))
    end = _layer()
    d = ImageDraw.Draw(end)
    f1 = _font(config.FONT_BODY, 28, "SemiBold")
    t1 = "LISTEN TO THE FULL"
    w1 = _tracked_width(d, t1, f1, f1.size * 0.32)
    fs = _font(config.FONT_SCRIPT, 128)
    while d.textlength(phrase, font=fs) > 860 and fs.size > 70:
        fs = _font(config.FONT_SCRIPT, fs.size - 6)
    nb = d.textbbox((0, 0), phrase, font=fs)
    f2 = _font(config.FONT_BODY, 40, "Light")
    w2 = d.textlength(invite, font=f2)
    i2 = d.textbbox((0, 0), invite, font=f2)
    f3 = _font(config.FONT_BODY, 24, "Regular")
    t3 = "link in description"
    w3 = _tracked_width(d, t3, f3, f3.size * 0.18)
    y1 = TEXT_Y - 170
    yn = TEXT_Y - 40 - (nb[1] + nb[3]) / 2
    y2 = TEXT_Y + 70 - i2[1]
    y3 = TEXT_Y + 155
    items = [((W - w1) / 2, y1, t1, f1, f1.size * 0.32), ((W - w3) / 2, y3, t3, f3, f3.size * 0.18)]

    def paint_end(md, f):
        for x, y, s_, fo, tr in items:
            _draw_tracked(md, (x, y), s_, fo, f, tr)
        md.text(((W - (nb[2] - nb[0])) / 2 - nb[0], yn), phrase, font=fs, fill=f)
        md.text(((W - w2) / 2, y2), invite, font=f2, fill=f)

    _glow_text(end, paint_end, blur=16, alpha=150)
    d = ImageDraw.Draw(end)
    for x, y, s_, fo, tr in items:
        _draw_tracked(d, (x, y), s_, fo, CREAM + (235,), tr)
    d.text(((W - (nb[2] - nb[0])) / 2 - nb[0], yn), phrase, font=fs, fill=(255, 226, 180, 255))
    d.text(((W - w2) / 2, y2), invite, font=f2, fill=CREAM + (245,))
    end.save(out_dir / "end.png")
    _bbox_ok(end)
    sprites.append(("end.png", t, t + END_SEC, "end"))
    dur = round(t + END_SEC, 2)

    plan = {"dur": dur, "sprites": sprites, "breath": breath}
    (out_dir / "plan.json").write_text(json.dumps(plan, indent=1))

    # Vorschau (Hintergrund + Hook) für Drive
    off = ((zw - W) // 2, (zh - H) // 2)
    prev = bg.crop((off[0], off[1], off[0] + W, off[1] + H)).convert("RGBA")
    for p in (overlay, label, hook_img):
        prev.alpha_composite(p)
    prev.convert("RGB").save(out_dir / "frame.png")
    return {"dir": out_dir, "dur": dur, "preview": out_dir / "frame.png", "plan": plan}


# ---------------------------------------------------------------- Rendern

def _smooth(x: float) -> float:
    x = 0.0 if x < 0 else 1.0 if x > 1 else x
    return x * x * (3 - 2 * x)


def _alpha_at(t: float, t0: float, t1: float, kind: str) -> tuple[float, float]:
    """Deckkraft und vertikaler Versatz (sanftes Aufsteigen beim Einblenden)."""
    if t < t0 - 0.001 or t > t1:
        return 0.0, 0.0
    if kind == "hook" and t0 == 0:
        a_in = 0.75 + 0.25 * _smooth(t / 0.9)          # ab Bild 1 lesbar, kommt sanft voll
    else:
        a_in = _smooth((t - t0) / FADE_IN)
    a_out = 1.0 if kind == "end" else _smooth((t1 - t) / FADE_OUT)
    if kind == "breath":                                 # Atem-Wörter: kurze, weiche Übergänge
        a_in = _smooth((t - t0) / 0.6)
        a_out = _smooth((t1 - t) / 0.6)
    dy = 14 * (1 - _smooth((t - t0) / FADE_IN)) if kind in ("line", "end") else 0.0
    return min(a_in, a_out), dy


def _with_alpha(img: Image.Image, a: float) -> Image.Image:
    if a >= 0.999:
        return img
    out = img.copy()
    out.putalpha(img.getchannel("A").point(lambda v: int(v * a)))
    return out


def _crop_sprite(path: Path) -> tuple[Image.Image, tuple[int, int]]:
    im = Image.open(path).convert("RGBA")
    bb = im.getbbox() or (0, 0, 1, 1)
    return im.crop(bb), (bb[0], bb[1])


def _ring(frame: Image.Image, r: float, a: float) -> None:
    """Feiner, leicht leuchtender Atem-Kreis um die Textmitte."""
    if a <= 0.01:
        return
    size = int(2 * (r + 40))
    ring = Image.new("L", (size, size), 0)
    rd = ImageDraw.Draw(ring)
    c = size / 2
    rd.ellipse((c - r, c - r, c + r, c + r), outline=255, width=3)
    glow = ring.filter(ImageFilter.GaussianBlur(10)).point(lambda v: min(255, v * 3))
    from PIL import ImageChops
    m = ImageChops.lighter(ring, glow.point(lambda v: v // 2)).point(lambda v: int(v * a * 0.9))
    col = Image.new("RGBA", (size, size), CREAM + (0,))
    col.putalpha(m)
    frame.alpha_composite(col, dest=(int(W / 2 - c), int(TEXT_Y - c)))


def render(built: dict, wav: Path, start: float, out: Path, fps: int = 30) -> Path:
    d = Path(built["dir"])
    plan = built["plan"]
    dur = plan["dur"]
    bg = Image.open(d / "bg.jpg").convert("RGB")
    k = bg.width / W
    overlay = Image.open(d / "overlay.png").convert("RGBA")
    light = Image.open(d / "light.png").convert("RGBA")
    label, lo = _crop_sprite(d / "label.png")
    sprites = [(*_crop_sprite(d / f), t0, t1, kind) for f, t0, t1, kind in plan["sprites"]]
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(fps), "-i", "-", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", str(wav),
           "-filter_complex", f"[1:a]afade=t=in:d=1.5,afade=t=out:st={dur - 2.5:.2f}:d=2.5[aout]",
           "-map", "0:v", "-map", "[aout]", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.2f}", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    br = plan.get("breath")
    try:
        for n in range(int(round(dur * fps))):
            t = n / fps
            p = _smooth(t / dur)
            z = 1.0 + 0.06 * p                                   # kaum spürbar, aber lebendig
            src_w, src_h = bg.width / (k * z), bg.height / (k * z)
            cx = bg.width / 2 + 18 * (p - 0.5) * 2
            cy = bg.height / 2 - 12 * p
            sc = src_w / W
            frame = bg.transform((W, H), Image.AFFINE, (sc, 0, cx - src_w / 2, 0, sc, cy - src_h / 2),
                                 resample=Image.BICUBIC).convert("RGBA")
            # warmes Licht wandert langsam von links oben nach rechts
            lx = -300 + 900 * p + 60 * math.sin(t / 3.1)
            ly = 380 + 160 * math.sin(t / 5.3)
            frame.alpha_composite(_with_alpha(light, 0.55 + 0.25 * math.sin(t / 2.7) ** 2), dest=(int(lx), int(ly)))
            frame.alpha_composite(overlay)
            frame.alpha_composite(_with_alpha(label, 0.75 + 0.25 * _smooth(t / 1.2)), dest=lo)
            if br:
                t0 = br["start"]
                if t0 <= t <= t0 + sum(br["phases"]) + 0.6:
                    ph = br["phases"]
                    e = t - t0
                    r_min, r_max = 150, 260
                    if e < ph[0]:
                        r = r_min + (r_max - r_min) * _smooth(e / ph[0])
                    elif e < ph[0] + ph[1]:
                        r = r_max
                    elif e < ph[0] + ph[1] + ph[2]:
                        r = r_max - (r_max - r_min) * _smooth((e - ph[0] - ph[1]) / ph[2])
                    else:
                        r = r_min
                    a = _smooth(e / 0.8) * _smooth((t0 + sum(ph) + 0.6 - t) / 0.8)
                    _ring(frame, r, a)
            for spr, o, t0, t1, kind in sprites:
                a, dy = _alpha_at(t, t0, t1, kind)
                if a > 0.01:
                    frame.alpha_composite(_with_alpha(spr, a), dest=(o[0], max(0, int(o[1] + dy))))
            proc.stdin.write(frame.convert("RGB").tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="ignore")
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg: {err[-400:]}")
    except Exception:
        proc.kill()
        raise
    return out
