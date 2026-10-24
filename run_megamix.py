#!/usr/bin/env python3
"""Samstags-Mega-Mix (Rolf, 17.10.2026): jeden Samstag ein langer Mix (bis 8 Std.) aus den vorhandenen Genre-Mixen.

  * Songs in Zufallsreihenfolge, pro Mix kein Song doppelt (pipeline/megamix.py), keine neue Musik, keine DistroKid-Abgabe.
  * Veröffentlichung geplant für 14:00 Uhr Berlin (liegt das schon zu nah/in der Vergangenheit: sofort öffentlich).
  * Italian Chillout / Mediterranean Lounge: kein neues Video (atmendes Licht aus den vorhandenen Track-Covern),
    nur EIN neues Hauptbild (Nano Banana, ca. 0,24 $) → Thumbnail mit auffälliger Schrift + Album-Cover 3000×3000.
  * Cozy Winter Cabin: neues Hauptbild + 2 neue Veo-Clips in 4K (ca. 5 $), nahtlos aneinandergesetzt wie bei den
    Cabin-Mixen; Schneeflocken im Prompt klein und fein; Musik nur aus den vorhandenen Cabin-Mixen.
  * 2 Shorts je Mega-Mix: Short 1 gehört zum Samstag, Short 2 zum Sonntag (beide privat; die Aufgabe „Related Video“ am
    Abend setzt den Link zum Mix und schaltet öffentlich, Instagram/TikTok plant Metricool). Cabin: Ausschnitte aus
    dem neuen 4K-Material; sonst: bereits bezahlte Kling-Clips der Warteschlange (run_short_v2.py --free-only).

  python run_megamix.py --genre all                   # ALLE Genres nacheinander (Standard am Samstag)
  python run_megamix.py --genre auto                  # nächstes Genre der Rotation (Italian → Cabin → Lounge)
  python run_megamix.py --genre "Cozy Winter Cabin"
  python run_megamix.py --genre "Italian Chillout" --dry-run   # synthetisch, kein Drive/YouTube/Mail, keine Kosten
"""
import argparse
import re
import base64
import json
import random
import shutil
import subprocess
import sys
import time
from datetime import date, timedelta
from email.message import EmailMessage
from pathlib import Path

from PIL import Image

from pipeline import audio, cabin_art, config, costs, images, loopvideo, megamix, memory, metadata, monthly, planner, shorts

CRACKLE = config.ASSETS / "ambience" / "fireplace_crackle_loop.m4a"
CABIN = "Cozy Winter Cabin"
MIN_TOTAL_MIN = 90                        # kürzer lohnt kein Mega-Mix
PLAN_MIN_PER_MIX = {CABIN: 120}           # Schätzung der Länge je Quell-Mix, bevor sie geladen sind (sonst 60 Min.)
WINDOW_DAYS = {CABIN: 35}                 # so weit zurück werden Quell-Mixe gesucht (sonst 28 Tage)
SHORT_GENRE = {"Italian Chillout": "Italian Chillout", "Mediterranean Lounge": "Mediterranean Spa Lounge"}
IMG_GENRE = {"Mediterranean Lounge": "Mediterranean Spa Lounge"}   # Bildstil/Motive der Lounge-Linie
NAMES = {
    "Italian Chillout": ["Sabato Sera", "Weekend in Positano", "Lake Como Weekend", "Amalfi Nights", "Dolce Weekend",
                         "Una Notte a Como", "Riviera Saturday", "Ravello Evenings", "Weekend al Lago", "Notte d'Estate",
                         "Golden Coast Weekend", "Bellagio Nights", "Sera Italiana", "Capri Evenings", "Portofino Hours"],
    "Mediterranean Lounge": ["Azure Terrace Weekend", "Sunset Terrace Hours", "Balearic Weekend", "Golden Hour Lounge",
                             "Marina Lounge Nights", "Cala Blue Weekend", "Blue Hour Lounge", "Sea Breeze Weekend"],
    CABIN: ["Snowbound Nights", "Long Winter Evenings", "Fireside Hours", "Deep Snow Hours",
            "Candlelit Cabin Nights", "Embers and Pines", "Woodsmoke Evenings",
            "Frost and Firelight", "Northern Cabin Nights", "Warm Hearth Hours"],
}
ESTIMATE_USD = {CABIN: 4.80 + 0.24, "Italian Chillout": 0.24, "Mediterranean Lounge": 0.24}   # Veo 16 s × 0,30 $ + Hauptbild


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] [megamix] {msg}", flush=True)


# ---------------------------------------------------------------- Quellen
def list_sources(svc, genre: str) -> list[dict]:
    """Alle Quell-Mixe des Genres, neueste zuerst: [{date, album, name, id, genre}]."""
    if genre == CABIN:
        from run_cabin_compilation import cabin_folders
        return sorted(cabin_folders(svc), key=lambda f: f["date"], reverse=True)
    from monthly_mix import collect_folders
    want = megamix.GROUPS.get(genre, (genre,))
    return sorted([f for f in collect_folders(svc) if f["genre"] in want], key=lambda f: f["date"], reverse=True)


def pick_sources(folders: list[dict], genre: str, max_hours: float, today: date) -> list[dict]:
    """Neueste Mixe zuerst, bis das Material mit etwas Luft für die Auswahl reicht (≈ 1,3 × Zielzeit)."""
    lo = (today - timedelta(days=WINDOW_DAYS.get(genre, 28))).isoformat()
    need = max_hours * 60 * 1.3
    out, have = [], 0.0
    for f in folders:
        if f["date"] < lo or f["date"] > today.isoformat():
            continue
        out.append(f)
        have += PLAN_MIN_PER_MIX.get(genre, 60)
        if have >= need:
            break
    return sorted(out, key=lambda f: f["date"])


def fetch_all(svc, sources: list[dict], dst: Path) -> list[tuple[dict, dict]]:
    from monthly_mix import fetch_mix
    pairs = []
    for f in sources:
        log(f"lade {f['name']} …")
        pairs.append((f, fetch_mix(svc, f, dst)))
    return pairs


def synthetic(dst: Path, genre: str) -> list[tuple[dict, dict]]:
    """Dry-run: fünf Fake-Mixe mit je 4 Sinus-MP3s (45 s), davon ein doppelter Titel."""
    out = []
    for i in range(5):
        d = dst / f"fake{i}"
        d.mkdir(parents=True, exist_ok=True)
        tracks, titles = [], []
        for t in range(4):
            p = d / f"{t + 1:02d} - Aix Walker - Fake {i}{t}.mp3"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                            f"sine=frequency={180 + 37 * (i * 4 + t)}:duration={40 + i * 3 + t}", "-ac", "2", str(p)], check=True)
            tracks.append(p)
            titles.append("Same Song" if (i == 3 and t == 0) or (i == 1 and t == 0) else f"Fake {i}{t}")
        cover = d / "cover.png"
        images.procedural_art("1:1", seed=i).save(cover)
        out.append(({"album": f"Fake Mix {i}", "genre": genre, "bpm": 90 + i, "date": f"2026-10-0{i + 1}",
                     "name": f"2026-10-0{i + 1} – Fake Mix {i}"},
                    {"tracks": tracks, "titles": titles, "cover": cover, "minutes": 3.0}))
    return out


# ---------------------------------------------------------------- Texte
def pick_name(genre: str, mem: dict) -> str:
    used = {str(e.get("name", "")).lower() for k in ("megamix", "weekly", "cabin_compilations") for e in mem.get(k, [])}
    used |= memory.used_albums(mem)
    names = NAMES[genre]
    free = [n for n in names if n.lower() not in used]
    return free[0] if free else f"{names[date.today().isocalendar()[1] % len(names)]} {date.today().isocalendar()[1]}"


COMMUNITY_MOOD = {
    "Italian Chillout": ("🌙🍋", "Lanterns on the cliffs, the sea whispering below, and a warm Italian evening that never wants to end. 💛"),
    "Mediterranean Lounge": ("🌅🍷", "Golden light on the water, a slow breeze and the soft hum of a summer evening by the sea. 💛"),
}


def community_text(genre: str, name: str, url: str) -> str:
    """Community-Beitrag (Englisch, kurz, romantisch, mit Video-Link; Rolf 24.10.2026). Keine Zeit-/Längenangaben.
    '{URL}' bleibt Platzhalter, bis der Link bekannt ist (send_mail ersetzt ihn)."""
    emo, line = COMMUNITY_MOOD.get(genre, COMMUNITY_MOOD["Italian Chillout"])
    tag = "".join(ch for ch in name.title() if ch.isalnum())
    return (f"{emo} AIX WALKER Mega-Mix · {name}\n\n{line}\n\n"
            f"Press play, dim the lights and let the night take you slowly. 🎧🌊\n\n▶️ {url}\n\n"
            f"#AixWalker #{tag} #{genre.replace(' ', '')} #RomanticVibes")


def texts_music(genre: str, name: str, total_min: int, albums: list[dict], chapters: str, bpm: str, playlist_id: str) -> dict:
    head, _, tags, playlist = monthly.genre_info(IMG_GENRE.get(genre, genre) if genre != "Italian Chillout" else genre)
    keyword = config.THUMB_KEYWORD.get(IMG_GENRE.get(genre, genre), head)
    hrs = metadata.hours_wording(total_min)
    title = f"{name} · {keyword} · {hrs} Long Mix"[:100]
    src = "\n".join(f"• {a['album']}" + (f" – https://youtu.be/{a['video_id']}" if a.get("video_id") else "") for a in albums)
    mood = ("Sunset aperitivo on the Amalfi Coast, a candlelit dinner on Lake Como" if genre == "Italian Chillout"
            else "Golden-hour terraces, ocean air and slow balearic grooves")
    desc = f"""🎧 {hrs} of calm {keyword.lower()} – one long, uninterrupted mix, shuffled from {len(albums)} of our mixes.

{mood}: every song plays only once, blended with smooth crossfades. No vocals, no ads in between – perfect for dinner, reading, working or a slow evening.

⏱️ CHAPTERS
{chapters}

📀 SHUFFLED FROM THESE MIXES
{src}

🔊 {bpm} BPM · no vocals · mastered for headphones and speakers
🎵 All tracks produced by {config.ARTIST} (AI-assisted, original music)
▶️ Full playlist: https://www.youtube.com/playlist?list={playlist_id}
🔔 New mixes regularly – subscribe and hit the bell!

👇 Where would you listen to this?

#{keyword.replace(' ', '')} #ChilloutMusic #LoungeMusic #{config.ARTIST.replace(' ', '')}
"""
    tags = list(dict.fromkeys(tags + ["long mix", f"{hrs.lower()} mix", "shuffled mix", "dinner music", "aix walker",
                                      "no vocals"]))[:15]
    comment = "🍋 The long mix is live! Which part of the day are you listening in? Full tracklist with timestamps below 👇"
    community = community_text(genre, name, "{URL}")
    return {"title": title, "description": desc[:5000], "tags": tags, "comment": comment, "community_de": community,
            "keyword": keyword, "playlist": playlist}


def texts_cabin(name: str, total_min: int, albums: list[dict], chapters: str, playlist_id: str) -> dict:
    hrs = metadata.hours_wording(total_min)
    title = f"{name} · Cozy Winter Cabin · {hrs} Relaxing Fireplace Chillout 4K"[:100]
    src = "\n".join(f"• {a['album']}" + (f" – https://youtu.be/{a['video_id']}" if a.get("video_id") else "") for a in albums)
    desc = f"""🎧 {hrs} in a cozy winter cabin: a crackling fireplace, candlelight and a quiet, snow-covered landscape outside – with warm lofi jazz and ambient chillout, in 4K.

One long, uninterrupted session with the songs of our fireplace films, shuffled – every song plays only once. Perfect to leave running while you read, work, study or fall asleep on a cold winter night.

⏱️ CHAPTERS
{chapters}

📀 SHUFFLED FROM THESE FIREPLACE FILMS
{src}

🔥 Real crackling fire sounds · no vocals · no interruptions · mastered quietly for background listening
🎵 All music produced by {config.ARTIST} (AI-assisted, original music)
▶️ Full playlist: https://www.youtube.com/playlist?list={playlist_id}
🔔 New cozy cabin films regularly – subscribe and hit the bell!

👇 What are you doing while the snow lies quiet outside?

#CozyWinterCabin #FireplaceAmbience #CozyCabin #WinterAmbience #AixWalker
"""
    tags = ["cozy winter cabin", "fireplace ambience 4k", "cozy cabin ambience", "winter cabin fireplace",
            "relaxing fireplace music", "snowy cabin ambience", "lofi jazz fireplace", f"{hrs.lower()} fireplace",
            "long fireplace video", "sleep music winter", "study music cozy", "aixwalker", "aix walker"]
    comment = f"❄️🔥 {hrs} by the fire – full tracklist with timestamps below 👇"
    community = (f"🔥❄️ AIX WALKER Mega-Mix · {name}\n\nA crackling fire, quiet snow outside and soft music for a slow winter evening. 💛\n\n"
                 f"Press play, wrap up warm and let the night take you slowly. 🎧\n\n▶️ {{URL}}\n\n"
                 f"#AixWalker #CozyCabin #FireplaceMusic #WinterVibes")
    return {"title": title, "description": desc[:5000], "tags": tags, "comment": comment, "community_de": community}


# ---------------------------------------------------------------- Mail
def send_mail(res: dict) -> dict:
    from pipeline import mailer
    svc = mailer._service()
    to = config.REPORT_EMAIL or svc.users().getProfile(userId="me").execute()["emailAddress"]
    t = res["texts"]
    when = ("PRIVAT hochgeladen (noch nicht öffentlich)" if res.get("private")
            else f"geplant für {res['publish_local']} Uhr (Berlin)" if res.get("publish_at") else "sofort öffentlich")
    lines = [f"AIX WALKER Mega-Mix ({res['genre']}) ist hochgeladen – {when}", "",
             f"Titel: {res['title']}", f"Video: {res.get('video_url')}",
             f"Dauer: {res['duration_min']} Min · {res['tracks']} Songs (zufällig gemischt, keine Datei doppelt) aus "
             f"{len(res['albums'])} Mixen: {', '.join(res['albums'])}", f"Drive: {res.get('drive_folder', '-')}",
             f"Kosten: Voranschlag {res['estimate_usd']:.2f} $ ≈ {res['estimate_usd'] * config.USD_EUR_RATE:.2f} €, "
             f"tatsächlich {res['cost_usd']:.2f} $ ≈ {res['cost_usd'] * config.USD_EUR_RATE:.2f} €",
             "Kein DistroKid-Release.", *res.get("extra_lines", []), "",
             "Shorts (privat; der Link zum Mix wird abends 19:45 in Studio gesetzt, dann öffentlich):"]
    lines += [f"  - {s['date']}: {s['title']} → {s.get('url') or s.get('error', 'nicht erzeugt')}" for s in res["shorts"]] or ["  (keine)"]
    lines += ["", "Kommentar mit Tracklist: " + ("gepostet – nur noch anpinnen (Studio → Kommentare → ⋮ → Anpinnen)"
                                                 if res.get("comment_ids") else "NICHT gepostet – Text steht in metadata.txt im Drive-Ordner"),
              "", "Community-Beitrag (Text zum Einfügen, Album-Cover hängt an):", t["community_de"].replace("{URL}", str(res.get("video_url") or "")), "", "Kapitel:", res["chapters"]]
    msg = EmailMessage()
    msg["To"], msg["From"] = to, "me"
    msg["Subject"] = f"AIX WALKER Mega-Mix: {res['name']} ({res['duration_min']} Min) – {when}"
    msg.set_content("\n".join(lines))
    for p in (res.get("thumbnail"), res.get("cover")):
        if p and Path(p).exists():
            mailer._attach_image(msg, Path(p))
    svc.users().messages().send(userId="me", body={"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}).execute()
    return {"sent": True, "to": to}


# ---------------------------------------------------------------- Shorts
def excerpt(flac: Path, start: float, dst: Path, sec: int = 90) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.1f}", "-t", str(sec), "-i", str(flac), "-ac", "2",
                    "-ar", "44100", str(dst)], check=True)
    return dst


def shorts_music(base: Path, flac: Path, vid: str, genre: str, days: list[date], dry: bool) -> list[dict]:
    """Variante Musik: je ein Short über run_short_v2.py (nur schon bezahlte Kling-Clips, privat)."""
    out = []
    total = audio.probe_duration(flac)
    for k, day in enumerate(days):
        entry = {"date": day.isoformat(), "title": None}
        if dry:
            entry["error"] = "Dry-Run: Short übersprungen"
            out.append(entry)
            continue
        wav = excerpt(flac, total * (0.2 + 0.4 * k), base / f"short_music_{k + 1}.wav")
        cmd = [sys.executable, "run_short_v2.py", "--free-only", "--private", "--megamix", "--genre",
               SHORT_GENRE.get(genre, genre), "--target-video-id", vid, "--audio", str(wav), "--date", day.isoformat()]
        log("Short " + str(k + 1) + ": " + " ".join(cmd[1:]))
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=config.ROOT)
        tail = (r.stdout + r.stderr)[-1500:]
        log(tail.strip().splitlines()[-1] if tail.strip() else "(keine Ausgabe)")
        entry["ok"] = r.returncode == 0
        entry["error"] = None if r.returncode == 0 else tail[-300:]
        for line in tail.splitlines():
            if '"url"' in line:
                entry["url"] = line.split(":", 1)[1].strip(' ",')
            if '"title"' in line and not entry["title"]:
                entry["title"] = line.split(":", 1)[1].strip(' ",')
        entry["title"] = entry["title"] or "(kein Short erzeugt – siehe Log)"
        out.append(entry)
    return out


def shorts_cabin(base: Path, final_flac: Path, starts: list[float], clips: list[Path], frame: Image.Image, name: str,
                 vid: str | None, mem: dict, days: list[date], dry: bool, video_url: str) -> list[dict]:
    """Zwei Cabin-Shorts aus dem NEUEN 4K-Material (Ausschnitt Kamin bzw. Fenster/Sofa), privat hochgeladen; Eintrag im
    Gedächtnis mit dem Datum des jeweiligen Tages, Drive-Ablage wie bei den übrigen Shorts 2.0."""
    import run_cabin
    from run_short_v2 import upload_drive
    (base / "shorts").mkdir(exist_ok=True)
    total = audio.probe_duration(final_flac)
    passages = shorts.find_passages(final_flac, starts, total, run_cabin.SHORT_SEC, 2,
                                    min_gap_sec=60 if dry else 1800)
    q0 = (date.today().toordinal() * 2) % len(cabin_art.SHORT_QUESTIONS)
    out = []
    for k, (p, day) in enumerate(zip(passages, days)):
        q = cabin_art.SHORT_QUESTIONS[(q0 + k) % len(cabin_art.SHORT_QUESTIONS)]
        mp4 = run_cabin.make_short(clips, k, frame, final_flac, p["start"], q, base)
        s_title, s_desc, s_tags = run_cabin.short_texts({"album": name}, q, video_url)
        sid = f"megacabin-{days[0].isoformat()}-{k + 1}"
        e = {"date": day.isoformat(), "id": sid, "title": s_title, "file": str(mp4)}
        if not dry:
            from pipeline import youtube
            try:
                e["video_id"] = youtube.upload_video(mp4, s_title, s_desc, s_tags, privacy="private")
                e["url"] = f"https://youtube.com/shorts/{e['video_id']}"
                final = base / "shorts" / f"Short2_{sid}.mp4"          # Name wie bei Shorts 2.0 (Instagram/TikTok-Aufgabe)
                shutil.copy(mp4, final)
                meta = base / "shorts" / f"metadata_{sid}.txt"
                meta.write_text(f"{s_title}\n\n{s_desc}\n\nTags: {', '.join(s_tags)}\n\nRelated Video: {video_url}\n", encoding="utf-8")
                try:
                    e["drive"] = upload_drive(base, {"id": sid}, [final, meta], day.isoformat())
                except Exception as ex:  # noqa: BLE001
                    e["drive_error"] = str(ex)[:160]
                mem.setdefault("shorts2", []).append({"date": day.isoformat(), "id": sid, "title": s_title,
                                                      "video_id": e["video_id"], "mix_video_id": vid, "cost_usd": 0.0,
                                                      "megamix": True})
            except Exception as ex:  # noqa: BLE001
                e["error"] = str(ex)[:300]
        out.append(e)
    return out


# ---------------------------------------------------------------- Lauf
def build_order(pairs, seed: int, max_hours: float, by_title: bool = True) -> list[dict]:
    durations = {str(t): audio.probe_duration(t) for _, mx in pairs for t in mx["tracks"]}
    tracks = megamix.collect_tracks(pairs, durations, by_title=by_title)
    log(f"{sum(len(mx['tracks']) for _, mx in pairs)} Songs gefunden, {len(tracks)} nach Entfernen von Doppelten")
    order = megamix.shuffle_unique(tracks, seed=seed, max_sec=max_hours * 3600)
    log(f"Zufallsreihenfolge: {len(order)} Songs, {megamix.total_seconds(order) / 3600:.2f} Std.")
    return order


def run_all(args) -> int:
    """Alle Genres der Rotation nacheinander (Rolf 17.10.2026: jeden Samstag EIN Mega-Mix PRO Genre). Jedes Genre läuft als
    eigener Prozess (eigener Arbeitsordner, eigenes Gedächtnis-Laden); fehlendes Material oder ein Fehler stoppt die anderen nicht.
    Reihenfolge: Italian, Lounge, zuletzt Cabin (dauert am längsten)."""
    order = ["Italian Chillout", "Mediterranean Lounge", "Cozy Winter Cabin"]
    rc = {}
    for g in order:
        cmd = [sys.executable, "run_megamix.py", "--genre", g, "--max-hours", str(args.max_hours), "--publish-at", args.publish_at]
        for flag in ("dry_run", "private", "no_email", "no_shorts"):
            if getattr(args, flag):
                cmd.append("--" + flag.replace("_", "-"))
        log(f"=== {g} ===")
        rc[g] = subprocess.run(cmd, cwd=config.ROOT).returncode
        log(f"=== {g}: Rückgabecode {rc[g]} ===")
    log("Ergebnis alle Genres: " + json.dumps(rc))
    return 0 if all(v in (0, 2) for v in rc.values()) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--genre", default="auto", choices=("auto", "all") + megamix.ROTATION)
    ap.add_argument("--max-hours", type=float, default=megamix.MAX_HOURS)
    ap.add_argument("--publish-at", default="14:00", help="Uhrzeit Berlin; 'now' = sofort öffentlich")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--private", action="store_true", help="privat lassen, nicht planen/veröffentlichen")
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--no-shorts", action="store_true")
    args = ap.parse_args()
    today = date.today()
    sat, sun = megamix.weekend_dates(today)
    if args.genre == "all":
        return run_all(args)
    base = config.ROOT / "build" / f"megamix-{today.isoformat()}-{re.sub(r'[^a-z0-9]+', '', args.genre.lower())}"
    shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True, exist_ok=True)
    costs.start(base / "costs.json")
    dry = args.dry_run

    svc, mem = None, {"mixes": []}
    if not dry:
        from pipeline import drive
        for v in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN", "DRIVE_REFRESH_TOKEN"):
            config.require(v)
        mem = memory.load()
        svc = drive.service()
    genre = args.genre
    if genre == "auto":
        if dry:
            genre = "Italian Chillout"
        else:
            avail = {}
            for g in megamix.ROTATION:
                avail[g] = len(pick_sources(list_sources(svc, g), g, args.max_hours, today))
            genre = megamix.next_genre(mem.get("megamix", []), avail)
            log(f"Material je Genre (Quell-Mixe): {avail} → {genre or 'keines ausreichend'}")
            if not genre:
                log("ABBRUCH: für kein Genre genug Quell-Mixe – nichts zu tun")
                return 2
    cabin = genre == CABIN
    week = f"{today.isocalendar()[0]}-W{today.isocalendar()[1]:02d}"
    if not dry and any(e.get("week") == week and e.get("genre") == genre for e in mem.get("megamix", [])):
        log(f"Mega-Mix {week} {genre} existiert schon – nichts zu tun")
        return 0
    est = ESTIMATE_USD[genre]
    log(f"Genre {genre} · Voranschlag Kosten {est:.2f} $ ≈ {est * config.USD_EUR_RATE:.2f} € · max. {args.max_hours:g} Std.")

    # 1) Quellen laden, mischen
    if dry:
        pairs = synthetic(base / "src", genre)
    else:
        sources = pick_sources(list_sources(svc, genre), genre, args.max_hours, today)
        log(f"Quell-Mixe: {[f['name'] for f in sources] or 'keine'}")
        if len(sources) < megamix.MIN_MIXES[genre]:
            log(f"ABBRUCH: nur {len(sources)} Quell-Mix(e) – mindestens {megamix.MIN_MIXES[genre]} nötig")
            return 2
        pairs = fetch_all(svc, sources, base / "src")
    order = build_order(pairs, seed=today.toordinal() * 31 + len(genre), max_hours=args.max_hours)
    if megamix.total_seconds(order) < (MIN_TOTAL_MIN * 60 if not dry else 60):
        log("ABBRUCH: zu wenig Material für einen Mega-Mix")
        return 2
    paths = [t["path"] for t in order]
    titles = [t["title"] for t in order]
    flac, starts = monthly.join_tracks(paths, base / "mix.flac", xf=megamix.XFADE)
    total_sec = audio.probe_duration(flac)
    total_min = int(round(total_sec / 60))
    chapters = megamix.chapter_text(titles, starts)
    comments = megamix.tracklist_comments(titles, starts)
    albums_used = list(dict.fromkeys(t["album"] for t in order))
    albums = [{"album": a, "video_id": next((e.get("video_id") for e in mem.get("mixes", [])
                                             if str(e.get("album", "")).lower() == a.lower()), None)} for a in albums_used]
    name = pick_name(genre, mem)
    log(f"{total_min} Min, {len(order)} Songs aus {len(albums)} Mixen · Name „{name}“")

    playlist_key = "cabin" if cabin else planner.GENRES.get(IMG_GENRE.get(genre, genre), {}).get("playlist", "chillout")
    playlist_id = "PLAYLIST"
    if not dry:
        from pipeline import youtube
        playlist_id = youtube.playlist_for(playlist_key)

    # 2) Bilder, Video
    cost_extra = 0.0
    mp4 = None
    clips: list[Path] = []
    frame = None
    final_flac = flac
    if cabin:
        import run_cabin
        from run_cabin_compilation import scene_prompt
        final_flac = loopvideo.mix_with_crackle(flac, CRACKLE, base / "final.flac")
        aac = loopvideo.encode_audio(final_flac, base / "work_audio.m4a")
        (base / "work").mkdir(exist_ok=True)
        (base / "img").mkdir(exist_ok=True)
        frame_png = base / "img" / "frame_4k.png"
        art = images.procedural_art("16:9") if dry else images.generate_art(
            scene_prompt(mem, today.toordinal()), "16:9", pro=True, style=images.style_for(CABIN), image_size="4K")
        frame = cabin_art.fire_right(loopvideo.frame_16x9(art))   # Kamin immer rechts, Text oben links
        frame.save(frame_png)
        frame.save(base / "master.jpg", "JPEG", quality=92)
        clips = run_cabin.make_clips(frame, base, config.LINE_FORMAT[CABIN].get("compilation_veo_clips", 2), dry)
        playlist_file = loopvideo.prepare_video(clips, total_sec, base / "work", log=log)
        thumb = cabin_art.make_thumbnail(frame, images.duration_label(total_min), base / "thumbnail.jpg")
        cover = None
        t = texts_cabin(name, total_min, albums, chapters, playlist_id)
    else:
        from run_weekly_compilation import master_scene
        igenre = IMG_GENRE.get(genre, genre)
        if dry:
            master = images.procedural_art("1:1", seed=7)
            config.GOOGLE_API_KEY = ""
        else:
            try:
                master = images.master_art(master_scene(igenre, mem, today.toordinal()), igenre)
                cost_extra = config.PRICES_USD.get("image_pro_4k", config.PRICES_USD["image_pro"])
            except Exception as e:  # noqa: BLE001
                log(f"Hauptbild fehlgeschlagen ({str(e)[:160]}) – Cover des letzten Quell-Mixes als Ersatz")
                master = Image.open(pairs[-1][1]["cover"]).convert("RGB")
        master.save(base / "master.jpg", "JPEG", quality=92)
        bpms = [int(p["bpm"]) for p, _ in pairs if p.get("bpm")] or [90]
        bpm = f"{min(bpms)}" if min(bpms) == max(bpms) else f"{min(bpms)}–{max(bpms)}"
        t = texts_music(genre, name, total_min, albums, chapters, bpm, playlist_id)
        scale = config.THUMB_TEXT_SCALE.get(igenre, 1.0)
        cover = images.make_album_cover(master, t["keyword"], name, base / "album_3000.png", text_scale=scale)
        thumb = images.make_thumbnail(images.crop_aspect(master, 16, 9), t["keyword"], name, base / "thumbnail.jpg",
                                      duration=images.duration_label(total_min), text_scale=scale)
        # Video: KEIN neues – atmendes Licht aus den vorhandenen Track-Covern (wie die übrigen Zusammenschnitte)
        mp4 = base / "megamix.mp4"
        log("Video rendern (vorhandene Track-Cover, atmendes Licht) …")
        vpair = [({"album": "Mega-Mix"}, {"tracks": paths, "cover": pairs[-1][1].get("cover")})]
        try:
            monthly.build_animated_video(vpair, flac, starts, mp4)
        except Exception as e:  # noqa: BLE001
            log(f"Animiertes Video fehlgeschlagen ({str(e)[:160]}) – Standbild")
            frame_p = base / "frame.png"
            images.make_video_frame(cover, frame_p)
            monthly.build_still_video(frame_p, flac, mp4)
        playlist_file = aac = None

    (base / "metadata.txt").write_text(
        f"=== YOUTUBE TITEL ===\n{t['title']}\n\n=== BESCHREIBUNG ===\n{t['description']}\n=== TAGS ===\n"
        f"{', '.join(t['tags'])}\n\n=== ANGEPINNTER KOMMENTAR ===\n{t['comment']}\n\n=== TRACKLISTE (Kommentar) ===\n"
        f"{chr(10).join(comments)}\n\n=== COMMUNITY-BEITRAG ===\n{t['community_de'].replace('{URL}', '(Video-Link)')}\n", encoding="utf-8")
    publish_at = None if (args.private or args.publish_at == "now") else megamix.publish_time_utc(args.publish_at)
    res = {"genre": genre, "week": week, "name": name, "title": t["title"], "duration_min": total_min,
           "albums": albums_used, "tracks": len(order), "thumbnail": str(thumb), "cover": str(cover) if cover else None,
           "chapters": chapters, "video_id": None, "video_url": None, "comment_ids": [], "texts": t, "estimate_usd": est,
           "publish_at": publish_at, "publish_local": args.publish_at, "shorts": []}

    if dry:
        if cabin:
            out_mp4 = base / "megamix.mp4"
            subprocess.run(loopvideo.mux_command(playlist_file, aac, str(out_mp4)), check=True)
            res["shorts"] = [{"date": d.isoformat(), "title": e["title"], "url": e.get("url"), "error": e.get("error")}
                             for d, e in zip((sat, sun), shorts_cabin(base, final_flac, starts, clips, frame, name, "DRYRUN",
                                                                      mem, [sat, sun], True, "https://youtu.be/DRYRUN"))]
            mp4 = out_mp4
        res["cost_usd"] = costs.total_usd()
        res["file"] = str(mp4)
        (base / "summary.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        log(f"Dry-Run fertig: {total_min} Min, {mp4} ({mp4.stat().st_size / 1e6:.0f} MB), {len(order)} Songs, "
            f"Kapitel {len(chapters.splitlines())}, Shorts {len(res['shorts'])}")
        return 0

    # 3) Hochladen (geplant 14:00 oder sofort), Thumbnail, Playlist
    from pipeline import drive, streamupload, youtube
    privacy = "private" if args.private else ("private" if publish_at else "public")
    if cabin:
        streamupload.remove_incomplete(t["title"], log=log)
        log(f"Streaming-Upload {total_min} Min 4K ({privacy}{', geplant ' + publish_at if publish_at else ''}) …")
        up = streamupload.upload_stream(loopvideo.mux_command(playlist_file, aac), t["title"], t["description"], t["tags"],
                                        privacy="private" if publish_at else privacy, log=log)
        vid = up["video_id"]
        if publish_at:
            youtube.schedule_publish(vid, publish_at)
    else:
        vid = youtube.upload_video(mp4, t["title"], t["description"], t["tags"], privacy=privacy, publish_at=publish_at)
    res["video_id"], res["video_url"] = vid, f"https://youtu.be/{vid}"
    log(f"Hochgeladen: {res['video_url']} ({'geplant ' + publish_at if publish_at else privacy})")
    for step, fn in (("Thumbnail", lambda: youtube.set_thumbnail(vid, thumb)),
                     ("Playlist", lambda: youtube.add_to_playlist(vid, playlist_id))):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            log(f"{step} fehlgeschlagen: {e}")

    # 4) Shorts (privat; Related-Video-Link + öffentlich schaltet die Abendaufgabe 19:45)
    days = [sat, sun]
    if not args.no_shorts:
        try:
            res["shorts"] = (shorts_cabin(base, final_flac, starts, clips, frame, name, vid, mem, days, False, res["video_url"])
                             if cabin else shorts_music(base, flac, vid, genre, days, False))
        except Exception as e:  # noqa: BLE001
            log(f"Shorts fehlgeschlagen: {str(e)[:200]}")
            res["shorts"] = [{"date": d.isoformat(), "title": "(Short fehlgeschlagen)", "error": str(e)[:200]} for d in days]
    if not cabin:
        mem = memory.load()     # run_short_v2 hat das Gedächtnis (shorts2) geschrieben → frisch laden, nichts überschreiben

    # 5) Drive, Gedächtnis
    files = [thumb, base / "master.jpg", base / "metadata.txt"] + ([Path(res["cover"])] if res["cover"] else [])
    links = drive.upload_mix_package(f"{today.isoformat()} – MEGAMIX {genre} – {name} ({total_min} Min)", files,
                                     {"loop_clips": clips} if clips else None)
    res["drive_folder"] = links.get("_folder")
    res["cost_usd"] = costs.total_usd() + cost_extra
    entry = {"week": week, "date": today.isoformat(), "genre": genre, "name": name, "video_id": vid, "title": t["title"],
             "duration_min": total_min, "albums": albums_used, "tracks": len(order), "drive": res["drive_folder"],
             "cost_usd": res["cost_usd"], "publish_at": publish_at}
    mem.setdefault("megamix", []).append(entry)
    memory.save(mem)

    # 6) Bericht, dann Kommentar mit Tracklist (erst möglich, wenn das Video öffentlich ist)
    if publish_at and not args.private:
        log(f"warte auf die Veröffentlichung um {args.publish_at} (für den Kommentar) …")
        wait = 5 * 3600
        if youtube.wait_until_public(vid, timeout_s=wait, log=log):
            privacy = "public"
    if privacy == "public" and not args.private:
        for k, text in enumerate([t["comment"] + "\n\n" + comments[0]] + comments[1:]):
            try:
                res["comment_ids"].append(youtube.post_comment(vid, text))
            except Exception as e:  # noqa: BLE001
                log(f"Kommentar {k + 1} fehlgeschlagen: {str(e)[:160]}")
    entry["comment_ids"] = res["comment_ids"]
    memory.save(mem)
    if not args.no_email:
        try:
            log(f"Mail: {send_mail(res)}")
        except Exception as e:  # noqa: BLE001
            log(f"Mail fehlgeschlagen: {e}")
    (base / "summary.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    shutil.rmtree(base / "src", ignore_errors=True)
    log("fertig")
    return 0


if __name__ == "__main__":
    sys.exit(main())
