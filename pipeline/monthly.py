"""Monats-Mix: Mixe eines Themas aus Drive zusammenfügen, Monats-Thumbnail, Titel/Beschreibung/Kommentar/Community-Text."""
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from . import audio, config, images, metadata

FOLDER_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) [–-] (.+?) \((.+?), (\d+) BPM\)$")
TRACK_RE = re.compile(r"^\d+ - .*?Aix Walker - (.+)\.mp3$", re.I)
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]

GENRE_TEXT = {   # Stichwort im Genre-Namen → (Titelteil, Zweck, Tags, Playlist)
    "gym": ("Slow Gym Beats", "Dark Workout Music for Heavy Lifting", ["gym music", "workout music", "slow gym beats",
            "heavy lifting music", "dark workout"], "gym"),
    "spa": ("Dark Ambient Spa Music", "Deep Relaxing Music for Massage & Wellness", ["spa music", "dark ambient",
            "massage music", "relaxing music", "wellness music"], "chillout"),
    "sleep": ("Sleep Music", "Fall Asleep Fast", ["sleep music", "deep sleep", "relaxing music", "fall asleep fast",
              "insomnia music"], "chillout"),
    "drive": ("Night Drive Deep Bass", "Late Night Driving Music", ["night drive", "deep bass", "dark ambient",
              "driving music", "night music"], "chillout"),
}


def genre_info(genre: str) -> tuple[str, str, list[str], str]:
    g = genre.lower()
    for key, v in GENRE_TEXT.items():
        if key in g:
            return v
    return (genre, "Long Mix", [genre.lower(), "long mix", "ambient"], "chillout")


def parse_folder(name: str) -> dict | None:
    m = FOLDER_RE.match(name.strip())
    if not m:
        return None
    return {"date": m.group(1), "album": m.group(2), "genre": m.group(3), "bpm": int(m.group(4)), "name": name}


def track_title(filename: str) -> str:
    m = TRACK_RE.match(filename)
    return m.group(1).strip() if m else Path(filename).stem


def hours_label(total_min: int) -> str:
    return metadata.hours_wording(total_min)


# ---------- Audio ----------

def _xfade(inputs: list[Path], dst: Path, xf: float) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y"]
    for p in inputs:
        cmd += ["-i", str(p)]
    chain, prev = "", "[0:a]"
    for i in range(1, len(inputs)):
        out = f"[a{i}]" if i < len(inputs) - 1 else "[out]"
        chain += f"{prev}[{i}:a]acrossfade=d={xf}:c1=tri:c2=tri{out};"
        prev = out
    if len(inputs) == 1:
        cmd += ["-ar", "44100", "-ac", "2", "-c:a", "flac", str(dst)]
    else:
        cmd += ["-filter_complex", chain.rstrip(";"), "-map", "[out]", "-ar", "44100", "-ac", "2", "-c:a", "flac", str(dst)]
    subprocess.run(cmd, check=True, capture_output=True)


def join_tracks(tracks: list[Path], dst: Path, xf: float = 2.0, batch: int = 10) -> tuple[Path, list[float]]:
    """Alle Tracks mit Crossfade zu einer FLAC-Datei (in Batches, damit ffmpeg nicht 40 Eingänge gleichzeitig hält)."""
    work = dst.parent / "_batches"
    work.mkdir(parents=True, exist_ok=True)
    parts, part_starts = [], []   # je Batch: Datei, Startzeiten der Tracks darin
    for bi in range(0, len(tracks), batch):
        grp = tracks[bi:bi + batch]
        p = work / f"b{bi // batch:02d}.flac"
        _xfade(grp, p, xf)
        st, t = [], 0.0
        for g in grp:
            st.append(t)
            t += audio.probe_duration(g) - xf
        parts.append(p)
        part_starts.append(st)
    _xfade(parts, dst, xf)
    starts, off = [], 0.0
    for p, st in zip(parts, part_starts):
        starts += [off + s for s in st]
        off += audio.probe_duration(p) - xf
    for p in parts:
        p.unlink(missing_ok=True)
    return dst, starts


def build_still_video(frame: Path, audio_file: Path, out: Path, fps: int = 2) -> Path:
    """Standbild + Audio, niedrige Bildrate (3 h bleiben klein). AAC 192k, faststart."""
    subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-y", "-loop", "1", "-framerate", str(fps), "-i", str(frame),
                    "-i", str(audio_file), "-vf", "scale=1920:1080,format=yuv420p", "-c:v", "libx264", "-preset",
                    "veryfast", "-tune", "stillimage", "-crf", "28", "-g", str(fps * 10), "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", str(out)], check=True, capture_output=True)
    return out


# ---------- Thumbnail ----------

def make_monthly_thumbnail(covers: list[Image.Image], hours_text: str, genre_line: str, month_label: str,
                           out: Path, w: int = 1280, h: int = 720) -> Path:
    """Monats-Look (anders als die Wochen-Thumbnails): Mosaik aus den Covern des Monats in senkrechten Streifen,
    dicker Teal-Rahmen, Teal-Band „MONTHLY MIX · MONAT“, riesige Stundenzahl in der Mitte."""
    s = h / 720
    n = max(1, len(covers))
    img = Image.new("RGB", (w, h), config.BG)
    sw = w / n
    for i, c in enumerate(covers):
        c = c.convert("RGB")
        scale = max(sw / c.width, h / c.height)
        c = c.resize((int(c.width * scale) + 1, int(c.height * scale) + 1), Image.LANCZOS)
        x0, y0 = (c.width - int(sw)) // 2, (c.height - h) // 2
        strip = c.crop((x0, y0, x0 + int(sw) + 1, y0 + h))
        img.paste(strip, (int(i * sw), 0))
    # abdunkeln, in der Mitte stärker (Lesbarkeit)
    shade = Image.new("L", (w, h), 0)
    sd = ImageDraw.Draw(shade)
    for y in range(h):
        a = int(60 + 70 * (1 - abs(y - h * 0.5) / (h * 0.5)))
        sd.line([(0, y), (w, y)], fill=min(a, 140))
    img = Image.composite(Image.new("RGB", (w, h), (4, 9, 10)), img, shade)
    d = ImageDraw.Draw(img)
    for i in range(1, n):   # dünne Trennlinien zwischen den Streifen
        d.line([(int(i * sw), 0), (int(i * sw), h)], fill=config.TEAL_DIM, width=max(2, int(3 * s)))
    # Teal-Band oben
    bar_h = int(96 * s)
    d.rectangle([0, 0, w, bar_h], fill=config.TEAL)
    bf = images._fit_text(d, f"MONTHLY MIX  ·  {month_label.upper()}", config.FONT_DISPLAY, int(w * 0.9), int(80 * s), 30)
    bw = d.textlength(f"MONTHLY MIX  ·  {month_label.upper()}", font=bf)
    d.text(((w - bw) / 2, (bar_h - bf.size) / 2 - 6 * s), f"MONTHLY MIX  ·  {month_label.upper()}", font=bf, fill=config.BG)
    # Stundenzahl
    hf = images._fit_text(d, hours_text.upper(), config.FONT_DISPLAY, int(w * 0.86), int(330 * s), 100)
    tw = d.textlength(hours_text.upper(), font=hf)
    ty = bar_h + (h - bar_h - hf.size) / 2 - 40 * s
    d.text(((w - tw) / 2 + 7 * s, ty + 7 * s), hours_text.upper(), font=hf, fill=(0, 0, 0))
    d.text(((w - tw) / 2, ty), hours_text.upper(), font=hf, fill=config.WHITE)
    gf = images._fit_text(d, genre_line.upper(), config.FONT_BODY, int(w * 0.84), int(54 * s), 24)
    gw = d.textlength(genre_line.upper(), font=gf)
    gy = h - int(112 * s)
    d.rectangle([(w - gw) / 2 - 24 * s, gy - 12 * s, (w + gw) / 2 + 24 * s, gy + gf.size + 12 * s], fill=(4, 9, 10))
    d.text(((w - gw) / 2, gy), genre_line.upper(), font=gf, fill=config.TEAL)
    # Rahmen
    bw_ = max(8, int(14 * s))
    d.rectangle([0, 0, w - 1, h - 1], outline=config.TEAL, width=bw_)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=92)
    if out.stat().st_size > 2_000_000:
        img.save(out, "JPEG", quality=80)
    return out


# ---------- Texte ----------

def make_texts(genre: str, month_label: str, year: int, total_min: int, albums: list[dict], chapter_text: str,
               bpm_range: str) -> dict:
    head, purpose, tags, playlist = genre_info(genre)
    hrs = hours_label(total_min)
    title = f"{head} · {hrs} · {purpose} (Monthly Mix {month_label} {year})"
    if len(title) > 100:
        title = f"{head} · {hrs} · Monthly Mix {month_label} {year}"
    mixes = "\n".join(f"• {a['album']}" + (f" – https://youtu.be/{a['video_id']}" if a.get("video_id") else "")
                      for a in albums)
    desc = f"""🎧 {hrs} of {head.lower()} – the best of {month_label}, in one uninterrupted mix.

{len(albums)} weekly AIX WALKER mixes, blended with smooth crossfades. No vocals, no interruptions – {purpose.lower()}.

⏱️ CHAPTERS
{chapter_text}

📀 FROM THESE WEEKLY MIXES
{mixes}

🔊 {bpm_range} BPM · no vocals · mastered for headphones and speakers
🎵 All tracks produced by {config.ARTIST} (AI-assisted, original music)
▶️ Full playlist: https://www.youtube.com/playlist?list={config.PLAYLISTS[playlist]}
🔔 New mixes every Tuesday and Friday, a monthly mix on the 1st – subscribe and hit the bell!

👇 Which track was your favourite this month? Drop it in the comments.

#{head.replace(' ', '')} #MonthlyMix #{config.ARTIST.replace(' ', '')} #NoVocals #LongMix
"""
    tags = tags + ["monthly mix", "long mix", f"{hrs.lower()} mix", "aix walker", "no vocals", "ai music"]
    comment = f"🎧 Monthly Mix {month_label}: which track was your favourite? Drop the chapter timestamp below 👇"
    community = (f"Monatsmix ist online: {head} – {hrs} am Stück 🎧\nAlle Highlights aus {len(albums)} Wochen-Mixen, "
                 f"nahtlos gemischt.")
    return {"title": title, "description": desc[:5000], "tags": tags, "comment": comment, "community_de": community,
            "playlist": playlist}
