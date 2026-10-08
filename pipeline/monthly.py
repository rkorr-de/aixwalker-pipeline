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

GENRE_TEXT = {   # Stichwort im Genre-Namen → (Titelteil, Zweck, Tags, Playlist); „mediterranean“ vor „spa“ (Reihenfolge zählt)
    "italian": ("Italian Chillout Music", "Amalfi Coast & Lake Como Dinner Lounge", ["italian chillout", "italian lounge music",
                "amalfi coast music", "italian dinner music", "lake como", "italian cafe music", "bossa lounge"], "italian"),
    "mediterranean": ("Mediterranean Spa Lounge", "Balearic Chillout for Relaxing Sunsets", ["balearic chillout",
                      "spa lounge", "ibiza chillout", "luxury spa music", "beach lounge", "chillout lounge", "sunset music"], "chillout"),
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

HERO_PROMPTS = {   # Genre-Stichwort → Motiv (immer eine Frau, werbefreundlich, Kanal-Look: dunkel, Teal-Licht)
    "italian": ("elegant, attractive woman in a fitted silk evening gown at a candlelit dinner table on a terrace above the "
                "Amalfi Coast or Lake Como at sunset, real professional editorial travel photograph (full-frame camera, "
                "natural skin texture, subtle film grain, not CGI), warm golden light"),
    "mediterranean": "elegant woman in a white dress on a luxury resort terrace at golden sunset over the Mediterranean, warm amber light with teal accents",
    "gym": "athletic woman in black sportswear gripping a barbell in a dark industrial gym, chalk dust, teal rim light",
    "spa": "calm woman in a spa robe by candles and hot stones, steam, dark moody spa, teal accent light",
    "sleep": "serene woman asleep in a soft bed by a starry window, moonlight, floor mist, teal accent glow",
    "drive": "woman at the wheel of a car at night, city lights bokeh, dark moody, teal accent light",
}


def hero_prompt(genre: str) -> str:
    g = genre.lower()
    base = next((v for k, v in HERO_PROMPTS.items() if k in g), "calm woman in a dark moody room, teal accent light")
    return (f"Cinematic photo, {base}. Woman on the RIGHT third of the frame, face clearly visible, left side dark and "
            "empty for text. Photorealistic, high contrast, no text, no logos, 16:9.")


def make_monthly_thumbnail(art: Image.Image, hours_text: str, genre_line: str, month_label: str,
                           out: Path, w: int = 1280, h: int = 720) -> Path:
    """Monats-Look: Frau rechts (wie bei den Wochen-Thumbnails), links riesige Stundenzahl, Teal-Band
    „MONTHLY MIX · MONAT“ oben und dicker Teal-Rahmen als Erkennungsmerkmal."""
    s = h / 720
    img = art.convert("RGB")
    scale = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1), Image.LANCZOS)
    x0, y0 = (img.width - w) // 2, (img.height - h) // 2
    img = img.crop((x0, y0, x0 + w, y0 + h))
    ov = Image.new("L", (w, h), 0)
    od = ImageDraw.Draw(ov)
    for x in range(int(w * 0.68)):
        od.line([(x, 0), (x, h)], fill=int(215 * (1 - x / (w * 0.68)) ** 1.1))
    img = Image.composite(Image.new("RGB", (w, h), (5, 10, 12)), img, ov)
    d = ImageDraw.Draw(img)
    bar_h = int(96 * s)
    d.rectangle([0, 0, w, bar_h], fill=config.TEAL)
    label = f"MONTHLY MIX  ·  {month_label.upper()}"
    bf = images._fit_text(d, label, config.FONT_DISPLAY, int(w * 0.9), int(80 * s), 30)
    bw = d.textlength(label, font=bf)
    d.text(((w - bw) / 2, (bar_h - bf.size) / 2 - 6 * s), label, font=bf, fill=config.BG)
    m = int(56 * s)
    ht = hours_text.upper()
    hf = images._fit_text(d, ht, config.FONT_DISPLAY, int(w * 0.58), int(300 * s), 100)
    ty = bar_h + (h - bar_h - hf.size) / 2 - 50 * s
    d.text((m + 7 * s, ty + 7 * s), ht, font=hf, fill=(0, 0, 0))
    d.text((m, ty), ht, font=hf, fill=config.WHITE)
    gy = ty + hf.size * 1.02
    d.rectangle([m, gy + 10 * s, m + 110 * s, gy + 18 * s], fill=config.TEAL)
    gf = images._fit_text(d, genre_line.upper(), config.FONT_BODY, int(w * 0.56), int(44 * s), 22)
    d.text((m + 130 * s, gy - 2 * s), genre_line.upper(), font=gf, fill=config.TEAL)
    d.rectangle([0, 0, w - 1, h - 1], outline=config.TEAL, width=max(8, int(14 * s)))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=92)
    if out.stat().st_size > 2_000_000:
        img.save(out, "JPEG", quality=80)
    return out


# ---------- Texte ----------

def make_texts(genre: str, month_label: str, year: int, total_min: int, albums: list[dict], chapter_text: str,
               bpm_range: str) -> dict:
    head, purpose, tags, playlist = genre_info(genre)
    playlist_id = config.PLAYLISTS.get(playlist, "")
    if not playlist_id:
        try:
            from . import youtube
            playlist_id = youtube.playlist_for(playlist)
        except Exception:  # noqa: BLE001 – ohne YouTube-Zugang (Dry-Run) Sammel-Playlist verlinken
            playlist_id = config.PLAYLISTS["chillout"]
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
▶️ Full playlist: https://www.youtube.com/playlist?list={playlist_id}
🔔 New mixes every Tuesday and Friday, a monthly mix on the 1st – subscribe and hit the bell!

👇 Which track was your favourite this month? Drop it in the comments.

#{head.replace(' ', '')} #MonthlyMix #{config.ARTIST.replace(' ', '')} #NoVocals #LongMix
"""
    tags = tags + ["monthly mix", "long mix", f"{hrs.lower()} mix", "aix walker", "no vocals", "ai music"]
    comment = f"🎧 Monthly Mix {month_label}: which track was your favourite? Drop the chapter timestamp below 👇"
    community = (f"Monthly Mix is live: {head} – {hrs} non-stop 🎧\nThe best of {month_label} from {len(albums)} weekly mixes, "
                 f"blended seamlessly. Listen here and tell us your favourite track!")
    return {"title": title, "description": desc[:5000], "tags": tags, "comment": comment, "community_de": community,
            "playlist": playlist}
