#!/usr/bin/env python3
"""Täglicher Zusammenschnitt: Intro + heutiger Short + ältere Shorts → 16:9-Video → Upload (öffentlich) → Drive → Report.

  python run_kids_compilation.py                       # Modus automatisch (So = weekly, 1. = monthly, sonst daily), kein Upload
  python run_kids_compilation.py --upload              # + Upload öffentlich auf den Kids-Kanal, Playlist, Drive
  python run_kids_compilation.py --mode weekly --upload
  python run_kids_compilation.py --dry-run             # Platzhalter-Shorts, kein Drive, kein Upload (Funktionstest)
  python run_kids_compilation.py --today-out build/kids/2026-10-05   # Ordner des heutigen Shorts (Standard: build/kids/<heute>)
  python run_kids_compilation.py --vertical --upload --publish-tomorrow 09:00   # langer Short (9:16), geplant für morgen 09:00
  python run_kids_compilation.py --vertical --if-due --upload --publish-tomorrow 09:00  # nur an Bau-Tagen (Mo/Mi/Fr)
  python run_kids_compilation.py --vertical --upload --publish-tomorrow 09:00 --no-social  # ohne TikTok-Post

Ergebnis: build/kids/<heute>/compilation/{compilation.mp4, thumbnail.jpg, chapters.txt, compilation_info.json,
result_compilation.json}. Exit-Code 0 = fertig, 1 = Fehler.
"""
import argparse
import json
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from kids import compilation, config, drive, social
from kids import youtube as yt

BERLIN = ZoneInfo("Europe/Berlin")


def log(msg: str) -> None:
    print(f"[{datetime.now(BERLIN).strftime('%H:%M:%S')}] {msg}", flush=True)


def _dry_short(out: Path, color: str, freq: int) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", f"color=c={color}:s=1080x1920:r=30:d=15",
                    "-f", "lavfi", "-i", f"sine=frequency={freq}:duration=15",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)], check=True)
    return out


def _drive_upload(today_out: Path, today: str, out: Path, names: list[str], subfolder: str, link: str | None,
                  title: str) -> dict:
    from pipeline import drive as base
    svc = base.service()
    root = base.ensure_folder(svc, drive.ROOT_FOLDER)
    res_today = json.loads((today_out / "result.json").read_text()) if (today_out / "result.json").exists() else {}
    title_today = res_today.get("story", {}).get("title", "Zusammenschnitt")
    folder = base.ensure_folder(svc, drive.folder_name(today, title_today), root)
    sub = base.ensure_folder(svc, subfolder, folder)
    links = {"_folder": f"https://drive.google.com/drive/folders/{sub}"}
    for name in names:
        f = out / name
        if f.exists():
            links[name] = base._upload(svc, f, sub)
    if link:
        lnk = out / "youtube_link.txt"
        lnk.write_text(f"{link}\n{title}\n")
        links[lnk.name] = base._upload(svc, lnk, sub)
    return links


def main_vertical(args, today: str) -> int:
    """Langer Short (9:16): bauen → Upload (geplant für morgen früh) → Drive → result.json."""
    import datetime as dt
    today_out = Path(args.today_out or (config.BUILD / today))
    out = Path(args.out or (today_out / "longshort"))
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    result: dict = {"date": today, "mode": "shorts", "out": str(out), "warnings": [], "dry_run": args.dry_run}
    if args.if_due and not args.dry_run and not compilation.longshort_due(today):
        log("Heute kein Bau-Tag für den langen Short – nichts zu tun.")
        result["status"] = "skipped"
        (out / "result_longshort.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    log(f"Langer Short (9:16) für {today}")
    try:
        dry = None
        if args.dry_run:
            dry = []
            cols = ["skyblue", "pink", "lightgreen", "khaki", "plum", "peachpuff"]
            for i in range(6):
                d = (dt.datetime.fromisoformat(today) - dt.timedelta(days=i)).strftime("%Y-%m-%d")
                p = _dry_short(out / "dry" / f"{d}.mp4", cols[i], 330 + 60 * i)
                dry.append({"date": d, "title": f"Dry Story {i + 1} #shorts", "name": ["Pip", "Lulu", "Momo", "Nino", "Bo", "Kiki"][i],
                            "species": "baby hamster", "video_id": f"dry{i}", "views": 100 * i, "path": p})
        info = compilation.build_vertical(today, out, today_out if not args.dry_run else None, dry_shorts=dry)
        result["info"] = {k: v for k, v in info.items() if k != "stories"}
        result["stories"] = info["stories"]
        log(f"Langer Short fertig: {info['video']} ({info['duration_sec']:.1f} s, {info['count']} Stories, Abspann: {info['intro']})")
        meta = compilation.metadata_vertical(info)
        result["meta"] = meta
        (out / "metadata_vertical.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
        log(f"Titel: {meta['title']}")
        publish_at = None
        if args.publish_tomorrow:
            hh, mm = (int(x) for x in args.publish_tomorrow.split(":"))
            local = (datetime.now(BERLIN) + dt.timedelta(days=1)).replace(hour=hh, minute=mm, second=0, microsecond=0)
            publish_at = local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            result["published_at_local"] = local.strftime("%d.%m.%Y %H:%M") + " (geplant)"
        if args.upload and not args.dry_run:
            vid = yt.upload(Path(info["video"]), meta["title"], meta["description"], meta["tags"],
                            privacy="private" if args.private else "public", publish_at=publish_at)
            try:
                yt.set_thumbnail(vid, Path(info["thumbnail"]))
            except Exception as e:  # noqa: BLE001
                result["warnings"].append(f"Thumbnail nicht gesetzt: {str(e)[:120]}")
            try:
                yt.add_to_playlist(vid)
            except Exception as e:  # noqa: BLE001
                result["warnings"].append(f"Playlist nicht gesetzt: {str(e)[:120]}")
            st = yt.status(vid).get("status", {})
            result.update({"video_id": vid, "url": f"https://www.youtube.com/shorts/{vid}",
                           "privacy": st.get("privacyStatus", ""), "publish_at": st.get("publishAt", publish_at)})
            log(f"Hochgeladen: {result['url']} ({result['privacy']}, geplant: {result.get('publish_at')})")
        if not args.no_drive and not args.dry_run and drive.available():
            try:
                result["drive"] = _drive_upload(today_out, today, out,
                                                ["longshort.mp4", "thumbnail_vertical.jpg", "chapters_vertical.txt",
                                                 "metadata_vertical.json", "longshort_info.json"],
                                                "langer-short", result.get("url"), meta["title"])
                log(f"Drive: {result['drive']['_folder']}")
            except Exception as e:  # noqa: BLE001
                result["warnings"].append(f"Drive-Ablage fehlgeschlagen: {str(e)[:160]}")
        # TikTok (Creator Rewards zahlt nur für Videos > 1 Minute – dafür ist genau dieser lange Short gedacht,
        # die täglichen 15-s-Shorts qualifizieren dort nicht). Gleicher kostenloser MCP-Weg wie der Tages-Short.
        if not args.no_social and not args.dry_run and result.get("video_id") and result.get("drive"):
            try:
                tiktok_when = (datetime.fromisoformat(publish_at.replace("Z", "+00:00")).astimezone(BERLIN)
                              + dt.timedelta(minutes=15)) if publish_at else (datetime.now(BERLIN) + dt.timedelta(minutes=20))
                sp = social.plan_longshort(meta, result["drive"], tiktok_when)
                plan_path = out / "longshort_social_plan.json"
                plan_path.write_text(json.dumps(sp, indent=2, ensure_ascii=False))
                result["social"] = {"status": "pending_mcp", "plan_file": str(plan_path)}
                result["warnings"].append("TikTok-Post vorbereitet (longshort_social_plan.json) – wird über den "
                                          "kostenlosen Metricool-Connector in dieser Sitzung veröffentlicht")
                log(f"TikTok-Plan (langer Short) geschrieben: {plan_path}")
            except Exception as e:  # noqa: BLE001
                result["warnings"].append(f"TikTok-Plan (langer Short) fehlgeschlagen: {str(e)[:160]}")
        result["status"] = "ok"
        rc = 0
    except Exception as e:  # noqa: BLE001
        result.update({"status": "error", "error": str(e), "trace": traceback.format_exc()[-2000:]})
        log(f"FEHLER: {e}")
        rc = 1
    result.update({"elapsed_min": (time.time() - t0) / 60, "finished_utc": datetime.now(timezone.utc).isoformat()})
    (out / "result_longshort.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    rj = today_out / "result.json"
    if rj.exists() and not args.dry_run:
        try:
            r = json.loads(rj.read_text())
            r["longshort"] = {"status": result["status"], "url": result.get("url"), "privacy": result.get("privacy"),
                              "published_at_local": result.get("published_at_local"),
                              "title": result.get("meta", {}).get("title"), "count": result.get("info", {}).get("count"),
                              "duration_sec": result.get("info", {}).get("duration_sec"),
                              "drive": result.get("drive", {}).get("_folder"), "error": result.get("error"),
                              "social": result.get("social"), "warnings": result.get("warnings", [])}
            rj.write_text(json.dumps(r, indent=2, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            log(f"result.json nicht aktualisiert: {e}")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["daily", "weekly", "monthly"], default=None)
    ap.add_argument("--today", default=None, help="Datum JJJJ-MM-TT (Standard: heute, Europe/Berlin)")
    ap.add_argument("--today-out", default=None, help="Build-Ordner des heutigen Shorts")
    ap.add_argument("--out", default=None)
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--private", action="store_true", help="privat statt öffentlich hochladen (Test)")
    ap.add_argument("--no-drive", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--vertical", action="store_true", help="langen Short (9:16, bis 3 min) statt 16:9-Video bauen")
    ap.add_argument("--if-due", action="store_true", help="mit --vertical: nur an den Bau-Tagen (KIDS_LONGSHORT_BUILD_DAYS)")
    ap.add_argument("--no-social", action="store_true", help="mit --vertical: kein TikTok-Post über Metricool")
    ap.add_argument("--publish-tomorrow", default=None, help="Uhrzeit Europe/Berlin MORGEN, z. B. 09:00 (geplante Veröffentlichung)")
    args = ap.parse_args()

    today = args.today or datetime.now(BERLIN).strftime("%Y-%m-%d")
    if args.vertical:
        return main_vertical(args, today)
    mode = args.mode or compilation.mode_for(today)
    today_out = Path(args.today_out or (config.BUILD / today))
    out = Path(args.out or (today_out / "compilation"))
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    result: dict = {"date": today, "mode": mode, "out": str(out), "warnings": [], "dry_run": args.dry_run}
    log(f"Zusammenschnitt {mode} für {today}")
    try:
        dry = None
        if args.dry_run:
            dry = []
            cols = ["skyblue", "pink", "lightgreen", "khaki", "plum", "peachpuff"]
            for i in range(6):
                d = (datetime.fromisoformat(today) - __import__("datetime").timedelta(days=i)).strftime("%Y-%m-%d")
                p = _dry_short(out / "dry" / f"{d}.mp4", cols[i], 330 + 60 * i)
                dry.append({"date": d, "title": f"Dry Story {i + 1} #shorts", "name": ["Pip", "Lulu", "Momo", "Nino", "Bo", "Kiki"][i],
                            "species": "baby hamster", "video_id": f"dry{i}", "views": 100 * i, "path": p})
        info = compilation.build(mode, today, out, today_out if not args.dry_run else None, dry_shorts=dry)
        result["info"] = {k: v for k, v in info.items() if k != "stories"}
        result["stories"] = info["stories"]
        log(f"Video fertig: {info['video']} ({info['duration_sec']:.1f} s, {info['count']} Stories, Intro: {info['intro']})")

        meta = compilation.metadata(info, today) if not args.dry_run else {
            "title": f"{info['count']} Cute Stories (dry) | Giggle Meadow", "description": info["chapters"], "tags": ["test"]}
        result["meta"] = meta
        (out / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
        log(f"Titel: {meta['title']}")

        if args.upload and not args.dry_run:
            if any(s["date"] == today for s in info["stories"]) is False:
                result["warnings"].append("heutiger Short nicht im Zusammenschnitt (noch nicht veröffentlicht?)")
            vid = yt.upload(Path(info["video"]), meta["title"], meta["description"], meta["tags"],
                            privacy="private" if args.private else "public")
            try:
                yt.set_thumbnail(vid, Path(info["thumbnail"]))
            except Exception as e:  # noqa: BLE001
                result["warnings"].append(f"Thumbnail nicht gesetzt: {str(e)[:120]}")
            try:
                yt.add_to_playlist(vid)
            except Exception as e:  # noqa: BLE001
                result["warnings"].append(f"Playlist nicht gesetzt: {str(e)[:120]}")
            s = yt.status(vid).get("status", {})
            result.update({"video_id": vid, "url": f"https://www.youtube.com/watch?v={vid}",
                           "privacy": s.get("privacyStatus", "")})
            log(f"Hochgeladen: {result['url']} ({result['privacy']})")

        if not args.no_drive and not args.dry_run and drive.available():
            try:
                result["drive"] = _drive_upload(today_out, today, out,
                                                ["compilation.mp4", "thumbnail.jpg", "chapters.txt", "metadata.json", "compilation_info.json"],
                                                "zusammenschnitt", result.get("url"), meta["title"])
                log(f"Drive: {result['drive']['_folder']}")
            except Exception as e:  # noqa: BLE001
                result["warnings"].append(f"Drive-Ablage fehlgeschlagen: {str(e)[:160]}")
        result["status"] = "ok"
        rc = 0
    except Exception as e:  # noqa: BLE001
        result.update({"status": "error", "error": str(e), "trace": traceback.format_exc()[-2000:]})
        log(f"FEHLER: {e}")
        rc = 1
    result.update({"elapsed_min": (time.time() - t0) / 60, "finished_utc": datetime.now(timezone.utc).isoformat()})
    (out / "result_compilation.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    # ins Tages-result.json übernehmen, damit die Report-Mail beide Videos nennt
    rj = today_out / "result.json"
    if rj.exists() and not args.dry_run:
        try:
            r = json.loads(rj.read_text())
            r["compilation"] = {"status": result["status"], "mode": mode, "url": result.get("url"),
                                "privacy": result.get("privacy"), "title": result.get("meta", {}).get("title"),
                                "count": result.get("info", {}).get("count"),
                                "duration_sec": result.get("info", {}).get("duration_sec"),
                                "drive": result.get("drive", {}).get("_folder"), "error": result.get("error"),
                                "warnings": result.get("warnings", [])}
            rj.write_text(json.dumps(r, indent=2, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            log(f"result.json nicht aktualisiert: {e}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
