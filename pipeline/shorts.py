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


# Sicherer Bereich im 9:16-Short: oben blendet YouTube die Kopfzeile ein, unten Titel/Kanal/Sound (≈ 22 %),
# rechts die Like-/Kommentar-Knöpfe. Alles Wichtige bleibt zwischen SAFE_TOP und SAFE_BOTTOM.
SAFE_TOP, SAFE_BOTTOM = 150, 1480
GAP = 44


def make_short_frame(art: Image.Image, cover_png: Path, headline: str, track_title: str, out: Path,
                     w: int = 1080, h: int = 1920, total_min: int | None = None, album: str | None = None) -> Path:
    """9:16-Bild ohne Überlagerungen: Hook oben, Cover, Albumname (Wiedererkennung), Track, Hinweis auf den Mix.
    Die Elemente werden nacheinander von oben nach unten gesetzt; das Cover schrumpft, falls der Platz nicht reicht.
    Zusätzlich wird <out>.layout.json mit Cover- und Textflächen geschrieben (für das atmende Licht im Video)."""
    aw, ah = art.size
    scale = max(w / aw, h / ah)
    bg = art.resize((int(aw * scale), int(ah * scale)), Image.LANCZOS)
    bg = bg.crop(((bg.width - w) // 2, (bg.height - h) // 2, (bg.width - w) // 2 + w, (bg.height - h) // 2 + h))
    bg = bg.filter(ImageFilter.GaussianBlur(18))
    bg = Image.blend(bg, Image.new("RGB", (w, h), (0, 0, 0)), 0.55)
    ov = Image.new("L", (w, h), 0)
    od = ImageDraw.Draw(ov)
    for yy in range(h):
        a_ = 0
        if yy < h * 0.3:
            a_ = int(190 * (1 - yy / (h * 0.3)) ** 1.5)
        elif yy > h * 0.65:
            a_ = int(210 * ((yy - h * 0.65) / (h * 0.35)) ** 1.3)
        od.line([(0, yy), (w, yy)], fill=a_)
    bg = Image.composite(Image.new("RGB", (w, h), (3, 8, 10)), bg, ov)
    d = ImageDraw.Draw(bg)
    m = 80
    boxes: list[tuple[int, int, int, int]] = []

    def centered(text, font, y, fill, shadow=False):
        tw = int(d.textlength(text, font=font))
        x = (w - tw) // 2
        if shadow:
            d.text((x + 5, y + 5), text, font=font, fill=(0, 0, 0))
        d.text((x, y), text, font=font, fill=fill)
        bb = d.textbbox((x, y), text, font=font)
        boxes.append((bb[0], bb[1], bb[2] + (5 if shadow else 0), bb[3] + (5 if shadow else 0)))
        return bb[3]

    # 1) Hook-Überschrift (max. 3 Zeilen)
    f = _fit_text(d, headline.upper(), config.FONT_DISPLAY, w - 2 * m, 150, 84)
    lines = _wrap(d, headline.upper(), f, w - 2 * m)[:3]
    y, text_bottom = SAFE_TOP, SAFE_TOP
    for ln in lines:
        text_bottom = centered(ln, f, y, config.WHITE, shadow=True)
        y += int(f.size * 0.92)
    bar_y = max(y, text_bottom) + 26                   # Strich immer unter der echten Text-Unterkante
    d.rectangle([(w - 160) // 2, bar_y, (w + 160) // 2, bar_y + 9], fill=config.TEAL)
    boxes.append(((w - 160) // 2, bar_y, (w + 160) // 2, bar_y + 9))
    # 2) Platz unter dem Cover vorab berechnen, dann Cover so groß wie möglich (max. 64 % Breite)
    f_album = _fit_text(d, (album or "").upper() or "X", config.FONT_DISPLAY, w - 2 * m, 76, 52)
    f_track = _font(config.FONT_BODY, 36)
    f_cta = _font(config.FONT_BODY, 44)
    f_cta2 = _font(config.FONT_BODY, 32)
    below = (GAP + (f_album.size if album else 0) + 18 + f_track.size + GAP + f_cta.size + 22 + f_cta2.size + 10)
    cover_top = bar_y + 9 + GAP + 10
    side = min(int(w * 0.64), SAFE_BOTTOM - below - cover_top)
    side = max(side, int(w * 0.42))
    cover = Image.open(cover_png).convert("RGB").resize((side, side), Image.LANCZOS)
    x = (w - side) // 2
    shadow_ = Image.new("RGBA", (side + 100, side + 100), (0, 0, 0, 0))
    ImageDraw.Draw(shadow_).rectangle([50, 50, side + 50, side + 50], fill=(0, 0, 0, 190))
    shadow_ = shadow_.filter(ImageFilter.GaussianBlur(35))
    bg.paste(shadow_, (x - 50, cover_top - 35), shadow_)
    bg.paste(cover, (x, cover_top))
    d = ImageDraw.Draw(bg)
    cover_box = (x, cover_top, x + side, cover_top + side)
    # 3) Albumname (identisch zu Video-/Albumtitel), Track, Hinweis auf den ganzen Mix
    y = cover_box[3] + GAP
    if album:
        y = centered(album.upper(), f_album, y, config.TEAL) + 18
    y = centered(f"{config.ARTIST.upper()}  ·  {track_title.upper()}", f_track, y, config.GREY) + GAP
    t1 = f"FULL {total_min} MIN ON THE CHANNEL" if total_min else "FULL MIX ON THE CHANNEL"
    y = centered(t1, f_cta, y, config.TEAL) + 22
    centered("link in description  ·  no vocals  ·  no interruptions", f_cta2, y, config.GREY)
    _check_no_overlap(boxes + [cover_box])
    out.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out, "PNG")
    Path(str(out) + ".layout.json").write_text(json.dumps({"cover": cover_box, "text": boxes}))
    return out


def _check_no_overlap(boxes: list[tuple[int, int, int, int]]) -> None:
    """Sicherheitsnetz: kein Element darf ein anderes berühren oder unter SAFE_BOTTOM rutschen."""
    for i, a in enumerate(boxes):
        if a[3] > SAFE_BOTTOM + 40:
            raise ValueError(f"Short-Layout: Element reicht bis y={a[3]} (> sicherer Bereich {SAFE_BOTTOM})")
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
    title = f"{title[:100 - len(' #Shorts')].rstrip()} #Shorts"
    desc = (f"{overlay}\n\n🎧 Full mix ({concept.get('total_min', 60)}+ min, no vocals, no interruptions): {full_url}\n"
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
