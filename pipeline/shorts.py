"""YouTube Shorts aus dem fertigen Mix: beste Passagen finden, 9:16-Video rendern, Metadaten.

Auswahl der Passagen (datenbasiert, kein Raten):
- Energieverlauf (RMS) und spektrale Helligkeit des Mixes in 1-s-Fenstern
- Kandidat = Fenster von `clip_sec` Sekunden mit höchstem "Hook-Score":
  Energie-Anstieg innerhalb des Fensters (Build-up → Drop) + absolute Energie + Helligkeit
- Zwei Clips mit großem Abstand (verschiedene Tracks), nie in den ersten/letzten 20 s
"""
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import config, metadata
from .images import _fit_text, _font, _wrap


def find_passages(mix_wav: Path, starts: list[float], total_sec: float, clip_sec: int = 45,
                  count: int = 2, min_gap_sec: float = 600) -> list[dict]:
    """Liefert `count` Passagen [{start, end, track_index, score}] nach Hook-Score."""
    import librosa
    y, sr = librosa.load(str(mix_wav), sr=11025, mono=True)
    hop = sr  # 1-s-Auflösung
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0]
    cent = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop)[0]
    rms = rms / (rms.max() + 1e-9)
    cent = cent / (cent.max() + 1e-9)
    n = len(rms)
    min_gap_sec = min(min_gap_sec, total_sec / 3)
    scores = np.full(n, -1.0)
    for t in range(20, max(21, n - clip_sec - 20)):
        win = rms[t:t + clip_sec]
        first, last = win[: clip_sec // 3].mean(), win[-clip_sec // 3:].mean()
        rise = max(0.0, last - first)                  # Build-up → Drop
        scores[t] = 0.5 * win.mean() + 0.35 * rise + 0.15 * cent[t:t + clip_sec].mean()
    chosen: list[dict] = []
    order = np.argsort(-scores)
    for t in order:
        if scores[t] < 0:
            break
        t = int(t)
        if any(abs(t - c["start"]) < min_gap_sec for c in chosen):
            continue
        # Clip-Start auf Track-Grenze beziehen (für Overlay/Kapitel)
        idx = max(i for i, s in enumerate(starts) if s <= t) if starts else 0
        if any(c["track_index"] == idx for c in chosen):
            continue
        chosen.append({"start": t, "end": min(t + clip_sec, int(total_sec)), "track_index": idx,
                       "score": float(scores[t])})
        if len(chosen) == count:
            break
    # Fallback, falls Mix sehr kurz: gleichmäßig verteilen
    while len(chosen) < count and total_sec > clip_sec * 2:
        t = int(total_sec * (len(chosen) + 1) / (count + 1))
        idx = max(i for i, s in enumerate(starts) if s <= t) if starts else 0
        chosen.append({"start": t, "end": t + clip_sec, "track_index": idx, "score": 0.0})
    return sorted(chosen, key=lambda c: c["start"])


def make_short_frame(art: Image.Image, cover_png: Path, headline: str, track_title: str, out: Path,
                     w: int = 1080, h: int = 1920) -> Path:
    """9:16-Bild: Motiv als unscharfer Hintergrund, Cover mittig, großer Hook-Text oben, CTA unten."""
    aw, ah = art.size
    scale = max(w / aw, h / ah)
    bg = art.resize((int(aw * scale), int(ah * scale)), Image.LANCZOS)
    bg = bg.crop(((bg.width - w) // 2, (bg.height - h) // 2, (bg.width - w) // 2 + w, (bg.height - h) // 2 + h))
    bg = bg.filter(ImageFilter.GaussianBlur(18))
    bg = Image.blend(bg, Image.new("RGB", (w, h), (0, 0, 0)), 0.5)
    # Vignette oben/unten für Textkontrast
    ov = Image.new("L", (w, h), 0)
    od = ImageDraw.Draw(ov)
    for yy in range(h):
        a = 0
        if yy < h * 0.3:
            a = int(190 * (1 - yy / (h * 0.3)) ** 1.5)
        elif yy > h * 0.72:
            a = int(210 * ((yy - h * 0.72) / (h * 0.28)) ** 1.3)
        od.line([(0, yy), (w, yy)], fill=a)
    bg = Image.composite(Image.new("RGB", (w, h), (3, 8, 10)), bg, ov)
    cover = Image.open(cover_png).convert("RGB")
    side = int(w * 0.72)
    c = cover.resize((side, side), Image.LANCZOS)
    shadow = Image.new("RGBA", (side + 100, side + 100), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([50, 50, side + 50, side + 50], fill=(0, 0, 0, 200))
    shadow = shadow.filter(ImageFilter.GaussianBlur(35))
    x, y = (w - side) // 2, int(h * 0.26)
    bg.paste(shadow, (x - 50, y - 35), shadow)
    bg.paste(c, (x, y))
    d = ImageDraw.Draw(bg)
    m = 70
    f = _fit_text(d, headline.upper(), config.FONT_DISPLAY, w - 2 * m, 170, 90)
    lines = _wrap(d, headline.upper(), f, w - 2 * m)
    lh = int(f.size * 0.92)
    ty = int(h * 0.09)
    for ln in lines[:3]:
        tw = d.textlength(ln, font=f)
        d.text(((w - tw) / 2 + 6, ty + 6), ln, font=f, fill=(0, 0, 0))
        d.text(((w - tw) / 2, ty), ln, font=f, fill=config.WHITE)
        ty += lh
    d.rectangle([(w - 160) // 2, ty + 18, (w + 160) // 2, ty + 28], fill=config.TEAL)
    small = _font(config.FONT_BODY, 40)
    sub = f"{config.ARTIST.upper()}  ·  {track_title.upper()}"
    tw = d.textlength(sub, font=small)
    d.text(((w - tw) / 2, y + side + 44), sub, font=small, fill=config.GREY)
    cta = _font(config.FONT_BODY, 46)
    t1 = "FULL 60+ MIN ON THE CHANNEL"
    tw = d.textlength(t1, font=cta)
    d.text(((w - tw) / 2, int(h * 0.76)), t1, font=cta, fill=config.TEAL)
    t2 = "link in description  ·  no vocals  ·  no ads mid-mix"
    small2 = _font(config.FONT_BODY, 34)
    tw = d.textlength(t2, font=small2)
    d.text(((w - tw) / 2, int(h * 0.76) + 70), t2, font=small2, fill=config.GREY)
    out.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out, "PNG")
    return out


def build_short(frame_png: Path, mix_wav: Path, start: float, end: float, out: Path, fps: int = 30) -> Path:
    """Rendert einen Short (1080x1920): langsamer Zoom auf das Standbild, Audioausschnitt mit Fades."""
    out.parent.mkdir(parents=True, exist_ok=True)
    dur = end - start
    frames = int(dur * fps)
    vf = (f"scale=1296:2304,zoompan=z='min(1.0+0.00025*on,1.25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
          f":d={frames}:s=1080x1920:fps={fps},format=yuv420p")
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y",
           "-loop", "1", "-i", str(frame_png),
           "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", str(mix_wav),
           "-vf", vf, "-af", f"afade=t=in:d=0.8,afade=t=out:st={dur - 1.5:.2f}:d=1.5",
           "-t", f"{dur:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def short_metadata(concept: dict, idx: int, passage: dict, track_title: str, overlay: str,
                   full_url: str) -> tuple[str, str, list[str]]:
    """Titel (<100), Beschreibung, Tags für einen Short. #Shorts im Titel sorgt für Shelf-Einordnung."""
    base = concept.get("short_titles") or []
    title = base[idx] if idx < len(base) else f"{overlay} – {concept['album']} ({concept['bpm']} BPM) #Shorts"
    if "#Shorts" not in title:
        title = f"{title} #Shorts"
    desc = (f"{overlay}\n\n🎧 Full mix ({concept.get('total_min', 60)}+ min, no vocals, no interruptions): {full_url}\n"
            f"Track: {track_title} · {concept['genre']} · {concept['bpm']} BPM\n"
            f"From the mix „{concept['album']}“ by {config.ARTIST} (AI-assisted, original music)\n\n"
            f"{' '.join(concept['hashtags'][:4])} #Shorts")
    tags = ["shorts", "music shorts", *concept["tags"][:12]]
    return title[:100], desc, tags


def write_shorts_section(shorts: list[dict]) -> str:
    lines = []
    for i, s in enumerate(shorts, 1):
        lines.append(f"{i}. {metadata.fmt_ts(s['start'])}–{metadata.fmt_ts(s['end'])}  „{s['overlay']}“  "
                     f"Track: {s['track_title']}  Score {s['score']:.2f}  → {s.get('url', '(nicht hochgeladen)')}")
    return "\n".join(lines)
