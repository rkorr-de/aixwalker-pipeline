"""Schnitt mit ffmpeg: 2 Clips → 15 s, Crossfade, Veo-Ton + Musikbett, Loudness, Thumbnail, Prüfbilder."""
import json
import subprocess
from pathlib import Path

from PIL import Image

from . import config


def _run(cmd: list[str]) -> None:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg fehlgeschlagen:\n{' '.join(cmd)}\n{res.stderr[-1500:]}")


def probe(path: Path) -> dict:
    res = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type,codec_name,width,height,r_frame_rate,duration:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def duration(path: Path) -> float:
    return float(probe(path)["format"]["duration"])


def has_audio(path: Path) -> bool:
    return any(s.get("codec_type") == "audio" for s in probe(path)["streams"])


def extract_frame(video: Path, t: float, out: Path, w: int = 1080) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video),
          "-frames:v", "1", "-vf", f"scale={w}:-2", str(out)])
    return out


def last_frame(video: Path, out: Path) -> Path:
    return extract_frame(video, max(0.0, duration(video) - 0.1), out)


def contact_sheet(video: Path, out: Path, n: int = 8) -> Path:
    """Prüfbild: n Frames nebeneinander (zum Sichten durch Claude: Artefakte, Text, falsche Figur)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    d = duration(video)
    frames = []
    for i in range(n):
        f = out.parent / f"_cs_{i}.jpg"
        extract_frame(video, d * (i + 0.5) / n, f, w=360)
        frames.append(Image.open(f))
    w, h = frames[0].size
    sheet = Image.new("RGB", (w * 4, h * ((n + 3) // 4)), (255, 255, 255))
    for i, fr in enumerate(frames):
        sheet.paste(fr, ((i % 4) * w, (i // 4) * h))
    sheet.save(out, "JPEG", quality=85)
    for i in range(n):
        (out.parent / f"_cs_{i}.jpg").unlink(missing_ok=True)
    return out


def assemble(clip1: Path, clip2: Path, music: Path | None, out: Path, total: float = config.SHORT_SEC) -> Path:
    """Verbindet zwei Clips (xfade), kürzt auf `total` s, mischt Musik leise unter den Veo-Ton, Loudness −14 LUFS."""
    out.parent.mkdir(parents=True, exist_ok=True)
    d1 = duration(clip1)
    xf = config.CROSSFADE_SEC
    off = max(0.5, d1 - xf)
    w, h, fps = config.WIDTH, config.HEIGHT, config.FPS
    a1, a2 = has_audio(clip1), has_audio(clip2)
    inputs = ["-i", str(clip1), "-i", str(clip2)]
    fc = [
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},format=yuv420p,setsar=1[v0]",
        f"[1:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},format=yuv420p,setsar=1[v1]",
        f"[v0][v1]xfade=transition=fade:duration={xf}:offset={off:.3f},trim=0:{total},setpts=PTS-STARTPTS,"
        f"fade=t=out:st={total - 0.25:.2f}:d=0.25[vout]",
    ]
    audio_parts = []
    if a1 and a2:
        fc.append(f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo[a0];"
                  f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo[a1];"
                  f"[a0][a1]acrossfade=d={xf}:c1=tri:c2=tri[sfx]")
        audio_parts.append("[sfx]")
    elif a1 or a2:
        src = "0:a" if a1 else "1:a"
        fc.append(f"[{src}]aformat=sample_rates=48000:channel_layouts=stereo[sfx]")
        audio_parts.append("[sfx]")
    if music and music.exists():
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        fc.append(f"[2:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={config.MUSIC_GAIN_DB}dB,"
                  f"afade=t=in:d=0.5[mus]")
        audio_parts.append("[mus]")
    if audio_parts:
        if len(audio_parts) == 2:
            fc.append(f"{''.join(audio_parts)}amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mix]")
            src = "[mix]"
        else:
            src = audio_parts[0]
        fc.append(f"{src}atrim=0:{total},asetpts=PTS-STARTPTS,"
                  f"loudnorm=I={config.TARGET_LUFS}:TP=-1.0:LRA=9,afade=t=out:st={total - 0.4:.2f}:d=0.4[aout]")
        maps = ["-map", "[vout]", "-map", "[aout]"]
    else:
        maps = ["-map", "[vout]"]
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs,
           "-filter_complex", ";".join(fc), *maps, "-t", f"{total}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(fps),
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out)]
    _run(cmd)
    return out


def assemble_single(clip: Path, cues: list[tuple[Path, float]], music: Path | None, out: Path,
                    total: float = config.SHORT_SEC) -> Path:
    """Ein durchgehender Clip (Kling): auf `total` s kürzen; Musik als Hauptspur, darüber die Geräusche aus der
    Bibliothek an ihren Sekunden (cues = [(datei, sekunde)]), −14 LUFS."""
    out.parent.mkdir(parents=True, exist_ok=True)
    w, h, fps = config.WIDTH, config.HEIGHT, config.FPS
    inputs = ["-i", str(clip)]
    fc = [f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},format=yuv420p,setsar=1,"
          f"trim=0:{total},setpts=PTS-STARTPTS,fade=t=out:st={total - 0.25:.2f}:d=0.25[vout]"]
    parts, idx = [], 1
    if has_audio(clip):
        fc.append("[0:a]aformat=sample_rates=48000:channel_layouts=stereo[a0]")
        parts.append("[a0]")
    for n, (f, t) in enumerate(cues):
        inputs += ["-i", str(f)]
        ms = int(max(0.0, t) * 1000)
        fc.append(f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={config.SFX_GAIN_DB}dB,"
                  f"adelay={ms}|{ms}[fx{n}]")
        parts.append(f"[fx{n}]")
        idx += 1
    if music and music.exists():
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        fc.append(f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={config.MUSIC_BED_GAIN_DB}dB,"
                  f"afade=t=in:d=0.3[mus]")
        parts.append("[mus]")
    if not parts:   # stille Tonspur, damit YouTube/QC eine Audiospur sehen
        inputs += ["-f", "lavfi", "-t", str(total), "-i", "anullsrc=r=48000:cl=stereo"]
        fc.append(f"[{idx}:a]anull[sil]")
        parts.append("[sil]")
    mix = parts[0] if len(parts) == 1 else "[mix]"
    if len(parts) > 1:
        fc.append(f"{''.join(parts)}amix=inputs={len(parts)}:duration=longest:dropout_transition=0:normalize=0[mix]")
    fc.append(f"{mix}atrim=0:{total},asetpts=PTS-STARTPTS,loudnorm=I={config.TARGET_LUFS}:TP=-1.0:LRA=9,"
              f"afade=t=out:st={total - 0.4:.2f}:d=0.4[aout]")
    _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(fc),
          "-map", "[vout]", "-map", "[aout]", "-t", f"{total}",
          "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(fps),
          "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out)])
    return out


def qc(video: Path, min_bytes: int = 500_000) -> dict:
    """Technische Prüfung: Dauer, Auflösung, Tonspur. Liefert dict mit ok/Gründen."""
    p = probe(video)
    d = float(p["format"]["duration"])
    v = next((s for s in p["streams"] if s["codec_type"] == "video"), {})
    reasons = []
    if not (14.0 <= d <= 15.5):
        reasons.append(f"Dauer {d:.2f} s statt ~15 s")
    if int(v.get("width", 0)) != config.WIDTH or int(v.get("height", 0)) != config.HEIGHT:
        reasons.append(f"Auflösung {v.get('width')}x{v.get('height')} statt {config.WIDTH}x{config.HEIGHT}")
    if not has_audio(video):
        reasons.append("keine Tonspur")
    if video.stat().st_size < min_bytes:
        reasons.append("Datei verdächtig klein")
    return {"ok": not reasons, "reasons": reasons, "duration": d}


def make_thumbnail(art: Image.Image, out: Path) -> Path:
    """Shorts-Thumbnail 1080×1920 (JPEG < 2 MB) – ohne Text, die Figur verkauft den Klick."""
    w, h = config.WIDTH, config.HEIGHT
    aw, ah = art.size
    scale = max(w / aw, h / ah)
    img = art.resize((int(aw * scale), int(ah * scale)), Image.LANCZOS)
    img = img.crop(((img.width - w) // 2, (img.height - h) // 2, (img.width - w) // 2 + w, (img.height - h) // 2 + h))
    out.parent.mkdir(parents=True, exist_ok=True)
    for q in (92, 85, 78):
        img.save(out, "JPEG", quality=q)
        if out.stat().st_size < 2_000_000:
            break
    return out
