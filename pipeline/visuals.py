"""Bewegte Visuals für den Mix: Standbild je Track plus audio-reaktive Wellenform (nur ffmpeg, CPU, kostenlos).

Ersetzt `video.build_video` nicht, sondern ergänzt es: gleiche Argumente, anderes Aussehen.
Gedacht, damit die Mixe nicht wie „ein Standbild mit Musik" wirken (YouTube-Monetarisierung).
"""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from . import config
from .images import _font

TEAL_HEX = "0x2dd4bf"


def make_animated_frame(cover_png: Path, out: Path, w: int = 1920, h: int = 1080) -> Path:
    """Videobild pro Track für die animierte Variante: Cover höher, unten Platz für die Wellenform."""
    cover = Image.open(cover_png).convert("RGB")
    bg = cover.resize((w, w), Image.LANCZOS).crop((0, (w - h) // 2, w, (w - h) // 2 + h))
    bg = bg.filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", (w, h), (0, 0, 0)), 0.5)
    side = int(h * 0.64)
    c = cover.resize((side, side), Image.LANCZOS)
    x, y = (w - side) // 2, int(h * 0.06)
    shadow = Image.new("RGBA", (side + 80, side + 80), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([40, 40, side + 40, side + 40], fill=(0, 0, 0, 180))
    shadow = shadow.filter(ImageFilter.GaussianBlur(30))
    bg.paste(shadow, (x - 40, y - 30), shadow)
    bg.paste(c, (x, y))
    # Kanalname klein unten links, dezent über der Wellenform
    d = ImageDraw.Draw(bg, "RGBA")
    d.text((60, h - 56), f"{config.ARTIST.upper()}  ·  {config.CHANNEL_HANDLE.upper()}",
           font=_font(config.FONT_BODY, 26), fill=(255, 255, 255, 170))
    out.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out, "PNG")
    return out


def build_short_animated(frame_png: Path, mix_wav: Path, start: float, end: float, out: Path, fps: int = 30) -> Path:
    """Wie shorts.build_short (langsamer Zoom, Audio-Fades), plus audio-reaktive Wellenform im freien Bereich
    unter dem Text (1080x1920, y≈1580)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    dur = end - start
    frames = int(dur * fps)
    graph = (
        f"[0:v]scale=1296:2304,zoompan=z='min(1.0+0.00025*on,1.25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s=1080x1920:fps={fps},format=rgba[bg];"
        f"[1:a]asplit=2[a1][avis];"
        f"[a1]afade=t=in:d=0.8,afade=t=out:st={dur - 1.5:.2f}:d=1.5[aout];"
        f"[avis]showwaves=s=960x140:mode=cline:rate={fps}:colors={TEAL_HEX}@0.9:scale=sqrt:draw=full,format=rgba[wv];"
        f"[bg][wv]overlay=60:1580:format=auto,format=yuv420p[v]"
    )
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y",
           "-loop", "1", "-i", str(frame_png),
           "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", str(mix_wav),
           "-filter_complex", graph, "-map", "[v]", "-map", "[aout]",
           "-t", f"{dur:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def build_video_animated(frames: list[Path], starts: list[float], audio_wav: Path, total_sec: float, out: Path,
                         fps: int = 15, crf: int = 26) -> Path:
    """Wie video.build_video, aber mit audio-reaktiver Wellenform (showwaves) unter dem Cover.

    frames[i] wird ab starts[i] gezeigt. 1920x1080, H.264, AAC 192k, faststart.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    concat = out.parent / "frames_concat.txt"
    lines = []
    for i, f in enumerate(frames):
        end = starts[i + 1] if i + 1 < len(starts) else total_sec
        lines.append(f"file '{f.resolve()}'\nduration {max(0.5, end - starts[i]):.3f}")
    lines.append(f"file '{frames[-1].resolve()}'")
    concat.write_text("\n".join(lines))
    graph = (
        f"[0:v]scale=1920:1080,fps={fps},format=rgba[bg];"
        f"[1:a]asplit=2[aout][avis];"
        f"[avis]showwaves=s=1800x170:mode=cline:rate={fps}:colors={TEAL_HEX}@0.9:scale=sqrt:draw=full,format=rgba[wv];"
        f"[bg][wv]overlay=60:H-h-80:format=auto,format=yuv420p[v]"
    )
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y",
           "-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(audio_wav),
           "-filter_complex", graph, "-map", "[v]", "-map", "[aout]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-g", str(fps * 10),
           "-c:a", "aac", "-b:a", "192k", "-t", f"{total_sec:.3f}", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out
