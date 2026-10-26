"""Tokyo-Sonntags-Mega-Mix (Rolf 24.10.2026, komplett neues Konzept, läuft AUTARK):
  * bis zu 8 Std. aus den vorhandenen Tokyo-Mixen (Drive), Zufallsreihenfolge, KEIN Song doppelt (Duplikat = identische Audiodatei;
    die Titel wiederholen sich bei Tokyo-Mixen absichtlich -> Titel-Vergleich AUS, sonst bleibt nur 1 Std. übrig!), keine neue Musik
  * NEUER Raum + NEUES Bild (wie bei den Tokyo-Mixen, Variation/Prüfung/Easter-Egg), NEUER Spruch zum Videostart, Beschreibung mit Amazon-Links
  * Video wie die normalen Tokyo-Mixe (Spruch-Intro, Blenden bei Songwechseln), SOFORT ÖFFENTLICH, Short (öffentlich), Tracklisten-Kommentar,
    Album-Cover (beschriftet) + Thumbnail, Drive-Paket, EINE Mail an Rolf (Community-Text, Cover, Infos)

Claude (die geplante Aufgabe) denkt sich pro Lauf NEU aus: Raum (Szene), Spruch, Beschreibung, Community-Text und ruft dann auf:
  python run_tokyo_megamix.py --room <kennung> --scene-file <datei> --desk-side left|right --person auto \\
       --quote-text "Z1|Z2|Z3" --description-file <datei> --community-file <datei>
Test ohne Kosten: --dry-run
Exit-Codes: 0 ok · 2 zu wenig Material · 3 kein brauchbares Bild · 6 heute schon gelaufen
"""
from __future__ import annotations

import argparse
import base64
import json
import shutil
import sys
import time
from datetime import date
from email.message import EmailMessage
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
MIN_HOURS = 4.0          # darunter ist es kein Mega-Mix: abbrechen und Rolf mailen


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] [tokyo-megamix] {msg}", flush=True)


def mail_problem(subject: str, body: str) -> None:
    try:
        from pipeline import mailer
        svc = mailer._service()
        to = config.REPORT_EMAIL or svc.users().getProfile(userId="me").execute()["emailAddress"]
        msg = EmailMessage()
        msg["To"], msg["From"], msg["Subject"] = to, "me", subject
        msg.set_content(body)
        svc.users().messages().send(userId="me", body={"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}).execute()
    except Exception as e:  # noqa: BLE001
        log(f"Problem-Mail fehlgeschlagen: {e}")


def tokyo_sources(svc) -> list[dict]:
    """Alle Tokyo-Mix-Ordner (Genre-Test-Ordner und frühere Mega-Mixe fallen durch das Namensmuster heraus)."""
    from monthly_mix import collect_folders
    fol = [f for f in collect_folders(svc) if "Tokyo Work Lounge" in f["name"] and "MEGAMIX" not in f["name"]]
    return sorted(fol, key=lambda f: f["date"])


def texts(total_min: int, chapters: str, intro: str, var: dict, playlist_id: str, comment_intro: str) -> dict:
    hrs = metadata.hours_wording(total_min)
    title = f"🎧 Tokyo Work Lounge | Slow Jazz for Deep Work & Coding - {hrs} Long Mix🎷"[:100]
    desc = rt.description(chapters, total_min, intro, var, date.today().toordinal())
    desc = desc.replace("Chapters\n", f"▶️ Full playlist: https://www.youtube.com/playlist?list={playlist_id}\n\nChapters\n", 1)[:5000]
    tags = list(dict.fromkeys(rt.TAGS + ["long mix", "tokyo work lounge mega mix", "shuffled mix", "no vocals"]))[:15]
    return {"title": title, "description": desc, "tags": tags, "comment": comment_intro, "hrs": hrs}


def spread_and_label(order: list[dict], gap: int = 12) -> list[dict]:
    """Die 22 Songtitel kommen in JEDEM Tokyo-Mix vor (verschiedene Songs, gleiche Namen). Damit es nicht wie Wiederholung wirkt:
    1) gleicher Titel frühestens nach `gap` anderen Songs, 2) Titel bekommt den Raum des Quell-Mixes angehängt (z. B. „Soft Compile · Kichijoji“)."""
    import re
    rest, out = list(order), []
    while rest:
        recent = {x["title"] for x in out[-gap:]}
        i = next((k for k, t in enumerate(rest) if t["title"] not in recent), 0)
        out.append(rest.pop(i))
    for t in out:
        m = re.search(r"Tokyo Work Lounge\s*[–-]\s*([a-z]+)", str(t.get("album", "")))
        if m:
            t["title"] = f"{t['title']} · {m.group(1).capitalize()}"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", default="", help="neue Raumkennung (nicht in Gedächtnis „tokyo“/„tokyo_megamix“ und nicht in r.ROOMS)")
    ap.add_argument("--scene-file", default="")
    ap.add_argument("--desk-side", default="right", choices=["left", "right"])
    ap.add_argument("--person", default="auto", choices=["auto", "woman", "man"])
    ap.add_argument("--quote-text", default="")
    ap.add_argument("--description-file", default="")
    ap.add_argument("--community-file", default="", help="Community-Text (englisch, {URL} und {HOURS} als Platzhalter)")
    ap.add_argument("--image", default="", help="fertiges Hauptbild statt Neuerzeugung (Notfall/Test)")
    ap.add_argument("--max-hours", type=float, default=megamix.MAX_HOURS)
    ap.add_argument("--desk-x", type=float, default=0.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--no-short", action="store_true")
    ap.add_argument("--private", action="store_true", help="privat statt sofort öffentlich")
    ap.add_argument("--force", action="store_true", help="auch wenn heute schon ein Lauf im Gedächtnis steht")
    args = ap.parse_args()
    dry = args.dry_run
    today = date.today()
    base = HERE / "build" / f"tokyo-megamix-{today.isoformat()}"
    shutil.rmtree(base, ignore_errors=True)
    (base / "img").mkdir(parents=True)
    costs.start(base / "costs.json")

    if not dry and not (args.image or (args.room and args.scene_file)):
        log("ABBRUCH: --room und --scene-file (neuer Raum) angeben")
        return 2
    lines = rt.parse_quote(args.quote_text or "Let the room find its rhythm.|One more commit, one more calm breath.|My tracks will keep you company.",
                           allow_used=dry)
    intro = rt.parse_description(args.description_file) if args.description_file else (
        "🌙 A quiet loft in Tokyo at night, warm lamps and a slow, steady groove.\n\n💻 Close the extra tabs, roll your shoulders and settle in. "
        "Slow jazz, a breathy saxophone and felt piano carry you from one calm song to the next, and no song ever returns.\n\n"
        "☕ Fetch some tea, rest your eyes on the window for a moment, then go back to your next commit with a clear head.")
    community = Path(args.community_file).read_text(encoding="utf-8").strip() if args.community_file else (
        "🎷🌃 AIX WALKER · Tokyo Work Lounge Mega-Mix\n\n{HOURS} of slow jazz for deep work and coding. One steady mix, no song twice. 💛\n\n"
        "▶️ {URL}\n\n#AixWalker #TokyoWorkLounge #SlowJazz #DeepWork #CodingMusic")

    svc, mem = None, {}
    if not dry:
        from pipeline import drive
        for v in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN", "DRIVE_REFRESH_TOKEN", "GMAIL_REFRESH_TOKEN", "GOOGLE_API_KEY"):
            config.require(v)
        mem = memory.load()
        svc = drive.service()
        if not args.force and any(e.get("date") == today.isoformat() for e in mem.get("tokyo_megamix", [])):
            log("Tokyo-Mega-Mix von heute existiert schon – nichts zu tun (Exit 6)")
            return 6
        used = {str(e.get("room", "")) for k in ("tokyo", "tokyo_megamix") for e in mem.get(k, [])}
        if args.room and args.room in used:
            log(f"ABBRUCH: Raumkennung {args.room} wurde schon verwendet")
            return 2

    # 1) NEUES Bild zuerst (scheitert es, ist noch nichts gebaut/bezahlt außer dem Bild)
    var: dict = {}
    desk_x, person_x = args.desk_x or None, None
    if dry:
        art = images.procedural_art("16:9", seed=5).convert("RGB").resize((3840, 2160))
        playlist_id = "PLAYLIST"
    else:
        from pipeline import youtube
        if args.image:
            art = Image.open(args.image).convert("RGB")
            chk = rt.check_room_image(art, None) or {}
            dx, px = chk.get("desk_x"), chk.get("person_x")
            desk_x = desk_x or (float(dx) if isinstance(dx, (int, float)) and 0.05 <= float(dx) <= 0.95 else None)
            person_x = float(px) if isinstance(px, (int, float)) and 0.0 <= float(px) <= 1.0 else None
        else:
            art, dx, px = rt.make_new_room(args.room, args.scene_file, args.desk_side, args.person, base,
                                           choice={"desk_pos": "auto", "chair": "auto", "sofa": "auto", "art": "auto", "person_place": "auto"})
            if art is None:
                log("ABBRUCH: kein Bild hat alle Kriterien erfüllt (3 Versuche)")
                mail_problem("AIX WALKER Tokyo-Mega-Mix: abgebrochen (kein brauchbares Bild)",
                             "Der Tokyo-Mega-Mix wurde abgebrochen: Das neue Raumbild hat nach 3 Versuchen die automatische Prüfung nicht bestanden. "
                             f"Es wurde nichts hochgeladen. Kosten nur für Bilder: {costs.total_usd():.2f} $.")
                return 3
            desk_x, person_x = desk_x or dx, px
            var = dict(rt.LAST_VARIATION)
        playlist_id = youtube.ensure_playlist(*rt.PLAYLIST)
    art = images._cover_crop(art, 3840, 2160) if art.size != (3840, 2160) else art
    desk_x = desk_x or 0.70
    art.save(base / "img" / "main_4k.png")
    art.save(base / "master.jpg", "JPEG", quality=92)
    log(f"Bild fertig, Schreibtischmitte {desk_x:.2f}, Person {person_x}")

    # 2) Quellen laden, mischen (Duplikat = identische Datei, NICHT gleicher Titel)
    if dry:
        pairs, sources = rm.synthetic(base / "src", GENRE), []
    else:
        sources = tokyo_sources(svc)
        log(f"Quell-Mixe ({len(sources)}): {[f['name'] for f in sources]}")
        if len(sources) < 3:
            mail_problem("AIX WALKER Tokyo-Mega-Mix: abgebrochen (zu wenig Material)", f"Nur {len(sources)} Tokyo-Mixe gefunden. Nichts hochgeladen.")
            return 2
        pairs = rm.fetch_all(svc, sources, base / "src")
    order = rm.build_order(pairs, seed=today.toordinal() * 31 + 7, max_hours=args.max_hours, by_title=False)
    order = spread_and_label(order)
    hours = megamix.total_seconds(order) / 3600
    if hours < (MIN_HOURS if not dry else 0.01):
        log(f"ABBRUCH: nur {hours:.1f} Std. Material")
        mail_problem("AIX WALKER Tokyo-Mega-Mix: abgebrochen (zu wenig Material)",
                     f"Aus {len(pairs)} Tokyo-Mixen ergeben sich nur {hours:.1f} Std. verschiedene Musik (Mindestens {MIN_HOURS:.0f} Std. nötig). "
                     "Nichts hochgeladen. Hinweis: Mixe mit --reuse-music enthalten dieselben Songs wie ihr Quell-Mix und zählen nur einmal.")
        return 2
    titles = [t["title"] for t in order]
    flac, starts = monthly.join_tracks([t["path"] for t in order], base / "mix.flac", xf=rt.XF)
    total = audio.probe_duration(flac)
    total_min = int(round(total / 60))
    chapters = megamix.chapter_text(titles, starts)
    comments = megamix.tracklist_comments(titles, starts)
    albums_used = list(dict.fromkeys(t["album"] for t in order))
    log(f"{total_min} Min, {len(order)} Songs aus {len(albums_used)} Mixen")

    # 3) Texte, Cover, Thumbnail, Video (wie die normalen Tokyo-Mixe)
    t = texts(total_min, chapters, intro, var, playlist_id, "🎷 The long mix is live! What are you working on today? Full tracklist below 👇")
    cover_img = rt.make_album_cover(art, desk_x, 3000)
    cover_img.save(base / "album_3000.png", optimize=True)
    thumb = rt.v.make_thumb(art, base / "thumb.jpg", 1920, 1080)
    qpng = rt.quote_frame(lines, base / "quote.png")
    silent = rt.build_video(base / "img" / "main_4k.png", qpng, starts, total, base / "parts")
    aac = rt.loopvideo.encode_audio(flac, base / "audio.m4a")
    mp4 = base / "tokyo_megamix.mp4"
    rt.run(["ffmpeg", "-v", "error", "-y", "-i", silent, "-i", aac, "-c", "copy", "-shortest", "-movflags", "+faststart", mp4])
    log(f"Video fertig: {mp4.stat().st_size / 1e6:.0f} MB")
    comm = community.replace("{HOURS}", t["hrs"])
    (base / "metadata.txt").write_text(
        f"=== YOUTUBE TITEL ===\n{t['title']}\n\n=== BESCHREIBUNG ===\n{t['description']}\n\n=== TAGS ===\n{', '.join(t['tags'])}\n\n"
        f"=== SPRUCH ===\n{' / '.join(lines)}\n\n=== TRACKLISTE (Kommentar) ===\n{chr(10).join(comments)}\n\n"
        f"=== COMMUNITY-BEITRAG ===\n{comm.replace('{URL}', '(Video-Link)')}\n", encoding="utf-8")
    res = {"genre": GENRE, "name": NAME, "title": t["title"], "duration_min": total_min, "albums": albums_used, "tracks": len(order),
           "thumbnail": str(thumb), "cover": str(base / "album_3000.png"), "chapters": chapters, "video_id": None, "video_url": None,
           "comment_ids": [], "texts": {"community_de": comm}, "estimate_usd": costs.total_usd(), "publish_at": None, "publish_local": "sofort",
           "private": bool(args.private), "shorts": [], "room": args.room, "extra_lines": [f"Raum: {args.room} · Spruch: {' / '.join(lines)}"]}
    if dry:
        res["cost_usd"] = 0.0
        (base / "summary.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        log(f"Dry-Run fertig: {total_min} Min, {len(order)} Songs\n{t['description']}")
        return 0

    # 4) Hochladen: SOFORT öffentlich
    from pipeline import drive, youtube
    vid = youtube.upload_video(mp4, t["title"], t["description"], t["tags"], privacy="private", location=youtube.TOKYO)
    res["video_id"], res["video_url"] = vid, f"https://youtu.be/{vid}"
    log(f"Hochgeladen: {res['video_url']}")
    for step, fn in (("Thumbnail", lambda: youtube.set_thumbnail(vid, thumb)), ("Playlist", lambda: youtube.add_to_playlist(vid, playlist_id))):
        ok, err = youtube.retry(fn, label=step)
        if not ok:
            log(f"{step} NICHT gesetzt: {err[:400]}")
    if not args.private:
        youtube.set_public(vid)
        log("Mix öffentlich")
        for k, text in enumerate([t["comment"] + "\n\n" + comments[0]] + comments[1:]):
            try:
                res["comment_ids"].append(youtube.post_comment(vid, text))
            except Exception as e:  # noqa: BLE001
                log(f"Kommentar {k + 1} fehlgeschlagen: {str(e)[:160]}")
        res["extra_lines"].append("Tracklisten-Kommentar gepostet – nur noch anpinnen." if res["comment_ids"] else "Kommentar NICHT gepostet (Text in metadata.txt).")

    # 5) Short (öffentlich), Spruch wie im Mix
    short_id, s_title = None, None
    if not args.no_short:
        try:
            wav = rm.excerpt(flac, total * 0.3, base / "short_audio.wav", sec=90)
            short, chk = rt.make_short_checked(art, lines, wav, 5, base / "short", rt.short_center(desk_x, person_x), person_x=person_x)
            s_title, s_desc, s_tags = rt.short_texts(lines, res["video_url"])
            short_id = youtube.upload_video(short, s_title, s_desc, s_tags, privacy="private", location=youtube.TOKYO)
            if not args.private:
                youtube.set_public(short_id)
            res["shorts"] = [{"date": today.isoformat(), "title": s_title, "url": f"https://youtube.com/shorts/{short_id}", "check": chk}]
            log(f"Short: https://youtube.com/shorts/{short_id}")
        except Exception as e:  # noqa: BLE001
            log(f"Short fehlgeschlagen: {str(e)[:200]}")
            res["shorts"] = [{"date": today.isoformat(), "title": "(Short fehlgeschlagen)", "error": str(e)[:200]}]

    # 6) Drive, Gedächtnis, EINE Mail
    links = drive.upload_mix_package(f"{today.isoformat()} – MEGAMIX {GENRE} – {args.room or 'Tokyo'} ({total_min} Min)",
                                     [thumb, base / "master.jpg", base / "metadata.txt", base / "album_3000.png"])
    res["drive_folder"] = links.get("_folder")
    res["cost_usd"] = costs.total_usd()
    mem = memory.load()
    mem.setdefault("tokyo_megamix", []).append({"date": today.isoformat(), "video_id": vid, "short_id": short_id, "title": t["title"],
                                                "room": args.room, "variation": var, "quote": " / ".join(lines), "duration_min": total_min,
                                                "tracks": len(order), "drive": res["drive_folder"], "cost_usd": res["cost_usd"]})
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
