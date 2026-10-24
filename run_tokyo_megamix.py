"""Tokyo-Mega-Mix (Rolf 24.10.2026): bis 8 Std. aus den vorhandenen Tokyo-Mixen (Drive), Zufallsreihenfolge, kein Song doppelt,
KEINE neue Musik, KEIN neues Bild (Hauptbild des neuesten Tokyo-Mixes). Sofort loslaufen, PRIVAT hochladen (kein Warten, keine Planung),
dazu 1 Short (privat), beschriftetes Album-Cover, Community-Text, Mail. Kosten: nur die Bildprüfung (Cent-Bereich).

  python run_tokyo_megamix.py            # echter Lauf (Umgebung „AixWalker“ mit Zugangsdaten)
  python run_tokyo_megamix.py --dry-run  # ohne Drive/YouTube, mit künstlichen Songs
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import date
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pipeline import audio, config, costs, images, megamix, memory, metadata, monthly  # noqa: E402
import run_megamix as rm  # noqa: E402
import run_tokyo as rt  # noqa: E402

GENRE = "Tokyo Work Lounge"
NAME = "Tokyo Work Lounge"
KEYWORD = "Slow Jazz"
DEFAULT_QUOTE = "Let the room find its rhythm.|One more commit, one more calm breath.|My tracks will keep you company."


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] [tokyo-megamix] {msg}", flush=True)


def community(url: str) -> str:
    return (f"🎷🌃 AIX WALKER · Tokyo Work Lounge Mega-Mix\n\nSlow jazz for deep work and coding: quiet Tokyo evenings, a warm desk lamp "
            f"and one steady groove after another. 💛\n\nPress play, settle in and let the music carry your focus. 🎧\n\n▶️ {url}\n\n"
            f"#AixWalker #TokyoWorkLounge #SlowJazz #DeepWork #CodingMusic")


def texts(total_min: int, albums: list[str], chapters: str, bpm: str, playlist_id: str) -> dict:
    hrs = metadata.hours_wording(total_min)
    title = f"{NAME} · {KEYWORD} for Deep Work & Coding · {hrs} Long Mix"[:100]
    src = "\n".join(f"• {a}" for a in albums)
    desc = f"""🎷 {hrs} of slow jazz for deep work and coding – one long, uninterrupted mix, shuffled from {len(albums)} Tokyo Work Lounge mixes.

Quiet Tokyo evenings, a warm desk lamp and a steady, soft groove: every song plays only once, blended with smooth crossfades. No vocals, no ads in between – perfect for coding, studying, writing or a slow focused evening.

⏱️ CHAPTERS
{chapters}

📀 SHUFFLED FROM THESE MIXES
{src}

🔊 {bpm} BPM · no vocals · mastered for headphones and speakers
🎵 All tracks produced by {config.ARTIST} (AI-assisted, original music)
▶️ Full playlist: https://www.youtube.com/playlist?list={playlist_id}
🔔 New mixes regularly – subscribe and hit the bell!

👇 What are you working on today?

{rt.HASHTAGS}
"""
    tags = list(dict.fromkeys(rt.TAGS + ["long mix", f"{hrs.lower()} mix", "shuffled mix", "slow jazz", "aix walker", "no vocals"]))[:15]
    comment = "🎷 The long mix is live! What are you working on today? Full tracklist with timestamps below 👇"
    return {"title": title, "description": desc[:5000], "tags": tags, "comment": comment, "community_de": community("{URL}"),
            "keyword": KEYWORD, "playlist": playlist_id}


def tokyo_sources(svc, max_hours: float) -> list[dict]:
    from monthly_mix import collect_folders
    fol = [f for f in collect_folders(svc) if "Tokyo Work Lounge" in f["name"]]
    fol.sort(key=lambda f: f["date"], reverse=True)
    out, have = [], 0.0
    for f in fol:
        out.append(f)
        have += 66
        if have >= max_hours * 60 * 1.3:
            break
    return sorted(out, key=lambda f: f["date"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-hours", type=float, default=megamix.MAX_HOURS)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--no-short", action="store_true")
    ap.add_argument("--quote-text", default=DEFAULT_QUOTE)
    ap.add_argument("--desk-x", type=float, default=0.0, help="Schreibtischmitte 0–1; 0 = automatisch messen")
    args = ap.parse_args()
    today = date.today()
    base = HERE / "build" / f"tokyo-megamix-{today.isoformat()}"
    shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True)
    costs.start(base / "costs.json")
    dry = args.dry_run
    lines = rt.parse_quote(args.quote_text, allow_used=dry)

    svc, mem = None, {}
    if not dry:
        from pipeline import drive
        for v in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN", "DRIVE_REFRESH_TOKEN"):
            config.require(v)
        mem = memory.load()
        svc = drive.service()
        if any(e.get("date") == today.isoformat() for e in mem.get("tokyo_megamix", [])):
            log("Tokyo-Mega-Mix von heute existiert schon – nichts zu tun")
            return 0

    # 1) Quellen, mischen
    if dry:
        pairs = rm.synthetic(base / "src", GENRE)
        sources = []
    else:
        sources = tokyo_sources(svc, args.max_hours)
        log(f"Quell-Mixe: {[f['name'] for f in sources] or 'keine'}")
        if len(sources) < 3:
            log("ABBRUCH: weniger als 3 Tokyo-Mixe – nichts zu tun")
            return 2
        pairs = rm.fetch_all(svc, sources, base / "src")
    order = rm.build_order(pairs, seed=today.toordinal() * 31 + 7, max_hours=args.max_hours)
    if megamix.total_seconds(order) < (60 * 60 if not dry else 60):
        log("ABBRUCH: zu wenig Material")
        return 2
    titles = [t["title"] for t in order]
    flac, starts = monthly.join_tracks([t["path"] for t in order], base / "mix.flac", xf=megamix.XFADE)
    total_min = int(round(audio.probe_duration(flac) / 60))
    chapters = megamix.chapter_text(titles, starts)
    comments = megamix.tracklist_comments(titles, starts)
    albums_used = list(dict.fromkeys(t["album"] for t in order))
    bpms = [int(p["bpm"]) for p, _ in pairs if p.get("bpm")] or [70]
    bpm = f"{min(bpms)}" if min(bpms) == max(bpms) else f"{min(bpms)}–{max(bpms)}"
    log(f"{total_min} Min, {len(order)} Songs aus {len(albums_used)} Mixen")

    # 2) Hauptbild des neuesten Tokyo-Mixes (Drive: master.jpg), Cover, Thumbnail
    if dry:
        art = images.procedural_art("16:9", seed=5).convert("RGB").resize((3840, 2160))
        playlist_id = "PLAYLIST"
    else:
        from pipeline import youtube
        playlist_id = youtube.ensure_playlist(*rt.PLAYLIST)
        art = None
        for f in reversed(sources):
            kids = drive.list_children(svc, f["id"])
            m = next((k for k in kids if k["name"] == "master.jpg"), None)
            if m:
                art = Image.open(drive.download(svc, m["id"], base / "master_src.jpg")).convert("RGB")
                log(f"Hauptbild: master.jpg aus „{f['name']}“ ({art.size[0]}×{art.size[1]})")
                break
        if art is None:
            log("ABBRUCH: kein master.jpg in den Tokyo-Ordnern")
            return 2
        art = images._cover_crop(art, 3840, 2160) if art.size != (3840, 2160) else art
    art.save(base / "master.jpg", "JPEG", quality=92)
    desk_x, person_x = args.desk_x or None, None
    if desk_x is None and not dry:
        chk = rt.check_room_image(art, None) or {}
        dx, px = chk.get("desk_x"), chk.get("person_x")
        desk_x = float(dx) if isinstance(dx, (int, float)) and 0.05 <= float(dx) <= 0.95 else None
        person_x = float(px) if isinstance(px, (int, float)) and 0.0 <= float(px) <= 1.0 else None
    desk_x = desk_x or 0.70
    log(f"Schreibtischmitte {desk_x:.2f}, Person {person_x}")
    t = texts(total_min, albums_used, chapters, bpm, playlist_id)
    cover_img = rt.make_album_cover(art, desk_x, 3000)
    cover_img.save(base / "album_3000.png", optimize=True)
    thumb = images.make_thumbnail(images.crop_aspect(art, 16, 9), KEYWORD, NAME, base / "thumbnail.jpg",
                                  duration=images.duration_label(total_min), text_scale=config.THUMB_TEXT_SCALE.get("Slow Jazz", 1.0))
    frame = base / "frame.png"
    art.resize((1920, 1080), Image.LANCZOS).save(frame)
    mp4 = monthly.build_still_video(frame, flac, base / "megamix.mp4")
    log(f"Video fertig: {mp4} ({mp4.stat().st_size / 1e6:.0f} MB)")
    (base / "metadata.txt").write_text(
        f"=== YOUTUBE TITEL ===\n{t['title']}\n\n=== BESCHREIBUNG ===\n{t['description']}\n=== TAGS ===\n{', '.join(t['tags'])}\n\n"
        f"=== ANGEPINNTER KOMMENTAR ===\n{t['comment']}\n\n=== TRACKLISTE (Kommentar) ===\n{chr(10).join(comments)}\n\n"
        f"=== COMMUNITY-BEITRAG ===\n{t['community_de'].replace('{URL}', '(Video-Link)')}\n", encoding="utf-8")
    res = {"genre": GENRE, "week": None, "name": NAME, "title": t["title"], "duration_min": total_min, "albums": albums_used,
           "tracks": len(order), "thumbnail": str(thumb), "cover": str(base / "album_3000.png"), "chapters": chapters,
           "video_id": None, "video_url": None, "comment_ids": [], "texts": t, "estimate_usd": 0.0, "publish_at": None,
           "publish_local": "privat", "private": True, "shorts": []}
    if dry:
        res["cost_usd"] = 0.0
        (base / "summary.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        log(f"Dry-Run fertig: {total_min} Min, {len(order)} Songs, Kapitel {len(chapters.splitlines())}, Community-Text:\n"
            + t["community_de"].replace("{URL}", "https://youtu.be/DRYRUN"))
        return 0

    # 3) Hochladen: SOFORT, PRIVAT (Rolf 24.10.2026), Thumbnail, Playlist
    from pipeline import drive, youtube
    vid = youtube.upload_video(mp4, t["title"], t["description"], t["tags"], privacy="private", location=youtube.TOKYO)
    res["video_id"], res["video_url"] = vid, f"https://youtu.be/{vid}"
    log(f"Hochgeladen (privat): {res['video_url']}")
    for step, fn in (("Thumbnail", lambda: youtube.set_thumbnail(vid, thumb)),
                     ("Playlist", lambda: youtube.add_to_playlist(vid, playlist_id))):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            log(f"{step} fehlgeschlagen: {e}")

    # 4) Short (privat; Mix-Link + öffentlich schaltet später die Abendaufgabe bzw. Rolf)
    short_id, s_title = None, None
    if not args.no_short:
        try:
            wav = rm.excerpt(flac, audio.probe_duration(flac) * 0.3, base / "short_audio.wav", sec=90)
            short, chk = rt.make_short_checked(art, lines, wav, 5, base / "short", rt.short_center(desk_x, person_x), person_x=person_x)
            s_title, s_desc, s_tags = rt.short_texts(lines, res["video_url"])
            short_id = youtube.upload_video(short, s_title, s_desc, s_tags, privacy="private", location=youtube.TOKYO)
            res["shorts"] = [{"date": today.isoformat(), "title": s_title, "url": f"https://youtube.com/shorts/{short_id}",
                              "check": chk}]
            log(f"Short hochgeladen (privat): https://youtube.com/shorts/{short_id}")
        except Exception as e:  # noqa: BLE001
            log(f"Short fehlgeschlagen: {str(e)[:200]}")
            res["shorts"] = [{"date": today.isoformat(), "title": "(Short fehlgeschlagen)", "error": str(e)[:200]}]

    # 5) Drive, Gedächtnis (eigene Liste „tokyo_megamix“, damit die Samstags-Rotation unberührt bleibt)
    links = drive.upload_mix_package(f"{today.isoformat()} – MEGAMIX {GENRE} – {NAME} ({total_min} Min)",
                                     [thumb, base / "master.jpg", base / "metadata.txt", base / "album_3000.png"])
    res["drive_folder"] = links.get("_folder")
    res["cost_usd"] = costs.total_usd()
    mem = memory.load()
    mem.setdefault("tokyo_megamix", []).append({"date": today.isoformat(), "video_id": vid, "short_id": short_id, "title": t["title"],
                                                "duration_min": total_min, "albums": albums_used, "tracks": len(order),
                                                "drive": res["drive_folder"], "cost_usd": res["cost_usd"]})
    if short_id:
        mem.setdefault("shorts2", []).append({"date": today.isoformat(), "id": f"tokyo-mega-{today.isoformat()}", "title": s_title,
                                              "video_id": short_id, "mix_video_id": vid, "cost_usd": 0.0, "tokyo": True})
    memory.save(mem)
    if not args.no_email:
        try:
            log(f"Mail: {rm.send_mail(res)}")
        except Exception as e:  # noqa: BLE001
            log(f"Mail fehlgeschlagen: {e}")
    (base / "summary.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    log("fertig")
    return 0


if __name__ == "__main__":
    sys.exit(main())
