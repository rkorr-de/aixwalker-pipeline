"""Shorts 2.0 (Rolf 15.10.2026, 22:26): Bewegtbild (Veo-Clip, ruhige Zeitlupe) + Text, der sich Wort für Wort aufbaut.

- Bild: 15-s-Clip aus Kling 3.0 (Bild-zu-Video) in Originaltempo – keine Zeitlupe (ruckelte); Vignette + Filmkorn
- Text: ein Satz nach dem anderen, Wort für Wort (sanft einblenden + leicht aufsteigen); *Wort* = Schlüsselwort in
  Kaushan Script (größer, warmes Creme), Rest Kaushan Script weiß; weicher Schatten, keine Kästen
- Formate: normal, „breathing“ (atmender Kreis: breathe in · hold · breathe out), „split“ (A oben, B unten)
- Schluss: „Full-length“ + Genre-Mix (Schlüsselwort-Stil) + Pfeil nach unten (zum verknüpften Video)
Jedes Bild wird in Python zusammengesetzt (sub-pixel-genau) und roh an ffmpeg gegeben.
"""
import math
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import config, shorts

W, H = 1080, 1920
# Rolf 15.10.2026, 23:51: Kaushan Script für alle Texte (Pinsel-Schreibschrift, OFL); Schlüsselwort größer + Creme
FONT_SANS = config.ASSETS / "fonts" / "KaushanScript-Regular.ttf"
FONT_SERIF_I = FONT_SANS
WHITE = (255, 255, 255)
CREAM = (255, 232, 196)
BREATH = (3.5, 1.0, 3.5)          # Sekunden: ein, halten, aus (passt in einen 15-s-Clip)
BREATH_START = 3.4
TEXT_CY = 560                     # Mitte der Textzone (oberes Drittel, Gesichter liegen meist tiefer)
GENRE_CTA = {"Mediterranean Spa Lounge": "Chillout Lounge mix", "Dark Ambient Spa": "Spa & Relax mix",
             "Chillout Sleep": "Sleep Music mix", "Italian Chillout": "Italian Chillout mix",
             "Cozy Winter Cabin": "Cozy Cabin mix"}


def _sans(size: int, weight: str = "SemiBold"):
    f = ImageFont.truetype(str(FONT_SANS), size)
    try:
        f.set_variation_by_name(weight)
    except Exception:  # noqa: BLE001
        pass
    return f


def _serif(size: int):
    return ImageFont.truetype(str(FONT_SERIF_I), size)


def _smooth(x: float) -> float:
    x = 0.0 if x < 0 else 1.0 if x > 1 else x
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- Text-Layout: Wörter als einzelne Sprites

def _tokens(text: str) -> list[tuple[str, bool]]:
    """„and the evening is finally *yours*“ → [(and,False)…,(yours,True)]; *mehrere Wörter* möglich."""
    out = []
    for part in re.split(r"(\*[^*]+\*)", text):
        if not part:
            continue
        hl = part.startswith("*") and part.endswith("*")
        if not hl and out and part[0] in ".,!?…:;":       # Satzzeichen direkt hinter *Wort* ohne Leerzeichen
            punct = part.split()[0] if part.split() else ""
            lead = len(punct) - len(punct.lstrip(".,!?…:;"))
            out[-1] = (out[-1][0] + punct[:lead], out[-1][1])
            part = part[lead:]
        for w in part.strip("*").split():
            out.append((w, hl))
    return out


def _wrap(toks, widths, sp, max_w):
    lines, cur, cw = [], [], 0.0
    for (w, hl), wd in zip(toks, widths):
        add = wd if not cur else cw + sp + wd
        if cur and add > max_w:
            lines.append((cur, cw))
            cur, cw = [(w, hl, wd)], wd
        else:
            cur.append((w, hl, wd))
            cw = add
    if cur:
        lines.append((cur, cw))
    return lines


def layout_sentence(text: str, cy: int = TEXT_CY, size: int = 100, max_w: int = 900) -> list[dict]:
    """Liefert je Wort {img, x, y} – Zeilen mittig, Schlüsselwörter in Serif kursiv (1,35× größer)."""
    probe = ImageDraw.Draw(Image.new("L", (10, 10)))
    while True:
        fs, fi = _sans(size), _serif(int(size * 1.22))
        sp = probe.textlength(" ", font=fs)
        toks = _tokens(text)
        widths = [probe.textlength(w, font=fi if hl else fs) for w, hl in toks]
        lines, cur, cw = [], [], 0.0
        for (w, hl), wd in zip(toks, widths):
            add = wd if not cur else cw + sp + wd
            if cur and add > max_w:
                lines.append((cur, cw))
                cur, cw = [(w, hl, wd)], wd
            else:
                cur.append((w, hl, wd))
                cw = add
        if cur:
            lines.append((cur, cw))
        if len(lines) <= 3 or size <= 50:
            break
        size -= 4
    # Ausgewogener Umbruch: kleinste Breite mit gleicher Zeilenzahl (kein einzelnes Wort allein in der letzten Zeile)
    if len(lines) > 1 and max_w > 400:
        lo = int(max(wd for wd in widths)) + 1
        for mw in range(lo, int(max_w), 10):
            trial = _wrap(toks, widths, sp, mw)
            if len(trial) == len(lines):
                lines = trial
                break
    lh = size * 1.32
    top = cy - lh * len(lines) / 2
    asc = fs.getmetrics()[0]
    words = []
    for li, (ln, lw) in enumerate(lines):
        x = (W - lw) / 2
        base = top + li * lh + asc                    # gemeinsame Grundlinie je Zeile
        for w, hl, wd in ln:
            f = fi if hl else fs
            bb = probe.textbbox((0, 0), w, font=f, anchor="ls")
            pad = 40
            img = Image.new("RGBA", (int(bb[2] - bb[0]) + 2 * pad, int(bb[3] - bb[1]) + 2 * pad), (0, 0, 0, 0))
            ox, oy = pad - bb[0], pad - bb[1]
            m = Image.new("L", img.size, 0)
            ImageDraw.Draw(m).text((ox, oy), w, font=f, fill=255, anchor="ls")
            sh = m.filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.75))
            shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
            shadow.putalpha(sh)
            img.alpha_composite(shadow)
            ImageDraw.Draw(img).text((ox, oy), w, font=f, fill=(CREAM if hl else WHITE) + (255,), anchor="ls")
            words.append({"img": img, "x": x - ox, "y": base - oy})
            x += wd + sp
    _check(words)
    return words


def _check(words: list[dict]) -> None:
    for wd in words:
        x0, y0 = wd["x"] + 40, wd["y"] + 40
        x1, y1 = wd["x"] + wd["img"].width - 40, wd["y"] + wd["img"].height - 40
        if y0 < shorts.SAFE_TOP - 20 or y1 > shorts.SAFE_BOTTOM:
            raise ValueError(f"Text außerhalb des sicheren Bereichs: {(x0, y0, x1, y1)}")
        if y1 > 950 and x1 > 925:
            raise ValueError("Text ragt in die Knopf-Spalte")


def layout_cta(genre: str, cy: int = 640) -> list[dict]:
    """Schluss: kleine Zeile „Full-length“, darunter der Genre-Mix als Schlüsselwort, darunter ein feiner Pfeil."""
    probe = ImageDraw.Draw(Image.new("L", (10, 10)))
    items = []
    small = "Full-length"
    fs = _sans(60)
    track = 0.02 * fs.size
    sw = sum(probe.textlength(c, font=fs) for c in small) + track * (len(small) - 1)
    img = Image.new("RGBA", (int(sw) + 80, 160), (0, 0, 0, 0))
    m = Image.new("L", img.size, 0)
    md, d = ImageDraw.Draw(m), ImageDraw.Draw(img)
    x = 40
    for c in small:
        md.text((x, 40), c, font=fs, fill=255)
        x += probe.textlength(c, font=fs) + track
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh.putalpha(m.filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * 0.7)))
    img.alpha_composite(sh)
    x = 40
    for c in small:
        d.text((x, 40), c, font=fs, fill=WHITE + (235,))
        x += probe.textlength(c, font=fs) + track
    items.append({"img": img, "x": (W - img.width) / 2, "y": cy - 175})
    big = layout_sentence(f"*{GENRE_CTA.get(genre, 'chillout mix')}*", cy=cy + 14, size=74, max_w=880)
    items += big
    # Pfeil
    ar = Image.new("RGBA", (120, 140), (0, 0, 0, 0))
    ad = ImageDraw.Draw(ar)
    ad.line([(60, 20), (60, 100)], fill=WHITE + (230,), width=3)
    ad.line([(38, 78), (60, 104), (82, 78)], fill=WHITE + (230,), width=3, joint="curve")
    items.append({"img": ar, "x": (W - 120) / 2, "y": cy + 90})
    return items


# ---------------------------------------------------------------- Zeitplan

def timeline(beats: list[str], genre: str, breathing: bool = False, dur: float = 15.0) -> tuple[list[dict], float]:
    """Elemente mit Start/Ende; Wörter je Satz versetzt (0,16 s)."""
    els = []
    t = -0.25                                  # erster Satz: erstes Wort ist im ersten Bild schon halb da
    first = layout_sentence(beats[0])
    for i, w in enumerate(first):
        els.append({**w, "t0": t + i * 0.16, "t1": 6.0 if not breathing else 3.2, "rise": 14})
    if breathing:
        t = BREATH_START
        for word, sec in (("breathe in", BREATH[0]), ("hold", BREATH[1]), ("breathe out", BREATH[2])):
            for w in layout_sentence(word, size=66):
                els.append({**w, "t0": t, "t1": t + sec - 0.1, "rise": 0, "fade": 0.5})
            t += sec
        els.append({"ring": True, "t0": BREATH_START, "t1": t + 0.3})
        cta_at = t + 0.2
        dur = max(dur, cta_at + 3.4)
    else:
        if len(beats) > 1:
            second = layout_sentence(beats[1])
            for i, w in enumerate(second):
                els.append({**w, "t0": 6.5 + i * 0.16, "t1": 10.6, "rise": 14})
        cta_at = 11.0
        dur = max(dur, cta_at + 4.0)
    for w in layout_cta(genre):
        els.append({**w, "t0": cta_at + (0.25 if "ring" not in w else 0), "t1": dur + 1, "rise": 10, "fade": 0.7})
    return els, dur


def _alpha(el: dict, t: float) -> tuple[float, float]:
    fade = el.get("fade", 0.45)
    a_in = _smooth((t - el["t0"]) / fade)
    a_out = _smooth((el["t1"] - t) / 0.5)
    a = min(a_in, a_out)
    dy = el.get("rise", 0) * (1 - _smooth((t - el["t0"]) / 0.6))
    return a, dy


def _ring(frame: Image.Image, e: float) -> None:
    """Atem-Kreis: einatmen (größer), halten, ausatmen (kleiner) – Takt aus BREATH."""
    bi, bh, bo = BREATH
    if e < bi:
        r = 130 + 120 * _smooth(e / bi)
    elif e < bi + bh:
        r = 250
    else:
        r = 250 - 120 * _smooth((e - bi - bh) / bo)
    a = _smooth(e / 0.6) * _smooth((bi + bh + bo + 0.3 - e) / 0.6)
    if a <= 0.01:
        return
    size = int(2 * r + 80)
    m = Image.new("L", (size, size), 0)
    c = size / 2
    ImageDraw.Draw(m).ellipse((c - r, c - r, c + r, c + r), outline=255, width=3)
    glow = m.filter(ImageFilter.GaussianBlur(9))
    from PIL import ImageChops
    mm = ImageChops.lighter(m, glow.point(lambda v: min(255, v * 2))).point(lambda v: int(v * a * 0.95))
    col = Image.new("RGBA", (size, size), WHITE + (0,))
    col.putalpha(mm)
    frame.alpha_composite(col, dest=(int(W / 2 - c), int(TEXT_CY - c)))


# ---------------------------------------------------------------- Video

def slow_clip(src: Path, dst: Path, factor: float, crop_half: bool = False) -> Path:
    """Verlangsamt den Clip mit Bewegungs-Interpolation auf 30 fps und skaliert auf 1080×1920 (bzw. 1080×960)."""
    h = 960 if crop_half else H
    # Interpolation in 720 px Breite (in voller Größe ~9 Min. je Clip auf 2 Kernen), danach weich hochskaliert
    vf = (f"scale=720:-2:flags=lanczos,setpts={factor}*PTS,"
          f"minterpolate=fps=30:mi_mode=mci:mc_mode=obmc:me_mode=bidir,"
          f"scale={W}:-2:flags=lanczos,crop={W}:{h},format=rgb24")
    subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-i", str(src), "-an", "-vf", vf,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p", str(dst)],
                   check=True)
    return dst


def prep_clip(src: Path, dst: Path, crop_half: bool = False) -> Path:
    """Nur skalieren/zuschneiden – Originaltempo und -bildrate (Kling liefert 15 s am Stück, keine Zeitlupe nötig)."""
    h = 960 if crop_half else H
    vf = f"scale={W}:-2:flags=lanczos,crop={W}:{h},format=rgb24"
    subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-i", str(src), "-an", "-vf", vf,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-pix_fmt", "yuv420p", str(dst)],
                   check=True)
    return dst


def _probe(path: Path) -> tuple[float, float]:
    """(Dauer s, Bildrate fps)"""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=r_frame_rate:format=duration", "-of", "default=nw=1", str(path)],
                         capture_output=True, text=True).stdout
    vals = dict(l.split("=", 1) for l in out.split() if "=" in l)
    num, _, den = vals.get("r_frame_rate", "30/1").partition("/")
    return float(vals.get("duration", 8)), float(num) / float(den or 1)


def _frames(path: Path, w: int, h: int):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE)
    n = w * h * 3
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        yield Image.frombytes("RGB", (w, h), buf)
    p.wait()


def render(clip: Path, beats: list[str], genre: str, wav: Path, start: float, out: Path,
           clip_b: Path | None = None, breathing: bool = False, labels: tuple[str, str] | None = None) -> Path:
    work = out.parent / (out.stem + "_work")
    work.mkdir(parents=True, exist_ok=True)
    els, dur = timeline(beats, genre, breathing)
    split = clip_b is not None
    src_len, src_fps = _probe(clip)
    if src_len >= dur - 0.6:                   # Kling 15 s: Originaltempo, ruckelfrei
        a = prep_clip(clip, work / "a.mp4", crop_half=split)
        b = prep_clip(clip_b, work / "b.mp4", crop_half=True) if split else None
        fps = round(src_fps) or 24
    else:                                      # alter Weg (Veo 8 s): Zeitlupe
        factor = round((dur + 0.5) / src_len, 3)
        a = slow_clip(clip, work / "a.mp4", factor, crop_half=split)
        b = slow_clip(clip_b, work / "b.mp4", factor, crop_half=True) if split else None
        fps = 30
    # Leichte Abdunklung oben (Text) – statisch
    shade = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shade)
    for y in range(H):
        v = int(120 * max(0.0, 1 - y / 1050) ** 1.4) + (int(150 * ((y - 1300) / 620) ** 1.5) if y > 1300 else 0)
        sd.line([(0, y), (W, y)], fill=min(255, v))
    shade_rgba = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shade_rgba.putalpha(shade)
    if split and labels:                       # Ortsnamen an der Trennlinie (A oben, B unten)
        els += [{**w, "t0": 0.3, "t1": dur + 1, "rise": 0} for w in layout_sentence(f"*{labels[0]}*", cy=900, size=40)]
        els += [{**w, "t0": 0.5, "t1": dur + 1, "rise": 0} for w in layout_sentence(f"*{labels[1]}*", cy=1020, size=40)]
    n_frames = int(round(dur * fps))
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(fps), "-i", "-", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", str(wav),
           "-filter_complex", f"[0:v]vignette=PI/5,noise=alls=5:allf=t,format=yuv420p[v];"
                              f"[1:a]afade=t=in:d=0.12,afade=t=out:st={dur - 1.6:.2f}:d=1.6[aout]",
           "-map", "[v]", "-map", "[aout]", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.2f}", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    ga = _frames(a, W, 960 if split else H)
    gb = _frames(b, W, 960) if split else None
    last_a = last_b = None
    try:
        for n in range(n_frames):
            t = n / fps
            fa = next(ga, None) or last_a
            last_a = fa
            if split:
                fb = next(gb, None) or last_b
                last_b = fb
                frame = Image.new("RGB", (W, H))
                frame.paste(fa, (0, 0))
                frame.paste(fb, (0, 960))
                frame = frame.convert("RGBA")
                ImageDraw.Draw(frame).line([(0, 960), (W, 960)], fill=(255, 255, 255, 200), width=3)
            else:
                frame = fa.convert("RGBA")
            frame.alpha_composite(shade_rgba)
            for el in els:
                if el.get("ring"):
                    if el["t0"] <= t <= el["t1"]:
                        _ring(frame, t - el["t0"])
                    continue
                al, dy = _alpha(el, t)
                if al <= 0.01:
                    continue
                img = el["img"]
                if al < 0.999:
                    img = img.copy()
                    img.putalpha(el["img"].getchannel("A").point(lambda v, al=al: int(v * al)))
                frame.alpha_composite(img, dest=(int(round(el["x"])), int(round(el["y"] + dy))))
            proc.stdin.write(frame.convert("RGB").tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="ignore")
        if proc.wait() != 0:
            raise RuntimeError(err[-500:])
    except Exception:
        proc.kill()
        raise
    return out
