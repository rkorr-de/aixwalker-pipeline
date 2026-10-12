"""YouTube Shorts aus dem fertigen Mix: beste Passagen finden, 9:16-Video rendern, Metadaten.

Auswahl der Passagen (datenbasiert, kein Raten):
- Energieverlauf (RMS) und spektrale Helligkeit des Mixes in 1-s-Fenstern
- je Track: Beginn des Hauptteils (Beat/volle Energie setzt ein und hält) – dort startet der Clip, auf einem Schlag
- Bewertung: Energie im Clip, Energie gleich in den ersten 3 s, Rhythmus (Onsets), Helligkeit
- Zwei Clips aus verschiedenen Tracks mit großem Abstand, jeder komplett innerhalb seines Tracks
"""
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import config, metadata
from .images import _fit_text, _font, _wrap


def _load_mono(path: Path, sr: int) -> np.ndarray:
    """Audio speichersparend als Mono-float32 laden (ffmpeg), auch für 3-Stunden-Mixe."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def _smooth(x: np.ndarray, n: int) -> np.ndarray:
    if n <= 1 or len(x) < n:
        return x
    k = np.ones(n) / n
    return np.convolve(x, k, mode="same")


def find_passages(mix_wav: Path, starts: list[float], total_sec: float, clip_sec: int = 45,
                  count: int = 2, min_gap_sec: float = 600) -> list[dict]:
    """Liefert `count` Passagen [{start, end, track_index, score, main_at}] – jede startet am Beginn des Hauptteils
    eines Tracks (dort, wo Beat/volle Energie einsetzt und bleibt), exakt auf einem Schlag, nie im Intro.

    Hintergrund (Rolf, 07.10.2026): Shorts, die leise oder vor dem Beat beginnen, werden sofort weggewischt.
    Vorgehen je Track: Energie (RMS) in 0,25-s-Schritten, geglättet über 2 s. Hauptteil = erste Stelle nach dem
    Intro, an der die Energie ≥ 85 % des Track-Niveaus (75. Perzentil) erreicht und 8 s lang hält. Start wird auf den
    nächsten Onset/Schlag gelegt; der ganze Clip liegt innerhalb des Tracks (kein Übergang im Short).
    """
    import librosa
    sr = 8000
    y = _load_mono(mix_wav, sr)
    hop = sr // 4                                   # 0,25 s
    rms = librosa.feature.rms(y=y, frame_length=hop * 2, hop_length=hop, center=True)[0]
    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    cent = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop)[0]
    n = min(len(rms), len(onset), len(cent))
    rms, onset, cent = rms[:n], onset[:n], cent[:n]
    fps = sr / hop
    env = _smooth(rms, int(2 * fps))
    gmax = float(np.percentile(env, 99)) + 1e-9
    bounds = list(starts) + [total_sec]
    min_gap_sec = min(min_gap_sec, total_sec / 3)
    cands: list[dict] = []
    for idx in range(len(starts)):
        t0, t1 = bounds[idx] + 2.0, bounds[idx + 1] - 3.0          # Überblendungen meiden
        if t1 - t0 < clip_sec + 10:
            continue
        a, b = int(t0 * fps), int(t1 * fps)
        seg = env[a:b]
        level = float(np.percentile(seg, 75))
        hold = int(8 * fps)
        main = None
        for j in range(0, len(seg) - hold):
            if seg[j] >= 0.85 * level and seg[j:j + hold].min() >= 0.7 * level:
                main = j
                break
        if main is None:
            continue
        # Glättung verzögert: im ungeglätteten Pegel rückwärts den echten Einsatz suchen (erste Stelle ≥ 60 %
        # des Niveaus in den 3 s davor), dann auf den kräftigsten Onset ±0,5 s legen (= erster Schlag)
        raw_level = float(np.percentile(rms[a:b], 75))
        lo = max(a, a + main - int(3 * fps))
        hit = next((k for k in range(lo, a + main + 1) if rms[k] >= 0.6 * raw_level), a + main)
        w0, w1 = max(a, hit - int(0.5 * fps)), min(b, hit + int(0.5 * fps) + 1)
        beat = w0 + int(np.argmax(onset[w0:w1])) if w1 > w0 else hit
        st = max(bounds[idx] + 2.0, beat / fps - 0.25)  # Onset-Frame ist 0,25 s breit → knapp davor starten
        if st + clip_sec > t1:
            st = t1 - clip_sec                          # Clip bleibt im Track
            if st < bounds[idx] + 2.0:
                continue
        c0, c1 = int(st * fps), int((st + clip_sec) * fps)
        win = env[c0:c1] / gmax
        head = env[c0:c0 + int(3 * fps)] / gmax         # erste 3 s müssen schon „da" sein
        score = (0.40 * float(win.mean()) + 0.25 * float(head.mean())
                 + 0.20 * float(onset[c0:c1].mean() / (onset.max() + 1e-9)) * 4
                 + 0.15 * float(cent[c0:c1].mean() / (cent.max() + 1e-9)))
        if head.mean() < 0.8 * win.mean():              # Start leiser als der Rest → kein guter Einstieg
            score *= 0.6
        cands.append({"start": round(st, 2), "end": round(st + clip_sec, 2), "track_index": idx,
                      "score": float(score), "main_at": round(bounds[idx] + 2.0 + main / fps, 2)})
    chosen: list[dict] = []
    for c in sorted(cands, key=lambda c: -c["score"]):
        if any(abs(c["start"] - x["start"]) < min_gap_sec for x in chosen):
            continue
        chosen.append(c)
        if len(chosen) == count:
            break
    for c in sorted(cands, key=lambda c: -c["score"]):     # Abstand nicht einhaltbar → trotzdem anderer Track
        if len(chosen) == count:
            break
        if all(c["track_index"] != x["track_index"] for x in chosen):
            chosen.append(c)
    while len(chosen) < count and total_sec > clip_sec * 2:   # Notlösung, sollte praktisch nie greifen
        t = float(int(total_sec * (len(chosen) + 1) / (count + 1)))
        idx = max(i for i, s0 in enumerate(starts) if s0 <= t) if starts else 0
        chosen.append({"start": t, "end": t + clip_sec, "track_index": idx, "score": 0.0, "main_at": t})
    return sorted(chosen, key=lambda c: c["start"])


# Sicherer Bereich im 9:16-Short (gemessen am echten Handy-Screenshot, Rolf 11.10.2026): oben Lupe/Menü (bis ≈ 170 px),
# unten Kanalname, Titel, „KI“/„Öffentlich“ und Knöpfe ab ≈ 1330 px, rechts die Like-/Kommentar-Spalte ab x ≈ 930,
# y ≈ 1000. Unsere Elemente bleiben zwischen SAFE_TOP und SAFE_BOTTOM; im unteren Teil nur mittig und schmal.
SAFE_TOP, SAFE_BOTTOM = 190, 1270
LOW_MAX_W = 700          # max. Breite der Elemente unterhalb von y ≈ 950 (Abstand zur Knopf-Spalte rechts)
GAP = 44


def _extrude(img: Image.Image, paint_white, draw_col, size: int, scale: float = 1.0) -> None:
    """Weicher Hof + 3D-Tiefenschatten wie auf Thumbnail/Cover (`paint_white(draw)` malt die Form, `draw_col(draw, dx, dy, col)` farbig)."""
    from .images import _soft_shadow
    _soft_shadow(img, paint_white, radius=max(6, size * 0.30), alpha=150)
    _soft_shadow(img, paint_white, radius=max(3, size * 0.08), alpha=170, offset=(int(5 * scale), int(6 * scale)))
    d = ImageDraw.Draw(img)
    depth = max(3, int(size * 0.06))
    for i in range(depth, 0, -1):
        t = i / depth
        draw_col(d, i, i, (int(40 + 30 * (1 - t)), int(26 + 20 * (1 - t)), int(18 + 12 * (1 - t))))


def make_short_frame(art: Image.Image, cover_png: Path | None, headline: str, track_title: str, out: Path,
                     w: int = 1080, h: int = 1920, total_min: int | None = None, album: str | None = None,
                     keyword: str | None = None, note: str = "no vocals") -> Path:
    """9:16-Bild „einladend statt Textwand“ (Rolf 11.10.2026): das Hauptbild randlos und scharf, oben Genre-Begriff +
    große Hook-Zeile, unten Albumname + leuchtender Knopf „FULL MIX · 3 HOURS“ (pulsiert im Video mit der Musik).
    Nur 4 Textelemente, alles im sicheren Bereich. Regel für ALLE Linien (Rolf 12.10.): nie ein kleines Cover im Short –
    `cover_png` wird bewusst ignoriert; `track_title` und `note` bleiben für alte Aufrufe erhalten.
    Schreibt <out>.layout.json: „cover“ = Knopf (dort sitzt das atmende Licht), „text“ = Textflächen."""
    from PIL import ImageEnhance
    from .images import _draw_tracked, _fit_tracked, _tracked_width, crop_aspect, duration_label
    a = art.convert("RGB")
    if abs(a.width / a.height - w / h) > 0.01:
        a = crop_aspect(a, 9, 16)
    bg = a.resize((w, h), Image.LANCZOS)
    bg = ImageEnhance.Contrast(ImageEnhance.Color(bg).enhance(1.12)).enhance(1.05)
    # Verläufe: oben dezent für die Überschrift, unten für die App-Zone (dort steht nur YouTubes eigener Text)
    ov = Image.new("L", (w, h), 0)
    od = ImageDraw.Draw(ov)
    for yy in range(h):
        a_ = 0
        if yy < 720:
            a_ = int(150 * (1 - yy / 720) ** 1.7)
        elif yy > 1080:
            a_ = int(185 * ((yy - 1080) / (h - 1080)) ** 1.5)
        od.line([(0, yy), (w, yy)], fill=a_)
    bg = Image.composite(Image.new("RGB", (w, h), (6, 8, 12)), bg, ov)
    d = ImageDraw.Draw(bg)
    boxes: list[tuple[int, int, int, int]] = []

    # 1) Genre-Begriff als kleine gesperrte Zeile (sofort klar: MUSIK) …
    y = SAFE_TOP
    if keyword:
        kw = keyword.upper()
        fk = _fit_tracked(d, kw, config.FONT_TITLE, 780, 46, 30, 0.22, "Bold")
        tk = fk.size * 0.22
        kx = (w - _tracked_width(d, kw, fk, tk)) / 2
        kb = d.textbbox((0, 0), kw, font=fk)
        from .images import _soft_shadow
        _soft_shadow(bg, lambda md: _draw_tracked(md, (kx, y - kb[1]), kw, fk, 255, tk), radius=10, alpha=170)
        d = ImageDraw.Draw(bg)
        _draw_tracked(d, (kx, y - kb[1]), kw, fk, config.CREAM, tk)
        boxes.append((int(kx), y, int(kx + _tracked_width(d, kw, fk, tk)), y + kb[3] - kb[1]))
        y += kb[3] - kb[1] + 34
    # … darunter die Hook-Zeile groß in Cinzel mit 3D-Schatten (max. 2 Zeilen)
    hook = headline.upper().strip()
    size = 136
    while True:
        fh = _font(config.FONT_HEAD, size, "Bold")
        lines = _wrap(d, hook, fh, w - 2 * 90)
        if len(lines) <= 2 or size <= 72:
            break
        size -= 4
    lines = lines[:2]
    lh = int(fh.size * 1.04)
    hb = [d.textbbox((0, 0), ln, font=fh) for ln in lines]
    pos = [((w - (b[2] - b[0])) / 2 - b[0], y - hb[0][1] + i * lh) for i, (ln, b) in enumerate(zip(lines, hb))]

    def paint_hook(md):
        for (x, yy), ln in zip(pos, lines):
            md.text((x, yy), ln, font=fh, fill=255)

    _extrude(bg, paint_hook, lambda dd, dx, dy, col: [dd.text((x + dx, yy + dy), ln, font=fh, fill=col)
                                                      for (x, yy), ln in zip(pos, lines)], fh.size)
    d = ImageDraw.Draw(bg)
    for (x, yy), ln in zip(pos, lines):
        d.text((x, yy), ln, font=fh, fill=config.WHITE)
        bb = d.textbbox((x, yy), ln, font=fh)
        boxes.append((bb[0], bb[1], bb[2] + 8, bb[3] + 8))

    # 2) Unten: Knopf „▶ FULL MIX · 3 HOURS“ (endet an SAFE_BOTTOM) …
    dur = duration_label(total_min)
    label = f"FULL MIX · {dur}" if dur else "FULL MIX"
    fp = _fit_tracked(d, label, config.FONT_TITLE, LOW_MAX_W - 2 * 54 - 56, 44, 30, 0.10, "Bold")
    tp = fp.size * 0.10
    lb = d.textbbox((0, 0), label, font=fp)
    tri = int(fp.size * 0.78)
    pw = int(54 + tri + 26 + _tracked_width(d, label, fp, tp) + 54)
    ph = int(fp.size * 2.45)
    px0, py1 = (w - pw) // 2, SAFE_BOTTOM
    py0 = py1 - ph
    pill = (px0, py0, px0 + pw, py1)
    from .images import _soft_shadow
    _soft_shadow(bg, lambda md: md.rounded_rectangle(pill, radius=ph // 2, fill=255), radius=22, alpha=150,
                 offset=(0, 8))
    d = ImageDraw.Draw(bg)
    d.rounded_rectangle(pill, radius=ph // 2, fill=config.CREAM)
    cy = (py0 + py1) // 2
    tx0 = px0 + 54
    ink = (24, 26, 30)
    d.polygon([(tx0, cy - tri // 2), (tx0, cy + tri // 2), (tx0 + int(tri * 0.86), cy)], fill=ink)
    _draw_tracked(d, (tx0 + tri + 26, cy - (lb[1] + lb[3]) / 2), label, fp, ink, tp)
    # … darüber der Albumname in Schreibschrift (identisch zu Video-/Albumtitel)
    if album:
        fa = _fit_text(d, album, config.FONT_SCRIPT, LOW_MAX_W + 40, 150, 84)
        ab = d.textbbox((0, 0), album, font=fa)
        ax = (w - (ab[2] - ab[0])) / 2 - ab[0]
        ay = py0 - 40 - ab[3]

        def paint_album(md):
            md.text((ax, ay), album, font=fa, fill=255)

        _extrude(bg, paint_album, lambda dd, dx, dy, col: dd.text((ax + dx * 0.7, ay + dy * 0.7), album, font=fa,
                                                                   fill=col), fa.size)
        d = ImageDraw.Draw(bg)
        d.text((ax, ay), album, font=fa, fill=config.CREAM)
        bb = d.textbbox((ax, ay), album, font=fa)
        boxes.append((bb[0], bb[1], bb[2] + 6, bb[3] + 6))
    _check_no_overlap(boxes + [pill])
    out.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out, "PNG")
    Path(str(out) + ".layout.json").write_text(json.dumps({"cover": pill, "text": boxes, "kind": "pill"}))
    return out


def _check_no_overlap(boxes: list[tuple[int, int, int, int]]) -> None:
    """Sicherheitsnetz: kein Element darf ein anderes berühren oder unter SAFE_BOTTOM rutschen."""
    for i, a in enumerate(boxes):
        if a[3] > SAFE_BOTTOM + 10 or a[1] < SAFE_TOP - 10:
            raise ValueError(f"Short-Layout: Element {a} außerhalb des sicheren Bereichs ({SAFE_TOP}–{SAFE_BOTTOM})")
        if a[3] > 950 and a[2] > 925:
            raise ValueError(f"Short-Layout: Element {a} ragt unten rechts in die Like-/Kommentar-Knöpfe")
        for b_ in boxes[i + 1:]:
            if a[0] < b_[2] and b_[0] < a[2] and a[1] < b_[3] and b_[1] < a[3]:
                raise ValueError(f"Short-Layout: Überlagerung {a} / {b_}")


def build_short(frame_png: Path, mix_wav: Path, start: float, end: float, out: Path, fps: int = 30) -> Path:
    """Einfacher Short (Rückfallebene) 1080×1920: ruhiges Standbild ohne Zoom, Audioausschnitt mit kurzem Fade."""
    out.parent.mkdir(parents=True, exist_ok=True)
    dur = end - start
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y",
           "-loop", "1", "-framerate", str(fps), "-i", str(frame_png),
           "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", str(mix_wav),
           "-vf", "scale=1080:1920,format=yuv420p", "-af", f"afade=t=in:d=0.15,afade=t=out:st={dur - 1.5:.2f}:d=1.5",
           "-t", f"{dur:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-tune", "stillimage",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def short_metadata(concept: dict, idx: int, passage: dict, track_title: str, overlay: str,
                   full_url: str) -> tuple[str, str, list[str]]:
    """Titel (<100), Beschreibung, Tags für einen Short. #Shorts im Titel sorgt für Shelf-Einordnung."""
    base = concept.get("short_titles") or []
    title = base[idx] if idx < len(base) else f"{overlay} – {concept['album']} ({concept['bpm']} BPM) #Shorts"
    title = title.replace("#Shorts", "").strip()
    if concept["album"].lower() not in title.lower():          # Wiedererkennung: Albumname steht im Short-Titel
        title = f"{title} – {concept['album']}"
    kw = config.THUMB_KEYWORD.get(concept.get("genre", ""), "")
    if kw and "music" not in title.lower():                     # sofort klar, dass es Musik ist (Rolf 08.10.)
        title = f"{title} · {kw}"
    title = f"{title[:100 - len(' #Shorts')].rstrip()} #Shorts"
    desc = (f"{overlay}\n\n🎧 Full mix ({concept.get('total_min', 60)}+ min, {config.vocal_note(concept.get('genre'))}, no interruptions): {full_url}\n"
            f"Track: {track_title} · {concept['genre']} · {concept['bpm']} BPM\n"
            f"From the mix „{concept['album']}“ by {config.ARTIST} (AI-assisted, original music)\n\n"
            f"{' '.join(concept['hashtags'][:4])} #Shorts")
    tags = ["shorts", "music shorts", *concept["tags"][:12]]
    return title, desc, tags


def write_shorts_section(shorts: list[dict]) -> str:
    lines = []
    for i, s in enumerate(shorts, 1):
        lines.append(f"{i}. {metadata.fmt_ts(s['start'])}–{metadata.fmt_ts(s['end'])}  „{s['overlay']}“  "
                     f"Track: {s['track_title']}  Score {s['score']:.2f}  → {s.get('url', '(nicht hochgeladen)')}")
    return "\n".join(lines)
