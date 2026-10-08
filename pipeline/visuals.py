"""Bewegte Visuals für Mix und Shorts: sanft „atmendes" Licht hinter dem Cover (nur ffmpeg + numpy, CPU, kostenlos).

Warum kein Pegel-/Wellenform-Balken mehr (Rolf, 07.10.2026): Die Wellenform war zu unruhig und klobig und hat bei den
Shorts (mit Zoom) den unteren Text verdeckt. Stattdessen:
- ein weicher Gold-Schein um das Cover, dessen Helligkeit langsam der Lautstärke folgt (geglättet über 1–2 s,
  Spannweite gering) – Bewegung ja, Unruhe nein; passt zu Spa/Sleep/Lounge
- das Cover selbst und alle Textflächen bleiben unberührt (Schein ist dort ausgespart, weich ausgeblendet)
- kein Zoom im Short: Text steht ruhig, nichts schiebt sich übereinander

Technik: Lautstärke-Hüllkurve je Videobild in numpy → winziges Graustufen-Video (16×9 px) → ffmpeg skaliert es und
multipliziert es mit einer Glow-Maske (nur Bereich um das Cover) → Gold-Fläche mit dieser Deckkraft über das Standbild.
"""
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import config
from .images import _font

# Helligkeit des Scheins: zwischen GLOW_MIN (leise) und 1.0 (laut) – bewusst schmale Spanne = dezent
GLOW_MIN = 0.45
ATTACK_SEC = 0.8     # wie schnell der Schein heller wird
RELEASE_SEC = 2.2    # wie langsam er wieder abklingt


# ---------------------------------------------------------------- Hüllkurve

def envelope(audio: Path, fps: float, start: float = 0.0, dur: float | None = None, sr: int = 4000) -> np.ndarray:
    """Geglättete Lautstärke 0..1 je Videobild (speichersparend über ffmpeg, auch für 3-Stunden-Mixe)."""
    cmd = ["ffmpeg", "-v", "error"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    if dur:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-i", str(audio), "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    y = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    hop = sr / fps
    n = max(1, int(len(y) / hop))
    idx = (np.arange(n + 1) * hop).astype(int)
    sq = np.add.reduceat(y[: idx[-1]] ** 2, idx[:-1]) if idx[-1] > 0 else np.zeros(n)
    cnt = np.maximum(np.diff(idx), 1)
    db = 10 * np.log10(sq / cnt + 1e-10)
    lo, hi = np.percentile(db, 10), np.percentile(db, 97)
    x = np.clip((db - lo) / max(hi - lo, 1e-6), 0, 1)
    # asymmetrisch glätten: langsam heller, noch langsamer dunkler → „Atmen" statt Zucken
    a_up, a_dn = 1 - np.exp(-1 / (ATTACK_SEC * fps)), 1 - np.exp(-1 / (RELEASE_SEC * fps))
    out = np.empty_like(x)
    v = float(x[: int(fps * 2)].mean()) if len(x) else 0.0
    for i, xi in enumerate(x):
        v += (a_up if xi > v else a_dn) * (xi - v)
        out[i] = v
    return GLOW_MIN + (1 - GLOW_MIN) * out


def _write_env_video(env: np.ndarray, path: Path) -> Path:
    """Hüllkurve als Roh-Graustufenvideo 16×9 (ein Wert je Bild)."""
    vals = np.clip(np.round(env * 255), 0, 255).astype(np.uint8)
    path.write_bytes(np.repeat(vals, 16 * 9).tobytes())
    return path


# ---------------------------------------------------------------- Glow-Maske

def make_glow(size: tuple[int, int], cover: tuple[int, int, int, int], out: Path,
              clear: list[tuple[int, int, int, int]] | None = None, spread: int | None = None,
              strength: float = 0.55) -> tuple[Path, tuple[int, int]]:
    """Deckkraft-Maske (Graustufen) des weichen Gold-Scheins um das Cover (x0, y0, x1, y1), nur für den Bereich um das
    Cover zugeschnitten. Das Cover selbst und `clear`-Flächen (Text) bleiben frei, mit weichem Übergang.
    Liefert (Pfad, (x, y)) – die Position der Maske im Bild."""
    w, h = size
    x0, y0, x1, y1 = cover
    spread = spread or int(min(w, h) * 0.05)
    g = Image.new("L", (w, h), 0)
    ImageDraw.Draw(g).rectangle([x0 - spread // 3, y0 - spread // 3, x1 + spread // 3, y1 + spread // 3], fill=255)
    g = g.filter(ImageFilter.GaussianBlur(spread))
    keep = Image.new("L", (w, h), 255)
    kd = ImageDraw.Draw(keep)
    for bx in clear or []:
        kd.rectangle([bx[0] - 12, bx[1] - 12, bx[2] + 12, bx[3] + 12], fill=0)
    keep = keep.filter(ImageFilter.GaussianBlur(10))
    keep.paste(0, (x0, y0, x1, y1))                       # Cover exakt unberührt
    a = np.asarray(g, dtype=np.float32) / 255 * (np.asarray(keep, dtype=np.float32) / 255) * strength
    pad = spread * 3
    cx0, cy0 = max(0, x0 - pad) // 2 * 2, max(0, y0 - pad) // 2 * 2   # gerade Werte (yuv420)
    cx1, cy1 = min(w, x1 + pad) // 2 * 2, min(h, y1 + pad) // 2 * 2
    m = Image.fromarray((a[cy0:cy1, cx0:cx1] * 255).clip(0, 255).astype(np.uint8), "L")
    out.parent.mkdir(parents=True, exist_ok=True)
    m.save(out, "PNG")
    return out, (cx0, cy0)


def _hold(fps: float) -> str:
    """Standbild einmal dekodieren und im Speicher wiederholen (statt -loop 1, das jedes Bild neu lädt – 2–3× langsamer)."""
    return f"loop=loop=-1:size=1:start=0,setpts=N/{fps}/TB"


def _glow_graph(w: int, h: int, fps: float, mask: Path, pos: tuple[int, int], still_bg: bool = False) -> str:
    """Hintergrund [0:v] + Gold-Fläche, deren Deckkraft = Maske [2:v] × Hüllkurve [3:v]."""
    mw, mh = Image.open(mask).size
    hexcol = "0x%02x%02x%02x" % config.GLOW
    bg = f"[0:v]{_hold(fps)},scale={w}:{h},format=yuv420p[bg];" if still_bg else \
        f"[0:v]scale={w}:{h},fps={fps},format=yuv420p[bg];"
    return (f"[3:v]scale={mw}:{mh}:flags=bilinear,format=gray[env];"
            f"[2:v]{_hold(fps)},format=gray[m];[m][env]blend=all_mode=multiply:shortest=1[alpha];"
            f"color=c={hexcol}:s={mw}x{mh}:r={fps},format=yuva420p[col];"
            f"[col][alpha]alphamerge[glow];" + bg +
            f"[bg][glow]overlay={pos[0]}:{pos[1]}:format=yuv420:shortest=1,format=yuv420p[v]")


# ---------------------------------------------------------------- Fortschrittsstrich (Rolf 08.10.2026)
# Hauchdünner Verlaufsstrich ganz unten, der pro Song von links nach rechts mitläuft und beim nächsten Song neu beginnt.
# Farben je Song aus dessen Cover gemessen; darunter eine kaum sichtbare Spur. Ganz unten am Bildrand.
BAR_H = 3            # Strichstärke in px bei 1080p
BAR_BOTTOM = 4       # Abstand zur Unterkante in px


def _cover_colors(frame_png: Path, w: int = 1920, h: int = 1080) -> tuple[tuple, tuple]:
    """Zwei harmonische Farben aus dem Cover-Bereich des Videobilds: gedeckter Grundton + helle, warme Akzentfarbe."""
    x0, y0, x1, y1 = mix_cover_rect(w, h)
    im = Image.open(frame_png).convert("RGB").crop((x0, y0, x1, y1)).resize((64, 64))
    arr = np.asarray(im, dtype=np.float32).reshape(-1, 3)
    lum = arr @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    sat = arr.max(1) - arr.min(1)
    base = arr[lum < np.percentile(lum, 45)].mean(0)                       # gedeckter Grundton
    bright = arr[(lum > np.percentile(lum, 70)) & (sat >= np.percentile(sat, 40))]
    acc = (bright.mean(0) if len(bright) else arr[lum > np.percentile(lum, 80)].mean(0))
    acc = np.clip(acc * 1.15 + 18, 0, 255)                                  # Akzent etwas heller → leuchtet dezent
    return tuple(int(v) for v in base), tuple(int(v) for v in acc)


def _bar_images(frame_png: Path, outdir: Path, idx: int, w: int = 1920) -> tuple[Path, Path]:
    """Spur (statisch, kaum sichtbar) + Verlaufsstrich (gleitet) als RGBA-Streifen in voller Bildbreite."""
    base, acc = _cover_colors(frame_png)
    t = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]
    grad = (np.array(base, np.float32) * (1 - t) + np.array(acc, np.float32) * t)            # links Grundton → rechts Akzent
    alpha = (0.35 + 0.65 * t ** 0.7) * 255                                                  # nach vorne kräftiger
    bar = np.concatenate([np.repeat(grad, BAR_H, 0), np.repeat(alpha, BAR_H, 0)], 2).clip(0, 255).astype(np.uint8)
    rail = np.zeros((BAR_H, w, 4), np.uint8)
    rail[..., :3] = np.array(acc, np.uint8)
    rail[..., 3] = 46                                                                        # ca. 18 % Deckkraft
    outdir.mkdir(parents=True, exist_ok=True)
    pb, pr = outdir / f"bar{idx:03d}.png", outdir / f"rail{idx:03d}.png"
    Image.fromarray(bar, "RGBA").save(pb)
    Image.fromarray(rail, "RGBA").save(pr)
    return pb, pr


def _progress_expr(starts: list[float], total_sec: float) -> str:
    """ffmpeg-Ausdruck 0..1 = Fortschritt im aktuellen Song (stückweise über alle Songs)."""
    parts = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else total_sec
        d = max(0.5, e - s)
        parts.append(f"between(t,{s:.3f},{e:.3f})*(t-{s:.3f})/{d:.3f}")
    return "min(1,(" + "+".join(parts) + "))"


def _concat_list(paths: list[Path], starts: list[float], total_sec: float, out: Path) -> Path:
    lines = []
    for i, f in enumerate(paths):
        end = starts[i + 1] if i + 1 < len(starts) else total_sec
        lines.append(f"file '{f.resolve()}'\nduration {max(0.5, end - starts[i]):.3f}")
    lines.append(f"file '{paths[-1].resolve()}'")
    out.write_text("\n".join(lines))
    return out


# ---------------------------------------------------------------- Mix

def mix_cover_rect(w: int = 1920, h: int = 1080) -> tuple[int, int, int, int]:
    side = int(h * 0.70)
    x, y = (w - side) // 2, (h - side) // 2 - int(h * 0.02)
    return x, y, x + side, y + side


def make_animated_frame(cover_png: Path, out: Path, w: int = 1920, h: int = 1080) -> Path:
    """Videobild pro Track: Cover mittig auf unscharfem, abgedunkeltem Hintergrund (ohne Kanal-Schriftzug)."""
    cover = Image.open(cover_png).convert("RGB")
    bg = cover.resize((w, w), Image.LANCZOS).crop((0, (w - h) // 2, w, (w - h) // 2 + h))
    bg = bg.filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", (w, h), (0, 0, 0)), 0.38)
    x0, y0, x1, y1 = mix_cover_rect(w, h)
    side = x1 - x0
    c = cover.resize((side, side), Image.LANCZOS)
    shadow = Image.new("RGBA", (side + 80, side + 80), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([40, 40, side + 40, side + 40], fill=(0, 0, 0, 170))
    shadow = shadow.filter(ImageFilter.GaussianBlur(30))
    bg.paste(shadow, (x0 - 40, y0 - 28), shadow)
    bg.paste(c, (x0, y0))
    # statt Schriftzug: rundes Kanal-Logo unten links (Rolf 08.10.2026), leicht transparent gegen Einbrennen,
    # Abstand nach unten so, dass der Fortschrittsstrich frei bleibt
    if config.LOGO_PNG.exists():
        side_l = int(h * 0.06)          # ca. 65 px bei 1080p (Rolf 08.10.: kleiner)
        logo = Image.open(config.LOGO_PNG).convert("RGBA").resize((side_l, side_l), Image.LANCZOS)
        a = logo.getchannel("A").point(lambda v: int(v * 0.7))   # 30 % transparent
        logo.putalpha(a)
        margin = int(h * 0.03)
        bg.paste(logo, (margin, h - margin - side_l), logo)
    out.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out, "PNG")
    return out


def build_video_animated(frames: list[Path], starts: list[float], audio_wav: Path, total_sec: float, out: Path,
                         fps: int = 15, crf: int = 26) -> Path:
    """Mix-Video 1920×1080: Standbild je Track + atmendes Licht. Gleiche Argumente wie video.build_video."""
    out.parent.mkdir(parents=True, exist_ok=True)
    w, h = 1920, 1080
    concat = out.parent / "frames_concat.txt"
    lines = []
    for i, f in enumerate(frames):
        end = starts[i + 1] if i + 1 < len(starts) else total_sec
        lines.append(f"file '{f.resolve()}'\nduration {max(0.5, end - starts[i]):.3f}")
    lines.append(f"file '{frames[-1].resolve()}'")
    concat.write_text("\n".join(lines))
    glow, pos = make_glow((w, h), mix_cover_rect(w, h), out.parent / "glow.png")
    env = _write_env_video(envelope(audio_wav, fps), out.parent / "glow_env.gray")
    # Fortschrittsstrich je Song (Farben aus dem jeweiligen Cover; gleiche Bilder → gleiche Streifen wiederverwenden)
    bdir = out.parent / "progress"
    cache: dict[str, tuple[Path, Path]] = {}
    bars, rails = [], []
    for i, f in enumerate(frames):
        key = str(Path(f).resolve())
        if key not in cache:
            cache[key] = _bar_images(Path(f), bdir, len(cache), w)
        bars.append(cache[key][0])
        rails.append(cache[key][1])
    bar_list = _concat_list(bars, starts, total_sec, out.parent / "bars_concat.txt")
    rail_list = _concat_list(rails, starts, total_sec, out.parent / "rails_concat.txt")
    y = h - BAR_BOTTOM - BAR_H
    graph = (_glow_graph(w, h, fps, glow, pos).replace("format=yuv420p[v]", "format=yuv420p[g]") +
             f";[4:v]fps={fps},format=rgba[rl];[5:v]fps={fps},format=rgba[br];"
             f"[g][rl]overlay=0:{y}:format=auto:shortest=1[g2];"
             f"[g2][br]overlay=x='-{w}+{w}*({_progress_expr(starts, total_sec)})':y={y}:format=auto:eval=frame:shortest=1,"
             f"format=yuv420p[v]")
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y",
           "-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(audio_wav),
           "-i", str(glow),
           "-f", "rawvideo", "-pix_fmt", "gray", "-s", "16x9", "-r", str(fps), "-i", str(env),
           "-f", "concat", "-safe", "0", "-i", str(rail_list),
           "-f", "concat", "-safe", "0", "-i", str(bar_list),
           "-filter_complex", graph, "-map", "[v]", "-map", "1:a",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-g", str(fps * 10),
           "-c:a", "aac", "-b:a", "192k", "-t", f"{total_sec:.3f}", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    for tmp in (env, glow):
        tmp.unlink(missing_ok=True)
    return out


# ---------------------------------------------------------------- Shorts

def build_short_animated(frame_png: Path, mix_wav: Path, start: float, end: float, out: Path, fps: int = 30) -> Path:
    """Short 1080×1920 ohne Zoom: ruhiges Bild, atmendes Licht um das Cover, Textflächen ausgespart.
    Das Layout (Cover- und Textflächen) liefert shorts.make_short_frame als <frame>.layout.json."""
    out.parent.mkdir(parents=True, exist_ok=True)
    w, h = 1080, 1920
    dur = end - start
    layout = json.loads(Path(str(frame_png) + ".layout.json").read_text())
    glow, pos = make_glow((w, h), tuple(layout["cover"]), out.parent / f"{out.stem}_glow.png",
                          clear=[tuple(b) for b in layout["text"]], spread=48, strength=0.6)
    env = _write_env_video(envelope(mix_wav, fps, start, dur), out.parent / f"{out.stem}_env.gray")
    graph = (_glow_graph(w, h, fps, glow, pos, still_bg=True) + ";"
             f"[1:a]afade=t=in:d=0.15,afade=t=out:st={dur - 1.5:.2f}:d=1.5[aout]")
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y",
           "-i", str(frame_png),
           "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", str(mix_wav),
           "-i", str(glow),
           "-f", "rawvideo", "-pix_fmt", "gray", "-s", "16x9", "-r", str(fps), "-i", str(env),
           "-filter_complex", graph, "-map", "[v]", "-map", "[aout]",
           "-t", f"{dur:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-r", str(fps),
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    for tmp in (env, glow):
        tmp.unlink(missing_ok=True)
    return out
