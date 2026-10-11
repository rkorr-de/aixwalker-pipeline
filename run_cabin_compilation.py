#!/usr/bin/env python3
"""Lange Zusammenschnitte der Winter-Cabin-Linie (Rolf 09.10.2026), alles echtes 4K, mit NEUEM Bild + neuen Clips:

  --period biweekly  alle 2 Wochen (sonntags): die beiden letzten Freitags-Mixe → ca. 4 Std.
  --period monthly   am 1.: alle Freitags-Mixe des Vormonats → ca. 8–10 Std. (max. 11:50 Std., YouTube-Grenze 12 Std.)

Musik: die MP3s der Freitags-Mixe aus Drive (keine Lyria-Kosten). Neu: EIN Hauptbild 4K + 3 Veo-Clips (ca. 7,50 $),
Kaminfilm per Streaming-Upload (kein 27-/55-GB-Video auf der Platte), Thumbnail C mit „4 HOURS“/„8 HOURS“, Playlist,
Kommentar, Drive (Thumbnail, Hauptbild, Loop-Clips, Metadaten – keine MP3s, die liegen bei den Freitags-Mixen),
Gedächtnis (memory.json → „cabin_compilations“), Bericht per E-Mail. Keine Shorts, kein DistroKid.

  python run_cabin_compilation.py --period biweekly --if-due     # Sonntags-Routine: nur wenn fällig
  python run_cabin_compilation.py --period monthly               # Monats-Routine (Vormonat)
  python run_cabin_compilation.py --period biweekly --dry-run    # synthetisch, keine APIs, Datei statt Upload
"""
import argparse
import base64
import json
import random
import re
import shutil
import subprocess
import sys
import time
from datetime import date, timedelta
from email.message import EmailMessage
from pathlib import Path

from pipeline import audio, cabin_art, config, costs, images, loopvideo, memory, metadata, monthly, planner

GENRE = "Cozy Winter Cabin"
FOLDER_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) – (.+) \(" + GENRE + r", 4K\)$")   # Ordner der Freitags-Mixe
CRACKLE = config.ASSETS / "ambience" / "fireplace_crackle_loop.m4a"
MAX_SEC = 11 * 3600 + 50 * 60
NAMES = {
    "biweekly": ["Snowbound Nights", "Hearth and Snowfall", "Long Winter Evenings", "Fireside Hours", "Deep Snow Hours",
                 "Candlelit Cabin Nights", "Embers and Pines", "Quiet Blizzard Nights", "Woodsmoke Evenings",
                 "Frost and Firelight", "Northern Cabin Nights", "Warm Hearth Hours"],
}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] [cabin-lang] {msg}", flush=True)


def cabin_folders(svc) -> list[dict]:
    from pipeline import drive
    root = drive.ensure_folder(svc, drive.ROOT_FOLDER)
    out = []
    for f in drive.list_children(svc, root, folders=True):
        m = FOLDER_RE.match(f["name"].strip())
        if m:
            out.append({"date": m.group(1), "album": m.group(2), "name": f["name"], "id": f["id"]})
    return sorted(out, key=lambda f: f["date"])


def pick_sources(period: str, folders: list[dict], mem: dict, today: date, month: str | None) -> list[dict]:
    if period == "monthly":
        return [f for f in folders if f["date"].startswith(month)]
    used = {a for e in mem.get("cabin_compilations", []) if e.get("period") == "biweekly" for a in e.get("albums", [])}
    recent = [f for f in folders if f["date"] >= (today - timedelta(days=15)).isoformat() and f["album"] not in used]
    return recent[-2:]


def scene_prompt(mem: dict, seed: int) -> str:
    g = planner.GENRES[GENRE]
    rnd = random.Random(seed)
    recent = {str((m.get("visual") or {}).get("motif_family", "")).lower()
              for m in mem.get("mixes", []) if m.get("genre") == GENRE}
    motifs = [m for m in g["motifs"] if m.lower() not in recent] or g["motifs"]
    return f"{rnd.choice(motifs)}, {rnd.choice(planner.LIGHTS[GENRE])}. {g['visual_rule']}"


def texts(period: str, name: str, total_min: int, albums: list[dict], chapter_text: str, playlist_id: str) -> dict:
    hrs = metadata.hours_wording(total_min)
    what = "two weeks of Friday fireplace films" if period == "biweekly" else "a whole month of Friday fireplace films"
    title = f"{name} · Cozy Winter Cabin · {hrs} Relaxing Fireplace Chillout 4K"[:100]
    src = "\n".join(f"• {a['album']}" + (f" – https://youtu.be/{a['video_id']}" if a.get("video_id") else "")
                    for a in albums)
    desc = f"""🎧 {hrs} in a cozy winter cabin: a crackling fireplace, candlelight and heavy snow falling outside – with warm lofi jazz and ambient chillout, in 4K.

{what.capitalize()} in one long, uninterrupted session – perfect to leave running while you read, work, study or fall asleep on a cold winter night.

⏱️ CHAPTERS
{chapter_text}

📀 INCLUDED MIXES
{src}

🔥 Real crackling fire sounds · no vocals · no interruptions · mastered quietly for background listening
🎵 All music produced by {config.ARTIST} (AI-assisted, original music)
▶️ Full playlist: https://www.youtube.com/playlist?list={playlist_id}
🔔 A new cozy cabin film every Friday – subscribe and hit the bell!

👇 What are you doing while the snow falls outside?

#CozyWinterCabin #FireplaceAmbience #CozyCabin #WinterAmbience #AixWalker
"""
    tags = ["cozy winter cabin", "fireplace ambience 4k", "cozy cabin ambience", "winter cabin fireplace",
            "relaxing fireplace music", "snowfall ambience", "lofi jazz fireplace", f"{hrs.lower()} fireplace",
            "long fireplace video", "sleep music winter", "study music cozy", "aixwalker", "aix walker"]
    comment = f"❄️🔥 {hrs} by the fire – which chapter is your favourite? Drop the timestamp below 👇"
    community = (f"Neu: {name} – {hrs} Kaminfeuer, Schneefall und ruhige Musik in 4K 🔥❄️\n"
                 f"Perfekt zum Laufenlassen an einem langen Winterabend.")
    return {"title": title, "description": desc[:5000], "tags": tags, "comment": comment, "community_de": community}


def send_mail(res: dict) -> dict:
    from pipeline import mailer
    svc = mailer._service()
    to = config.REPORT_EMAIL or svc.users().getProfile(userId="me").execute()["emailAddress"]
    kind = "2-Wochen-Mix" if res["period"] == "biweekly" else "Monats-Mix"
    lines = [f"AIX WALKER Cozy Winter Cabin – {kind} ist online", "", f"Titel: {res['title']}",
             f"Video (ÖFFENTLICH): {res.get('video_url')}", f"Dauer: {res['duration_min']} Min · {res['tracks']} Tracks aus "
             f"{len(res['albums'])} Freitags-Mixen: {', '.join(res['albums'])}", f"Drive: {res.get('drive_folder', '-')}",
             f"Kosten: {res['cost_usd']:.2f} $ (neues Hauptbild + Kaminfilm-Clips in 4K, keine neue Musik)",
             "Kein DistroKid, keine Shorts.",
             f"Kommentar gepostet: {'ja' if res.get('comment_id') else 'nein'} – anpinnen in Studio: Kommentar → ⋮ → Anpinnen",
             "", "Community-Beitrag (Text zum Einfügen):", res["texts"]["community_de"], "", "Kapitel:", res["chapters"]]
    msg = EmailMessage()
    msg["To"], msg["From"] = to, "me"
    msg["Subject"] = f"AIX WALKER {kind} online: {res['name']} ({res['duration_min']} Min, 4K)"
    msg.set_content("\n".join(lines))
    mailer._attach_image(msg, Path(res["thumbnail"]))
    svc.users().messages().send(userId="me", body={"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}).execute()
    return {"sent": True, "to": to}


def synthetic(dst: Path) -> list[tuple[dict, dict]]:
    out = []
    for i in range(2):
        d = dst / f"fake{i}"
        d.mkdir(parents=True, exist_ok=True)
        tracks = []
        for t in range(3):
            p = d / f"{t + 1:02d} - Aix Walker - Fake {i}{t}.mp3"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                            f"sine=frequency={200 + 40 * (i * 3 + t)}:duration=40", "-ac", "2", str(p)], check=True)
            tracks.append(p)
        out.append(({"date": f"2026-10-0{i + 2}", "album": f"Fake Cabin {i}"},
                    {"tracks": tracks, "titles": [f"Fake {i}{t}" for t in range(3)], "minutes": 2.0}))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", required=True, choices=("biweekly", "monthly"))
    ap.add_argument("--month", default=None, help="Monats-Mix für YYYY-MM (Standard: Vormonat)")
    ap.add_argument("--if-due", action="store_true", help="2-Wochen-Mix nur, wenn der letzte ≥ 13 Tage her ist")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--private", action="store_true")
    ap.add_argument("--no-email", action="store_true")
    args = ap.parse_args()
    today = date.today()
    y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    month = args.month or f"{y}-{m:02d}"
    tag = month if args.period == "monthly" else today.isoformat()
    base = config.ROOT / "build" / f"cabin-{args.period}-{tag}"
    base.mkdir(parents=True, exist_ok=True)
    costs.start(base / "costs.json")

    if args.dry_run:
        mem = {"mixes": []}
        pairs = synthetic(base / "src")
        config.GOOGLE_API_KEY = ""
    else:
        from monthly_mix import fetch_mix
        from pipeline import drive
        mem = memory.load()
        done = [e for e in mem.get("cabin_compilations", []) if e.get("period") == args.period]
        if args.period == "monthly" and any(e.get("month") == month for e in done):
            log(f"Monats-Mix {month} existiert schon – nichts zu tun")
            return 0
        if args.period == "biweekly" and args.if_due:
            last = max((date.fromisoformat(e["date"]) for e in done), default=None)
            if last and (today - last).days < 13:
                log(f"2-Wochen-Mix nicht fällig (letzter am {last}) – nichts zu tun")
                return 0
        svc = drive.service()
        sources = pick_sources(args.period, cabin_folders(svc), mem, today, month)
        log(f"Freitags-Mixe: {[f['name'] for f in sources] or 'keine'}")
        if len(sources) < 2:
            log(f"ABBRUCH: nur {len(sources)} Freitags-Mix(e) – mindestens 2 nötig")
            return 2
        pairs = []
        for f in sources:
            log(f"lade {f['name']} …")
            mx = fetch_mix(svc, f, base / "src")
            order = sorted(range(len(mx["tracks"])), key=lambda i: Path(mx["tracks"][i]).name)
            mx["tracks"] = [mx["tracks"][i] for i in order]
            mx["titles"] = [mx["titles"][i] for i in order]
            pairs.append((f, mx))
        while len(pairs) > 2 and sum(mx["minutes"] for _, mx in pairs) * 60 > MAX_SEC:
            log(f"zu lang für YouTube (> 11:50 Std.) – ältesten Mix {pairs[0][0]['album']} weggelassen")
            pairs = pairs[1:]

    tracks = [t for _, mx in pairs for t in mx["tracks"]]
    titles = [t for _, mx in pairs for t in mx["titles"]]
    log(f"{len(tracks)} Tracks aus {len(pairs)} Mixen verbinden …")
    flac, starts = monthly.join_tracks(tracks, base / "mix.flac", xf=1.5)
    total_sec = audio.probe_duration(flac)
    total_min = int(round(total_sec / 60))
    if len(tracks) > 100:   # Beschreibung max. 5000 Zeichen → Kapitel je Freitags-Mix statt je Track
        idx, firsts = 0, []
        for p, mx in pairs:
            firsts.append((p["album"], starts[idx]))
            idx += len(mx["tracks"])
        chapter_text = metadata.chapters([a for a, _ in firsts], [s for _, s in firsts])
    else:
        chapter_text = metadata.chapters(titles, starts)
    final = loopvideo.mix_with_crackle(flac, CRACKLE, base / "final.flac")
    flac.unlink(missing_ok=True)
    (base / "work").mkdir(exist_ok=True)
    aac = loopvideo.encode_audio(final, base / "work" / "audio.m4a")
    final.unlink(missing_ok=True)

    if args.period == "monthly":
        name = f"{monthly.MONTHS[int(month[5:]) - 1]} by the Fire"
    else:
        used = {e.get("name", "").lower() for e in mem.get("cabin_compilations", [])}
        free = [n for n in NAMES["biweekly"] if n.lower() not in used] or NAMES["biweekly"]
        name = free[0]

    # Neues Hauptbild + Clips (wie Freitags-Mix)
    (base / "img").mkdir(exist_ok=True)
    frame_png = base / "img" / "frame_4k.png"   # gleiche Ablage wie run_cabin (Clips im Dry-Run nutzen sie)
    if frame_png.exists():
        from PIL import Image
        frame = Image.open(frame_png).convert("RGB")
    else:
        art = images.procedural_art("16:9") if args.dry_run else images.generate_art(
            scene_prompt(mem, today.toordinal()), "16:9", pro=True, style=images.style_for(GENRE), image_size="4K")
        frame = cabin_art.fire_right(loopvideo.frame_16x9(art))   # Kamin immer rechts, Text oben links
        frame.save(frame_png)
        frame.save(base / "master.jpg", "JPEG", quality=92)
    import run_cabin
    clips = run_cabin.make_clips(frame, base, config.LINE_FORMAT[GENRE]["veo_clips"], args.dry_run)
    playlist_file = loopvideo.prepare_video(clips, total_sec, base / "work", log=log)
    thumb = cabin_art.make_thumbnail(frame, images.duration_label(total_min), base / "thumbnail.jpg")

    playlist_id = "PLAYLIST"
    if not args.dry_run:
        from pipeline import youtube
        playlist_id = youtube.playlist_for("cabin")
    albums = [{"album": p["album"], "video_id": next((e.get("video_id") for e in mem.get("mixes", [])
                                                      if e.get("album", "").lower() == p["album"].lower()), None)}
              for p, _ in pairs]
    t = texts(args.period, name, total_min, albums, chapter_text, playlist_id)
    (base / "metadata.txt").write_text(
        f"=== YOUTUBE TITEL ===\n{t['title']}\n\n=== BESCHREIBUNG ===\n{t['description']}\n=== TAGS ===\n"
        f"{', '.join(t['tags'])}\n\n=== PINNED COMMENT ===\n{t['comment']}\n\n=== COMMUNITY-BEITRAG ===\n"
        f"{t['community_de']}\n", encoding="utf-8")
    res = {"period": args.period, "month": month if args.period == "monthly" else None, "name": name,
           "title": t["title"], "duration_min": total_min, "albums": [p["album"] for p, _ in pairs],
           "tracks": len(tracks), "thumbnail": str(thumb), "chapters": chapter_text, "video_id": None,
           "video_url": None, "comment_id": None, "texts": t}

    if args.dry_run:
        mp4 = base / "video.mp4"
        subprocess.run(loopvideo.mux_command(playlist_file, aac, str(mp4)), check=True)
        res["cost_usd"] = costs.total_usd()
        (base / "summary.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        log(f"Dry-Run fertig: {total_min} Min, {mp4} ({mp4.stat().st_size / 1e6:.0f} MB)")
        return 0

    from pipeline import drive, streamupload, youtube
    privacy = "private" if args.private else "public"
    streamupload.remove_incomplete(t["title"], log=log)   # Reste eines abgebrochenen Laufs
    log(f"Streaming-Upload {total_min} Min 4K ({privacy}) …")
    up = streamupload.upload_stream(loopvideo.mux_command(playlist_file, aac), t["title"], t["description"], t["tags"],
                                    privacy=privacy, log=log)
    vid = up["video_id"]
    res["video_id"], res["video_url"] = vid, f"https://youtu.be/{vid}"
    log(f"Hochgeladen: {res['video_url']} ({up['bytes'] / 1e9:.1f} GB in {up['seconds'] / 60:.0f} Min)")
    for step, fn in (("Thumbnail", lambda: youtube.set_thumbnail(vid, thumb)),
                     ("Playlist", lambda: youtube.add_to_playlist(vid, playlist_id))):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            log(f"{step} fehlgeschlagen: {e}")
    if not args.private:
        try:
            res["comment_id"] = youtube.post_comment(vid, t["comment"])
        except Exception as e:  # noqa: BLE001
            log(f"Kommentar fehlgeschlagen: {e}")
    kind = "2-WOCHEN" if args.period == "biweekly" else "MONTHLY"
    # Ordnername passt bewusst NICHT zum Muster der Freitags-Mixe → wird nie selbst wieder zusammengeschnitten
    links = drive.upload_mix_package(f"{today.isoformat()} – {kind} {GENRE} – {name} ({total_min} Min, 4K)",
                                     [thumb, base / "master.jpg", base / "metadata.txt"], {"loop_clips": clips})
    res["drive_folder"] = links.get("_folder")
    res["cost_usd"] = costs.total_usd()
    mem.setdefault("cabin_compilations", []).append(
        {"period": args.period, "date": today.isoformat(), "month": res["month"], "name": name, "video_id": vid,
         "title": t["title"], "duration_min": total_min, "albums": res["albums"], "drive": res["drive_folder"],
         "cost_usd": res["cost_usd"]})
    memory.save(mem)
    if not args.no_email:
        try:
            log(f"Mail: {send_mail(res)}")
        except Exception as e:  # noqa: BLE001
            log(f"Mail fehlgeschlagen: {e}")
    (base / "summary.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(base / "src", ignore_errors=True)
    log("fertig")
    return 0


if __name__ == "__main__":
    sys.exit(main())
