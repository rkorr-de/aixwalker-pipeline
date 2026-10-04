"""Zusammenschnitte aus den täglichen Shorts (16:9-Langform für die Suche nach „compilation for toddlers“).

Drei Modi (alle vollautomatisch, keine KI-Videokosten – nur Schnitt + ein Textaufruf für die Metadaten):
  daily   – Intro → heutiger Short → bis zu 9 ältere Shorts in zufälliger Auswahl/Reihenfolge → Abspann (≈ 3 min)
  weekly  – Intro → die 7 Shorts der Woche → 7 beliebteste ältere (Aufrufe) → Abspann (sonntags)
  monthly – Intro → alle Shorts des Monats, neueste zuerst → Abspann (am 1. für den Vormonat)
Jeder Zusammenschnitt ist dadurch wirklich anders (YouTube wertet sonst „wiederholten Inhalt“ ab).

Quellen: Google Drive „Giggle Meadow Shorts/<Datum – Titel>/short.mp4“ und „…/intro.mp4“ (16:9, von Rolf).
Verlauf (_verlauf.json) liefert Titel, Figur, Video-ID und Aufrufe je Short.
"""
import json
import random
import re
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from pipeline import drive as base

from . import config, drive as kdrive, history, render

W, H, FPS = 1920, 1080, 30
FONT = config.ROOT / "assets" / "kids" / "Fredoka.ttf"
LOGO = config.ROOT / "assets" / "kids" / "logo_512.png"
CACHE = config.BUILD / "_cache"
INTRO_NAMES = ["intro.mp4", "intro_16x9.mp4"]
TITLE_CARD_SEC = 1.4
OUTRO_SEC = 5.0
DAILY_OLD_COUNT = 9
WEEKLY_TOP_COUNT = 7
PASTELS = [(255, 223, 128), (186, 230, 255), (255, 190, 214), (214, 190, 255), (190, 240, 200), (255, 210, 170)]


# ---------------------------------------------------------------- Drive: Intro + Shorts einsammeln ----------------
def _font(size: int, weight: str = "Bold") -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONT), size)
    try:
        f.set_variation_by_name(weight)
    except Exception:  # noqa: BLE001
        pass
    return f


def _download(svc, file_id: str, out: Path) -> Path:
    from googleapiclient.http import MediaIoBaseDownload
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as fh:
        req = svc.files().get_media(fileId=file_id)
        dl = MediaIoBaseDownload(fh, req, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            _, done = dl.next_chunk()
    return out


def fetch_intro(vertical: bool = False) -> Path | None:
    """Holt intro.mp4 (bzw. intro_vertical.mp4) aus dem Drive-Wurzelordner; None, wenn es (noch) nicht da ist."""
    if not kdrive.available():
        return None
    names = ["intro_vertical.mp4", "intro_9x16.mp4"] if vertical else INTRO_NAMES
    svc = base.service()
    root = base.ensure_folder(svc, kdrive.ROOT_FOLDER)
    for name in names:
        q = f"name = '{name}' and '{root}' in parents and trashed = false"
        files = svc.files().list(q=q, fields="files(id,name,modifiedTime,size)", pageSize=1).execute().get("files", [])
        if files:
            f = files[0]
            local = CACHE / f"{name}.{f['modifiedTime'].replace(':', '')}.mp4"
            if not local.exists():
                _download(svc, f["id"], local)
            return local
    return None


def fetch_shorts(today_out: Path | None = None, today: str | None = None) -> list[dict]:
    """Alle veröffentlichten Shorts: [{date, title, name, species, video_id, views, path}], ältester zuerst.

    Der heutige Short wird aus `today_out/short.mp4` genommen (liegt lokal vor), alle anderen aus Drive (gecacht).
    """
    entries = [e for e in history.load() if e.get("status") == "published" and e.get("video_id")]
    try:
        entries = history.refresh_views(entries)
    except Exception as e:  # noqa: BLE001
        print(f"[compilation] Aufrufe nicht aktualisiert: {e}")
    by_date: dict[str, dict] = {}
    for e in entries:
        by_date[e["date"]] = e            # bei mehreren Einträgen je Tag gilt der letzte (veröffentlichte)
    svc = base.service() if kdrive.available() else None
    folders: dict[str, str] = {}
    if svc:
        root = base.ensure_folder(svc, kdrive.ROOT_FOLDER)
        token = None
        while True:
            r = svc.files().list(q=f"'{root}' in parents and mimeType = '{base.FOLDER_MIME}' and trashed = false",
                                 fields="nextPageToken,files(id,name)", pageSize=200, pageToken=token).execute()
            for f in r.get("files", []):
                m = re.match(r"(\d{4}-\d{2}-\d{2})", f["name"])
                if m:
                    folders[m.group(1)] = f["id"]
            token = r.get("nextPageToken")
            if not token:
                break
    out: list[dict] = []
    for d, e in sorted(by_date.items()):
        path: Path | None = None
        if today and d == today and today_out and (today_out / "short.mp4").exists():
            path = today_out / "short.mp4"
        elif svc and d in folders:
            local = CACHE / "shorts" / f"{d}.mp4"
            if not local.exists():
                q = f"name = 'short.mp4' and '{folders[d]}' in parents and trashed = false"
                files = svc.files().list(q=q, fields="files(id)", pageSize=1).execute().get("files", [])
                if files:
                    _download(svc, files[0]["id"], local)
            if local.exists():
                path = local
        if path:
            out.append({**e, "path": path})
    return out


# ---------------------------------------------------------------- Auswahl -------------------------------------------
def select(shorts: list[dict], mode: str, today: str, seed: int | None = None) -> list[dict]:
    """Liefert die Reihenfolge der Shorts für den Zusammenschnitt (heutiger immer zuerst, wenn vorhanden)."""
    rnd = random.Random(seed if seed is not None else int(today.replace("-", "")))
    todays = [s for s in shorts if s["date"] == today]
    others = [s for s in shorts if s["date"] != today]
    if mode == "daily":
        pick = others[:]
        rnd.shuffle(pick)
        return todays + pick[:DAILY_OLD_COUNT]
    if mode == "weekly":
        d = date.fromisoformat(today)
        week_start = (d - timedelta(days=6)).isoformat()
        week = [s for s in shorts if week_start <= s["date"] <= today]
        week.sort(key=lambda s: s["date"], reverse=True)
        rest = [s for s in shorts if s["date"] < week_start]
        rest.sort(key=lambda s: s.get("views", 0), reverse=True)
        return week + rest[:WEEKLY_TOP_COUNT]
    if mode == "monthly":
        d = date.fromisoformat(today)
        first_this = d.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        month = last_prev.strftime("%Y-%m") if d.day <= 3 else d.strftime("%Y-%m")
        sel = [s for s in shorts if s["date"].startswith(month)]
        sel.sort(key=lambda s: s["date"], reverse=True)
        return sel
    raise ValueError(mode)


# ---------------------------------------------------------------- Bausteine rendern --------------------------------
def _run(cmd: list[str]) -> None:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg fehlgeschlagen:\n{' '.join(cmd)}\n{res.stderr[-1500:]}")


def _norm_video_args() -> list[str]:
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]


def segment_short(src: Path, out: Path, accent: tuple[int, int, int]) -> Path:
    """9:16-Short → 1920×1080: weich verschwommener, aufgehellter Hintergrund aus dem Short selbst, Short mittig."""
    out.parent.mkdir(parents=True, exist_ok=True)
    r, g, b = accent
    fc = (f"[0:v]split=2[bg][fg];"
          f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=40,"
          f"colorbalance=rs=0.05:gs=0.03:bs=0.05,eq=brightness=0.06:saturation=1.25,format=yuv420p[bgb];"
          f"[fg]scale=-2:{H},setsar=1[fgs];"
          f"[bgb][fgs]overlay=(W-w)/2:0:format=auto,fps={FPS},format=yuv420p,setsar=1[v]")
    audio = ["-map", "0:a?"] if render.has_audio(src) else []
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-filter_complex", fc,
           "-map", "[v]", *audio, *_norm_video_args(), str(out)]
    if not audio:
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
               "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-filter_complex", fc,
               "-map", "[v]", "-map", "1:a", "-shortest", *_norm_video_args(), str(out)]
    _run(cmd)
    return out


def segment_intro(src: Path, out: Path) -> Path:
    """Intro auf 1920×1080/30fps/AAC normalisieren (füllt mit weichen Rändern, falls das Format abweicht)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    fc = (f"[0:v]split=2[bg][fg];[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=30[bgb];"
          f"[fg]scale={W}:{H}:force_original_aspect_ratio=decrease,setsar=1[fgs];"
          f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,fps={FPS},format=yuv420p,setsar=1[v]")
    if render.has_audio(src):
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-filter_complex", fc,
               "-map", "[v]", "-map", "0:a", *_norm_video_args(), str(out)]
    else:
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-f", "lavfi",
               "-i", "anullsrc=r=48000:cl=stereo", "-filter_complex", fc, "-map", "[v]", "-map", "1:a",
               "-shortest", *_norm_video_args(), str(out)]
    _run(cmd)
    return out


def _card_image(title: str, subtitle: str, bg: tuple[int, int, int], out: Path, logo: bool = False) -> Path:
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img, "RGBA")
    rnd = random.Random(sum(bg))
    for _ in range(60):   # weiche Lichtpunkte
        x, y, rad = rnd.randint(0, W), rnd.randint(0, H), rnd.randint(10, 46)
        d.ellipse((x - rad, y - rad, x + rad, y + rad), fill=(255, 255, 255, rnd.randint(40, 110)))
    img = img.filter(ImageFilter.GaussianBlur(2))
    d = ImageDraw.Draw(img)
    big = _font(118)
    small = _font(54, "SemiBold")
    y = H // 2 - 60
    if logo and LOGO.exists():
        lg = Image.open(LOGO).convert("RGBA").resize((300, 300), Image.LANCZOS)
        mask = Image.new("L", lg.size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 299, 299), fill=255)
        img.paste(lg, (W // 2 - 150, 150), mask)
        y = 520
    for line, f in ((title, big), (subtitle, small)):
        if not line:
            continue
        tw = d.textlength(line, font=f)
        d.text((W / 2 - tw / 2 + 5, y + 7), line, font=f, fill=(90, 60, 30))
        d.text((W / 2 - tw / 2, y), line, font=f, fill=(255, 255, 255), stroke_width=6, stroke_fill=(255, 138, 70))
        y += int(f.size * 1.35)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    return out


def segment_card(png: Path, out: Path, seconds: float, chime: Path | None = None) -> Path:
    """Standbild mit sanftem Zoom; Ton: Glöckchen aus der SFX-Bibliothek oder Stille."""
    frames = int(seconds * FPS)
    vf = (f"scale={W + 96}:{H + 54},zoompan=z='min(1.0+0.0015*on,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
          f":d={frames}:s={W}x{H}:fps={FPS},fade=t=in:d=0.25,fade=t=out:st={seconds - 0.25:.2f}:d=0.25,format=yuv420p,setsar=1")
    if chime and chime.exists():
        audio_in = ["-i", str(chime)]
        af = ["-af", f"volume=-6dB,apad,atrim=0:{seconds}"]
    else:
        audio_in = ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        af = []
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-i", str(png), *audio_in,
           "-vf", vf, *af, "-t", f"{seconds}", "-shortest", *_norm_video_args(), str(out)]
    _run(cmd)
    return out


def concat(segments: list[Path], out: Path) -> Path:
    """Alle Segmente (gleiches Format) zu einem Video – Loudness −14 LUFS, Kapitel aus den Längen."""
    out.parent.mkdir(parents=True, exist_ok=True)
    inputs: list[str] = []
    for s in segments:
        inputs += ["-i", str(s)]
    n = len(segments)
    fc = "".join(f"[{i}:v]setsar=1,settb=AVTB,fps={FPS}[v{i}];[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,asettb=AVTB[a{i}];" for i in range(n)) \
         + "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a0];" \
         f"[a0]loudnorm=I={config.TARGET_LUFS}:TP=-1.0:LRA=11[a]"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex", fc,
           "-map", "[v]", "-map", "[a]", *_norm_video_args(), "-movflags", "+faststart", str(out)]
    _run(cmd)
    return out


# ---------------------------------------------------------------- Thumbnail + Kapitel --------------------------------
def make_thumbnail(today_thumb: Path | None, count: int, mode: str, out: Path) -> Path:
    """1280×720: heutige Figur rechts (aus dem 9:16-Thumbnail), links großer Text „10 Cute Stories“."""
    tw, th = 1280, 720
    bg_col = PASTELS[count % len(PASTELS)]
    img = Image.new("RGB", (tw, th), bg_col)
    if today_thumb and today_thumb.exists():
        art = Image.open(today_thumb).convert("RGB")
        bg = art.resize((tw, int(art.height * tw / art.width)), Image.LANCZOS)
        bg = bg.crop((0, (bg.height - th) // 2, tw, (bg.height - th) // 2 + th)).filter(ImageFilter.GaussianBlur(28))
        img = Image.blend(bg, Image.new("RGB", (tw, th), bg_col), 0.35)
        fig = art.resize((int(art.width * th / art.height), th), Image.LANCZOS)
        fig = fig.crop((0, 0, min(fig.width, 560), th))
        img.paste(fig, (tw - fig.width, 0))
    d = ImageDraw.Draw(img)
    label = {"daily": "CUTE STORIES", "weekly": "BEST OF THE WEEK", "monthly": "MONTHLY MARATHON"}[mode]
    lines = [f"{count}", label, "for toddlers"]
    fonts = [_font(300), _font(96), _font(64, "SemiBold")]
    y = 40
    for line, f in zip(lines, fonts):
        d.text((70 + 6, y + 8), line, font=f, fill=(90, 60, 30))
        d.text((70, y), line, font=f, fill=(255, 255, 255), stroke_width=8 if f.size > 100 else 5, stroke_fill=(255, 138, 70))
        y += int(f.size * 1.1)
    if LOGO.exists():
        lg = Image.open(LOGO).convert("RGBA").resize((130, 130), Image.LANCZOS)
        mask = Image.new("L", lg.size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 129, 129), fill=255)
        img.paste(lg, (70, th - 160), mask)
        d.text((220, th - 125), "Giggle Meadow", font=_font(56), fill=(255, 255, 255), stroke_width=4, stroke_fill=(110, 70, 140))
    out.parent.mkdir(parents=True, exist_ok=True)
    for q in (92, 85, 78):
        img.save(out, "JPEG", quality=q)
        if out.stat().st_size < 2_000_000:
            break
    return out


def fmt_ts(sec: float) -> str:
    s = int(sec)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def clean_title(t: str) -> str:
    t = re.sub(r"#\w+", "", t or "").strip(" –-|")
    return t[:60]


# ---------------------------------------------------------------- Gesamtablauf ----------------------------------------
def build(mode: str, today: str, out: Path, today_out: Path | None = None, dry_shorts: list[dict] | None = None,
          intro: Path | None = None) -> dict:
    """Erzeugt <out>/compilation.mp4, thumbnail.jpg, chapters.txt. Liefert Infos für Metadaten + Report."""
    out.mkdir(parents=True, exist_ok=True)
    shorts = dry_shorts if dry_shorts is not None else fetch_shorts(today_out, today)
    chosen = select(shorts, mode, today)
    if len(chosen) < 2:
        raise RuntimeError(f"zu wenige Shorts für einen Zusammenschnitt ({len(chosen)})")
    if intro is None and dry_shorts is None:
        intro = fetch_intro()
    seg_dir = out / "segments"
    segments: list[Path] = []
    chapters: list[tuple[float, str]] = []
    t = 0.0
    chime = config.ROOT / "assets" / "kids_sfx" / "sparkle.mp3"
    if intro and intro.exists():
        s = segment_intro(intro, seg_dir / "00_intro.mp4")
        segments.append(s)
        chapters.append((0.0, "Intro"))
        t += render.duration(s)
    else:
        card = _card_image("Giggle Meadow", "tiny cute stories for little ones", PASTELS[0], seg_dir / "00_intro.png", logo=True)
        s = segment_card(card, seg_dir / "00_intro.mp4", 3.0, chime)
        segments.append(s)
        chapters.append((0.0, "Intro"))
        t += 3.0
    for i, sh in enumerate(chosen, 1):
        col = PASTELS[i % len(PASTELS)]
        name = sh.get("name") or ""
        species = sh.get("species") or ""
        sub = f"{name} the {species}".strip() if name else species
        card = _card_image(clean_title(sh.get("title", "")) or f"Story {i}", sub, col, seg_dir / f"{i:02d}_card.png")
        c = segment_card(card, seg_dir / f"{i:02d}_card.mp4", TITLE_CARD_SEC, chime)
        segments.append(c)
        chapters.append((t, clean_title(sh.get("title", "")) or f"Story {i}"))
        t += TITLE_CARD_SEC
        v = segment_short(sh["path"], seg_dir / f"{i:02d}_short.mp4", col)
        segments.append(v)
        t += render.duration(v)
    outro = _card_image("See you tomorrow!", "a new story every day at 4 pm  •  Giggle Meadow", PASTELS[3],
                        seg_dir / "99_outro.png", logo=True)
    segments.append(segment_card(outro, seg_dir / "99_outro.mp4", OUTRO_SEC, chime))
    chapters.append((t, "See you tomorrow"))
    final = concat(segments, out / "compilation.mp4")
    dur = render.duration(final)
    today_thumb = (today_out / "thumbnail.jpg") if today_out and (today_out / "thumbnail.jpg").exists() else None
    if today_thumb is None and chosen and dry_shorts is None:
        today_thumb = None
    make_thumbnail(today_thumb, len(chosen), mode, out / "thumbnail.jpg")
    chap_txt = "\n".join(f"{fmt_ts(ts)} {name}" for ts, name in chapters)
    (out / "chapters.txt").write_text(chap_txt)
    info = {"mode": mode, "count": len(chosen), "duration_sec": dur, "chapters": chap_txt,
            "stories": [{"date": s["date"], "title": s.get("title", ""), "name": s.get("name", ""),
                         "species": s.get("species", ""), "video_id": s.get("video_id")} for s in chosen],
            "intro": str(intro) if intro else "(Karte)", "video": str(final), "thumbnail": str(out / "thumbnail.jpg")}
    (out / "compilation_info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))
    return info


# ---------------------------------------------------------------- Metadaten --------------------------------------------
def metadata(info: dict, today: str) -> dict:
    """Titel/Beschreibung/Tags (EN) – per Gemini, mit sicherem Fallback ohne API."""
    mode, n = info["mode"], info["count"]
    first = clean_title(info["stories"][0]["title"]) if info["stories"] else "Cute Stories"
    minutes = max(1, round(info["duration_sec"] / 60))
    fallback_title = {
        "daily": f"{n} Cute Baby Animal Stories for Toddlers 🌼 {first} & more | Giggle Meadow",
        "weekly": f"Best of the Week: {n} Cute Cartoons for Toddlers 🐥 Calm, No Talking | Giggle Meadow",
        "monthly": f"{n} Cute Stories Marathon for Toddlers 🧸 {minutes} Minutes of Calm Cartoons | Giggle Meadow",
    }[mode]
    stories_lines = "\n".join(f"• {clean_title(s['title'])}" for s in info["stories"])
    fallback_desc = (
        f"{n} tiny cute cartoons in one video – gentle baby animals, little adventures, happy endings. 🌼\n"
        f"Made for toddlers and preschoolers (ages 1–5): no talking, no scary moments, just sweet sounds and bright colors.\n"
        f"Perfect for a calm minute, a car ride or bedtime.\n\n"
        f"⏱️ Chapters\n{info['chapters']}\n\n"
        f"📖 Stories in this video\n{stories_lines}\n\n"
        f"🐥 New 15-second story every day at 4 pm (CET) – and a fresh compilation every day too!\n"
        f"All characters and stories are original creations by Giggle Meadow.\n\n"
        f"cute cartoon for toddlers · baby animals compilation · calm video for kids · toddler video no talking · "
        f"bedtime cartoon · preschool cartoon · 3D animation for kids · cute animal stories\n\n"
        f"#kids #toddlers #cutecartoon #babyanimals #kidsvideos #3danimation #compilation #gigglemeadow"
    )
    tags = ["cute cartoon compilation", "toddler cartoon", "baby animals cartoon", "calm video for kids",
            "no talking cartoon", "bedtime cartoon", "preschool cartoon", "3d animation kids", "cute animal stories",
            "kids compilation", "giggle meadow", "cartoon for babies", "wholesome kids video", "toddler videos"]
    try:
        from . import gemini
        prompt = (
            f"Write YouTube metadata (English) for a {mode} compilation video on the kids channel 'Giggle Meadow': "
            f"{n} wordless 15-second Pixar-style cartoons about cute baby animals for toddlers (ages 1–5), "
            f"{minutes} minutes long. Stories: {json.dumps([clean_title(s['title']) for s in info['stories']])}.\n"
            f"Chapters (must appear verbatim in the description):\n{info['chapters']}\n"
            "Return JSON {\"title\": str (< 90 chars, emotional, parent-search keywords like 'cute cartoon for toddlers', "
            "one emoji, ends with '| Giggle Meadow'), \"description\": str (first line hooks parents, then who it's for, "
            "then the chapter list exactly as given, then a bullet list of the stories, then 8 search phrases, then "
            "8 hashtags), \"tags\": [15-20 strings]}. No brand names, no known characters."
        )
        data = gemini.text_json(prompt, "You are a YouTube growth strategist for kids content. Answer with JSON only.",
                                temperature=0.8)
        title = str(data.get("title", "")).strip() or fallback_title
        desc = str(data.get("description", "")).strip() or fallback_desc
        if info["chapters"].split("\n")[1].split(" ", 1)[0] not in desc:
            desc += "\n\n⏱️ Chapters\n" + info["chapters"]
        tg = [str(x) for x in data.get("tags", [])][:20] or tags
        return {"title": title[:100], "description": desc[:4900], "tags": tg}
    except Exception as e:  # noqa: BLE001
        print(f"[compilation] Metadaten per Gemini fehlgeschlagen, Fallback: {e}")
        return {"title": fallback_title[:100], "description": fallback_desc[:4900], "tags": tags}


def mode_for(today: str) -> str:
    d = date.fromisoformat(today)
    if d.day == 1:
        return "monthly"
    if d.weekday() == 6:
        return "weekly"
    return "daily"
