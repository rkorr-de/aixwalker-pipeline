#!/usr/bin/env python3
"""Monats-Mix (am 1. des Monats, vollautomatisch): je Thema/Genre, das im Vormonat ≥ 2 Wochen-Mixe hat, werden die
Mixe aus Drive zu einem 2–4-Stunden-Mix verbunden (Video mit atmendem Licht aus den Album-Covern) und öffentlich auf
YouTube hochgeladen (inkl. Kommentar, Drive-Ordner, Bericht per E-Mail, Gedächtnis). Kosten: nur 1 Motivbild je
Monats-Mix (ca. 0,13 $), keine Lyria-Kosten, kein DistroKid.

  python monthly_mix.py                    # Vormonat, alle Genres mit genug Material
  python monthly_mix.py --month 2026-10    # bestimmten Monat
  python monthly_mix.py --dry-run          # synthetische Tracks, kein Drive/YouTube/Mail
  python monthly_mix.py --private          # Upload privat statt öffentlich
"""
import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from PIL import Image

from pipeline import audio, config, drive, images, memory, metadata, monthly, youtube

MIN_MIN, TARGET_MIN, MAX_MIN, MAX_RUNS = 100, 150, 240, 4
OWN_LINES = ("Italian Chillout", "Ibiza Sunset Lounge")   # eigene Linien zuerst – sie fallen nie wegen MAX_RUNS weg (Rolf 08.10.2026)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] [monthly] {msg}", flush=True)


def prev_month(today: date) -> str:
    y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    return f"{y}-{m:02d}"


def shift(month: str, k: int) -> str:
    y, m = int(month[:4]), int(month[5:])
    m -= k
    while m < 1:
        m += 12
        y -= 1
    return f"{y}-{m:02d}"


def collect_folders(svc) -> list[dict]:
    root = drive.ensure_folder(svc, drive.ROOT_FOLDER)
    out = []
    for f in drive.list_children(svc, root, folders=True):
        p = monthly.parse_folder(f["name"])
        if p:
            p["id"] = f["id"]
            out.append(p)
    return out


def fetch_mix(svc, folder: dict, dst: Path) -> dict:
    """Lädt MP3s (und Cover) eines Wochen-Mixes. Liefert {tracks:[Path], titles:[str], cover:Path|None, minutes}."""
    kids = drive.list_children(svc, folder["id"])
    mp3_dir = next((k for k in kids if k["name"] == "mp3" and k["mimeType"] == drive.FOLDER_MIME), None)
    files = drive.list_children(svc, mp3_dir["id"], folders=False) if mp3_dir else []
    files = [f for f in files if f["name"].lower().endswith(".mp3")]
    d = dst / folder["name"][:10]
    tracks, titles = [], []
    for f in files:
        p = drive.download(svc, f["id"], d / f["name"])
        tracks.append(p)
        titles.append(monthly.track_title(f["name"]))
    cover = next((k for k in kids if k["name"].startswith("album_")), None)
    cp = drive.download(svc, cover["id"], d / "cover.png") if cover else None
    minutes = sum(audio.probe_duration(t) for t in tracks) / 60
    return {"tracks": tracks, "titles": titles, "cover": cp, "minutes": minutes}


RETIRED_GENRES = ("gym", "drive")   # Gym- und Night-Drive-Mixe eingestellt (Rolf, 08.10.2026)


def pick_groups(folders: list[dict], month: str, done: set[str]) -> dict[str, list[dict]]:
    """Genre → Mixe. Basis: Mixe des Monats; zu wenig Material → gleiche Genre-Mixe der 2 Vormonate ergänzen."""
    by_genre = defaultdict(list)
    for f in folders:
        by_genre[f["genre"]].append(f)
    groups = {}
    for g, items in by_genre.items():
        if any(x in g.lower() for x in RETIRED_GENRES):
            log(f"{g}: Genre eingestellt – kein Monats-Mix")
            continue
        if f"{month}|{g}" in done:
            log(f"{g}: Monats-Mix {month} existiert schon – übersprungen")
            continue
        cur = sorted([f for f in items if f["date"].startswith(month)], key=lambda f: f["date"])
        if not cur:
            continue
        older = sorted([f for f in items if f["date"][:7] in (shift(month, 1), shift(month, 2))],
                       key=lambda f: f["date"], reverse=True)
        sel = list(cur)
        if len(sel) < 2:
            sel = older[:2 - len(sel)][::-1] + sel
        if len(sel) >= 2:
            groups[g] = sel
    return groups


def synthetic(dst: Path) -> list[tuple[dict, dict]]:
    """Dry-run: 3 Fake-Mixe mit je 4 Sinus-MP3s und prozeduralen Covern."""
    out = []
    for i in range(3):
        d = dst / f"fake{i}"
        d.mkdir(parents=True, exist_ok=True)
        tracks, titles = [], []
        for t in range(4):
            p = d / f"{t + 1:02d} - Aix Walker - Fake {i}{t}.mp3"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                            f"sine=frequency={200 + 40 * (i * 4 + t)}:duration=45", "-ac", "2", str(p)], check=True)
            tracks.append(p)
            titles.append(f"Fake {i}{t}")
        cover = d / "cover.png"
        images.procedural_art("1:1", seed=i).save(cover)
        out.append(({"album": f"Fake Mix {i}", "genre": "Dark Ambient Spa", "bpm": 55 + i, "date": f"2026-09-0{i + 1}"},
                    {"tracks": tracks, "titles": titles, "cover": cover, "minutes": 3.0}))
    return out


def produce(genre: str, month: str, pairs: list[tuple[dict, dict]], out: Path, mem: dict, args) -> dict:
    y, m = int(month[:4]), int(month[5:])
    month_label = monthly.MONTHS[m - 1]
    tracks = [t for _, mx in pairs for t in mx["tracks"]]
    titles = [t for _, mx in pairs for t in mx["titles"]]
    out.mkdir(parents=True, exist_ok=True)
    log(f"{genre}: {len(tracks)} Tracks aus {len(pairs)} Mixen verbinden …")
    flac, starts = monthly.join_tracks(tracks, out / "monthly.flac")
    total_sec = audio.probe_duration(flac)
    total_min = int(round(total_sec / 60))
    chapter_text = metadata.chapters(titles, starts)
    bpms = [p["bpm"] for p, _ in pairs]
    bpm_range = f"{min(bpms)}" if min(bpms) == max(bpms) else f"{min(bpms)}–{max(bpms)}"
    texts = monthly.make_texts(genre, month_label, y, total_min,
                               [{"album": p["album"], "video_id": next((e.get("video_id") for e in mem.get("mixes", [])
                                                                          if e.get("album", "").lower() == p["album"].lower()), None)}
                                for p, _ in pairs], chapter_text, bpm_range)
    if args.dry_run:
        art = images.procedural_art("16:9", seed=1)
    else:
        try:
            art = images.generate_art(monthly.hero_prompt(genre), "16:9", pro=True, style=images.style_for(genre))
            
        except Exception as e:  # noqa: BLE001
            log(f"Motiv-Erzeugung fehlgeschlagen ({e}) – Cover des letzten Mixes als Ersatz")
            art = Image.open(pairs[-1][1]["cover"]) if pairs[-1][1].get("cover") else images.procedural_art("16:9", seed=1)
    head = monthly.genre_info(genre)[0]
    thumb = monthly.make_monthly_thumbnail(art, monthly.hours_label(total_min), head, f"{month_label} {y}",
                                           out / "thumbnail_monthly.jpg")
    frame = monthly.make_monthly_thumbnail(art, monthly.hours_label(total_min), head, f"{month_label} {y}",
                                           out / "frame.png", 1920, 1080)
    fr = Image.open(frame).convert("RGB")
    images.add_subscribe_badge(fr)
    fr.save(frame)
    log("Video rendern (atmendes Licht) …")
    try:
        mp4 = monthly.build_animated_video(pairs, flac, starts, out / "monthly.mp4")
    except Exception as e:  # noqa: BLE001 – lieber Standbild als kein Video
        log(f"Animiertes Video fehlgeschlagen ({str(e)[:160]}) – Standbild")
        mp4 = monthly.build_still_video(frame, flac, out / "monthly.mp4")
    flac.unlink(missing_ok=True)
    result = {"genre": genre, "month": month, "title": texts["title"], "duration_min": total_min,
              "albums": [p["album"] for p, _ in pairs], "tracks": len(tracks), "thumbnail": str(thumb),
              "mp4": str(mp4), "chapters": chapter_text, "video_id": None, "video_url": None, "comment_id": None,
              "cost_usd": 0.0 if args.dry_run else config.PRICES_USD["image_pro"]}
    meta = f"""=== YOUTUBE TITEL ===
{texts['title']}

=== BESCHREIBUNG ===
{texts['description']}
=== TAGS ===
{', '.join(texts['tags'])}

=== PINNED COMMENT ===
{texts['comment']}

=== COMMUNITY-BEITRAG ===
{texts['community_de']}
"""
    (out / "metadata.txt").write_text(meta, encoding="utf-8")
    if args.dry_run:
        return result
    vid = youtube.upload_video(mp4, texts["title"], texts["description"], texts["tags"],
                               privacy="private" if args.private else "public")
    result["video_id"], result["video_url"] = vid, f"https://youtu.be/{vid}"
    log(f"Hochgeladen: {result['video_url']}")
    try:
        youtube.set_thumbnail(vid, thumb)
    except Exception as e:  # noqa: BLE001
        log(f"Thumbnail fehlgeschlagen: {e}")
    try:
        youtube.add_to_playlist(vid, youtube.playlist_for(texts["playlist"]))
    except Exception as e:  # noqa: BLE001
        log(f"Playlist fehlgeschlagen: {e}")
    if not args.private:
        try:
            result["comment_id"] = youtube.post_comment(vid, texts["comment"])
        except Exception as e:  # noqa: BLE001
            log(f"Kommentar fehlgeschlagen: {e}")
    result["texts"] = texts
    return result


def send_mail(results: list[dict], errors: list[str], month: str) -> dict:
    from pipeline import mailer
    svc = mailer._service()
    to = config.REPORT_EMAIL or svc.users().getProfile(userId="me").execute()["emailAddress"]
    lines = [f"AIX WALKER Monats-Mix {month}", ""]
    for r in results:
        t = r.get("texts", {})
        lines += [f"✅ {r['genre']}: {r['title']}", f"   {r.get('video_url')} · {r['duration_min']} Min · {r['tracks']} Tracks",
                  f"   Drive: {r.get('drive_folder', '-')}",
                  "   Mixe: " + ", ".join(r["albums"]),
                  f"   Kommentar gepostet: {'ja' if r.get('comment_id') else 'nein'} (ANPINNEN geht nur in Studio: Kommentar → ⋮ → Anpinnen)",
                  "   Community-Beitrag (Text zum Einfügen, API kann keine Beiträge posten):",
                  "   " + t.get("community_de", "").replace("\n", "\n   "), ""]
    if errors:
        lines += ["⚠️ Probleme:"] + [f" - {e}" for e in errors]
    if not results and not errors:
        lines.append("Kein Genre hatte genug Material – diesen Monat kein Monats-Mix.")
    msg = EmailMessage()
    msg["To"], msg["From"] = to, "me"
    msg["Subject"] = f"AIX WALKER Monats-Mix {month}: {len(results)} online" + (" ⚠️" if errors else "")
    msg.set_content("\n".join(lines))
    if results and Path(results[0]["thumbnail"]).exists():
        mailer._attach_image(msg, Path(results[0]["thumbnail"]))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"sent": True, "to": to}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--private", action="store_true")
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--genre", default=None)
    args = ap.parse_args()
    month = args.month or prev_month(date.today())
    base = config.ROOT / "build" / f"monthly-{month}"
    shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True, exist_ok=True)
    results, errors = [], []

    if args.dry_run:
        mem = {"mixes": []}
        pairs = synthetic(base / "src")
        groups = {"Dark Ambient Spa": pairs}
        svc = None
    else:
        for v in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN", "DRIVE_REFRESH_TOKEN"):
            config.require(v)
        mem = memory.load()
        svc = drive.service()
        done = {f"{e['month']}|{e['genre']}" for e in mem.get("monthly", [])}
        sel = pick_groups(collect_folders(svc), month, done)
        if args.genre:
            sel = {g: v for g, v in sel.items() if g == args.genre}
        groups = {}
        for g, folders in sel.items():
            fetched = []
            for f in folders:
                log(f"lade {f['name']} …")
                fetched.append((f, fetch_mix(svc, f, base / "src" / g.replace(" ", "_"))))
            total = sum(mx["minutes"] for _, mx in fetched)
            if total < MIN_MIN:
                log(f"{g}: nur {total:.0f} Min – zu wenig, übersprungen")
                continue
            groups[g] = fetched
        log(f"Genres mit Monats-Mix: {list(groups) or 'keine'}")

    ordered = sorted(groups.items(), key=lambda kv: kv[0] not in OWN_LINES)
    for g, pairs in ordered[:MAX_RUNS]:
        # Obergrenze: ältere Mixe verwerfen, bis ≤ MAX_MIN
        while len(pairs) > 2 and sum(mx["minutes"] for _, mx in pairs) > MAX_MIN:
            pairs = pairs[1:]
        try:
            res = produce(g, month, pairs, base / g.replace(" ", "_"), mem, args)
            if not args.dry_run:
                files = [Path(res["thumbnail"]), base / g.replace(" ", "_") / "metadata.txt", Path(res["mp4"])]
                links = drive.upload_mix_package(f"{month}-01 – MONTHLY {g} ({res['duration_min']} Min)", files)
                res["drive_folder"] = links["_folder"]
                mem.setdefault("monthly", []).append({"month": month, "genre": g, "video_id": res["video_id"],
                                                      "title": res["title"], "duration_min": res["duration_min"],
                                                      "albums": res["albums"], "drive": res["drive_folder"]})
                memory.save(mem)
            results.append(res)
        except Exception as e:  # noqa: BLE001
            log(f"FEHLER {g}: {e}")
            errors.append(f"{g}: {str(e)[:300]}")

    (base / "summary.json").write_text(json.dumps({"results": results, "errors": errors}, indent=2, ensure_ascii=False,
                                                  default=str), encoding="utf-8")
    if not args.dry_run and not args.no_email:
        try:
            log(f"Mail: {send_mail(results, errors, month)}")
        except Exception as e:  # noqa: BLE001
            log(f"Mail fehlgeschlagen: {e}")
    log(f"fertig: {len(results)} Monats-Mix(e), {len(errors)} Fehler")
    return 1 if errors and not results else 0


if __name__ == "__main__":
    sys.exit(main())
