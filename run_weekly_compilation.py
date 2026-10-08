#!/usr/bin/env python3
"""Samstags-Lang-Mix einer eigenen Linie (Rolf, 08.10.2026): die Mixe der laufenden Woche (Italien: Mo, Mi, Fr) werden
aus Google Drive geladen und zu EINEM ca. 3-Stunden-Mix zusammengeschnitten – Überblendungen, Kapitel, Video mit
atmendem Licht aus den Album-Covern der Tages-Mixe. Neu erzeugt wird nur EIN Hauptbild für Album-Cover und Thumbnail
(Nano Banana, ca. 0,24 $). Keine Lyria-Kosten, kein DistroKid, keine Shorts (die Tages-Mixe haben schon Shorts; doppelte
Clips würde YouTube als wiederverwendeten Inhalt werten).

  python run_weekly_compilation.py --genre "Italian Chillout"            # öffentlich, alles automatisch
  python run_weekly_compilation.py --genre "Italian Chillout" --dry-run  # synthetisch, kein Drive/YouTube/Mail
  python run_weekly_compilation.py --genre "Italian Chillout" --private
"""
import argparse
import base64
import json
import random
import shutil
import sys
import time
from datetime import date, timedelta
from email.message import EmailMessage
from pathlib import Path

from PIL import Image

from monthly_mix import collect_folders, fetch_mix, synthetic
from pipeline import audio, config, drive, images, memory, metadata, monthly, planner

DAYS_BACK = 6          # Samstag → Sonntag davor bis Freitag; Italien: Mo, Mi, Fr (der So-Mix gehört zur Vorwoche)
MIN_MIXES = 2

# Name des Wochenend-Releases (steht in Schreibschrift auf Cover/Thumbnail und vorne im Titel); rotiert, keine Dopplung
WEEKEND_NAMES = {
    "Italian Chillout": ["Sabato Sera", "Weekend in Positano", "Lake Como Weekend", "Amalfi Nights", "Dolce Weekend",
                         "Una Notte a Como", "Riviera Saturday", "Ravello Evenings", "Weekend al Lago", "Notte d'Estate",
                         "Golden Coast Weekend", "Bellagio Nights", "Amalfi Aperitivo", "Sera Italiana"],
}
SUBTITLE = {"Italian Chillout": "Amalfi Coast & Lake Como Dinner Lounge"}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] [weekly] {msg}", flush=True)


def pick_name(genre: str, mem: dict) -> str:
    used = {str(e.get("name", "")).lower() for e in mem.get("weekly", [])} | memory.used_albums(mem)
    names = WEEKEND_NAMES.get(genre) or [f"{genre} Weekend"]
    free = [n for n in names if n.lower() not in used]
    if free:
        return free[0]
    return f"{names[date.today().isocalendar()[1] % len(names)]} {date.today().isocalendar()[1]}"


def make_texts(genre: str, name: str, total_min: int, albums: list[dict], chapter_text: str, bpm_range: str,
               playlist_id: str) -> dict:
    head, _, tags, playlist = monthly.genre_info(genre)
    keyword = config.THUMB_KEYWORD.get(genre, head)
    hrs = metadata.hours_wording(total_min)
    sub = SUBTITLE.get(genre, "Weekend Mix")
    title = f"{name} · {keyword} · {hrs} · {sub}"
    if len(title) > 100:
        title = f"{name} · {keyword} · {hrs} Weekend Mix"
    mixes = "\n".join(f"• {a['album']}" + (f" – https://youtu.be/{a['video_id']}" if a.get("video_id") else "")
                      for a in albums)
    desc = f"""🎧 {hrs} of calm {keyword.lower()} – the whole week in one uninterrupted weekend mix.

Sunset aperitivo on the Amalfi Coast, a candlelit dinner on Lake Como: {len(albums)} mixes of this week, blended with
smooth crossfades. No vocals, no ads in between – perfect for dinner, reading, cooking or a slow evening.

⏱️ CHAPTERS
{chapter_text}

📀 FROM THIS WEEK'S MIXES
{mixes}

🔊 {bpm_range} BPM · no vocals · mastered for headphones and speakers
🎵 All tracks produced by {config.ARTIST} (AI-assisted, original music)
▶️ Full playlist: https://www.youtube.com/playlist?list={playlist_id}
🔔 New Italian chillout mixes every Monday, Wednesday, Friday and Sunday, a long weekend mix every Saturday – subscribe!

👇 Where would you listen to this – Amalfi Coast or Lake Como?

#{keyword.replace(' ', '')} #ItalianLounge #AmalfiCoast #LakeComo #{config.ARTIST.replace(' ', '')}
"""
    tags = list(dict.fromkeys(tags + ["weekend mix", f"{hrs.lower()} mix", "long mix", "dinner music",
                                      "aix walker", "no vocals"]))[:15]
    comment = "🍋 Weekend mix is here! Which chapter is your favourite? Drop the timestamp below 👇"
    community = (f"Weekend mix is live: {name} – {hrs} of {keyword.lower()} 🍷\nThe whole week in one long, calm mix – "
                 f"perfect for a slow Saturday evening. Amalfi or Como – where are you listening?")
    return {"title": title[:100], "description": desc[:5000], "tags": tags, "comment": comment,
            "community_de": community, "playlist": playlist, "keyword": keyword}


def master_scene(genre: str, mem: dict, seed: int) -> str:
    g = planner.GENRES.get(genre, {})
    rnd = random.Random(seed)
    recent = {str((m.get("visual") or {}).get("motif_family", "")).lower() for m in mem.get("mixes", [])[-6:]}
    motifs = [m for m in g.get("motifs", []) if m.lower() not in recent] or g.get("motifs", ["elegant evening scene"])
    light = rnd.choice(planner.LIGHTS.get(genre, ["golden hour"]))
    rule = g.get("visual_rule", "")
    return f"{rnd.choice(motifs)}, {light}. {rule}"


def send_mail(res: dict) -> dict:
    from pipeline import mailer
    svc = mailer._service()
    to = config.REPORT_EMAIL or svc.users().getProfile(userId="me").execute()["emailAddress"]
    t = res.get("texts", {})
    lines = [f"AIX WALKER Samstags-Mix ({res['genre']}) ist online", "",
             f"Titel: {res['title']}", f"Video: {res.get('video_url')}", f"Dauer: {res['duration_min']} Min · "
             f"{res['tracks']} Tracks aus {len(res['albums'])} Mixen: {', '.join(res['albums'])}",
             f"Drive: {res.get('drive_folder', '-')}",
             f"Kosten: ca. {res['cost_usd']:.2f} $ (nur Hauptbild, keine Musik-Erzeugung)",
             "Kein DistroKid-Release (Zusammenschnitt). Keine Shorts (Tages-Mixe haben schon Shorts).",
             f"Kommentar gepostet: {'ja' if res.get('comment_id') else 'nein'} – anpinnen in Studio: Kommentar → ⋮ → Anpinnen",
             "", "Community-Beitrag (Text zum Einfügen):", t.get("community_de", ""), "", "Kapitel:", res["chapters"]]
    msg = EmailMessage()
    msg["To"], msg["From"] = to, "me"
    msg["Subject"] = f"AIX WALKER Samstags-Mix online: {res['name']} ({res['duration_min']} Min)"
    msg.set_content("\n".join(lines))
    for p in (res.get("thumbnail"), res.get("cover")):
        if p and Path(p).exists():
            mailer._attach_image(msg, Path(p))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"sent": True, "to": to}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--genre", required=True, choices=sorted(planner.ROTATION_EXCLUDE))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--private", action="store_true")
    ap.add_argument("--no-email", action="store_true")
    args = ap.parse_args()
    genre = args.genre
    today = date.today()
    week = f"{today.isocalendar()[0]}-W{today.isocalendar()[1]:02d}"
    base = config.ROOT / "build" / f"weekly-{week}-{genre.replace(' ', '_')}"
    shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        mem = {"mixes": []}
        pairs = [({**p, "genre": genre}, mx) for p, mx in synthetic(base / "src")]
        config.GOOGLE_API_KEY = ""
    else:
        for v in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN", "DRIVE_REFRESH_TOKEN"):
            config.require(v)
        mem = memory.load()
        if any(e.get("week") == week and e.get("genre") == genre for e in mem.get("weekly", [])):
            log(f"Samstags-Mix {week} {genre} existiert schon – nichts zu tun")
            return 0
        svc = drive.service()
        lo = (today - timedelta(days=DAYS_BACK)).isoformat()
        folders = sorted([f for f in collect_folders(svc) if f["genre"] == genre and lo <= f["date"] < today.isoformat()],
                         key=lambda f: f["date"])
        log(f"Mixe dieser Woche: {[f['name'] for f in folders] or 'keine'}")
        if len(folders) < MIN_MIXES:
            log(f"ABBRUCH: nur {len(folders)} Mix(e) diese Woche – mindestens {MIN_MIXES} nötig")
            return 2
        pairs = []
        for f in folders:
            log(f"lade {f['name']} …")
            mx = fetch_mix(svc, f, base / "src")
            order = sorted(range(len(mx["tracks"])), key=lambda i: Path(mx["tracks"][i]).name)
            mx["tracks"] = [mx["tracks"][i] for i in order]
            mx["titles"] = [mx["titles"][i] for i in order]
            pairs.append((f, mx))

    tracks = [t for _, mx in pairs for t in mx["tracks"]]
    titles = [t for _, mx in pairs for t in mx["titles"]]
    log(f"{len(tracks)} Tracks aus {len(pairs)} Mixen verbinden …")
    flac, starts = monthly.join_tracks(tracks, base / "weekly.flac")
    total_sec = audio.probe_duration(flac)
    total_min = int(round(total_sec / 60))
    chapter_text = metadata.chapters(titles, starts)
    bpms = [int(p["bpm"]) for p, _ in pairs]
    bpm_range = f"{min(bpms)}" if min(bpms) == max(bpms) else f"{min(bpms)}–{max(bpms)}"
    name = pick_name(genre, mem)

    playlist_key = planner.GENRES[genre]["playlist"]
    if args.dry_run:
        playlist_id = config.PLAYLISTS.get(playlist_key) or config.PLAYLISTS["chillout"]
    else:
        from pipeline import youtube
        playlist_id = youtube.playlist_for(playlist_key)
    albums = [{"album": p["album"], "video_id": next((e.get("video_id") for e in mem.get("mixes", [])
                                                      if e.get("album", "").lower() == p["album"].lower()), None)}
              for p, _ in pairs]
    texts = make_texts(genre, name, total_min, albums, chapter_text, bpm_range, playlist_id)

    # EIN Hauptbild → Album-Cover (ganz) + Thumbnail (16:9-Ausschnitt), große Schrift wie die Tages-Mixe der Linie
    cost = 0.0
    if args.dry_run:
        master = images.procedural_art("1:1", seed=7)
    else:
        try:
            master = images.master_art(master_scene(genre, mem, today.toordinal()), genre)
            cost = config.PRICES_USD.get("image_pro_4k", config.PRICES_USD["image_pro"])
        except Exception as e:  # noqa: BLE001
            log(f"Hauptbild fehlgeschlagen ({str(e)[:160]}) – Cover des letzten Mixes als Ersatz")
            master = Image.open(pairs[-1][1]["cover"]).convert("RGB")
    master.save(base / "master.jpg", "JPEG", quality=92)
    scale = config.THUMB_TEXT_SCALE.get(genre, 1.0)
    cover = images.make_album_cover(master, texts["keyword"], name, base / "album_3000.png", text_scale=scale)
    thumb = images.make_thumbnail(images.crop_aspect(master, 16, 9), texts["keyword"], name, base / "thumbnail.jpg",
                                  duration=images.duration_label(total_min), text_scale=scale)

    log("Video rendern (atmendes Licht) …")
    mp4 = base / "weekly.mp4"
    try:
        monthly.build_animated_video(pairs, flac, starts, mp4)
    except Exception as e:  # noqa: BLE001
        log(f"Animiertes Video fehlgeschlagen ({str(e)[:160]}) – Standbild")
        frame = base / "frame.png"
        images.make_video_frame(cover, frame)
        monthly.build_still_video(frame, flac, mp4)
    flac.unlink(missing_ok=True)

    res = {"genre": genre, "week": week, "name": name, "title": texts["title"], "duration_min": total_min,
           "albums": [p["album"] for p, _ in pairs], "tracks": len(tracks), "thumbnail": str(thumb), "cover": str(cover),
           "mp4": str(mp4), "chapters": chapter_text, "video_id": None, "video_url": None, "comment_id": None,
           "cost_usd": cost, "texts": texts}
    (base / "metadata.txt").write_text(
        f"=== YOUTUBE TITEL ===\n{texts['title']}\n\n=== BESCHREIBUNG ===\n{texts['description']}\n=== TAGS ===\n"
        f"{', '.join(texts['tags'])}\n\n=== PINNED COMMENT ===\n{texts['comment']}\n\n=== COMMUNITY-BEITRAG ===\n"
        f"{texts['community_de']}\n", encoding="utf-8")
    if args.dry_run:
        (base / "summary.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        log(f"Dry-Run fertig: {total_min} Min, {mp4}")
        return 0

    from pipeline import youtube
    vid = youtube.upload_video(mp4, texts["title"], texts["description"], texts["tags"],
                               privacy="private" if args.private else "public")
    res["video_id"], res["video_url"] = vid, f"https://youtu.be/{vid}"
    log(f"Hochgeladen: {res['video_url']}")
    for step, fn in (("Thumbnail", lambda: youtube.set_thumbnail(vid, thumb)),
                     ("Playlist", lambda: youtube.add_to_playlist(vid, playlist_id))):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            log(f"{step} fehlgeschlagen: {e}")
    if not args.private:
        try:
            res["comment_id"] = youtube.post_comment(vid, texts["comment"])
        except Exception as e:  # noqa: BLE001
            log(f"Kommentar fehlgeschlagen: {e}")
    # Ordnername passt bewusst NICHT zum Tages-Mix-Muster → der Monats-Mix nimmt nur die Tages-Mixe, keine Dopplung
    links = drive.upload_mix_package(f"{today.isoformat()} – WEEKEND {genre} – {name} ({total_min} Min)",
                                     [thumb, cover, base / "metadata.txt", mp4])
    res["drive_folder"] = links.get("_folder")
    mem.setdefault("weekly", []).append({"week": week, "genre": genre, "name": name, "video_id": vid,
                                         "title": texts["title"], "duration_min": total_min, "albums": res["albums"],
                                         "drive": res["drive_folder"], "date": today.isoformat()})
    memory.save(mem)
    if not args.no_email:
        try:
            log(f"Mail: {send_mail(res)}")
        except Exception as e:  # noqa: BLE001
            log(f"Mail fehlgeschlagen: {e}")
    (base / "summary.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    log("fertig")
    return 0


if __name__ == "__main__":
    sys.exit(main())
