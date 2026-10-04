#!/usr/bin/env python3
"""Täglicher Kids-Short: Story → Figur → Keyframes → 2 Veo-Clips → Schnitt → Thumbnail → Upload → Report.

  python run_kids_short.py --dry-run                      # Funktionstest ohne API-Kosten (Platzhalter-Clips)
  python run_kids_short.py --out build/kids/test          # alles erzeugen, kein Upload
  python run_kids_short.py --upload --private             # Upload privat (Testlauf)
  python run_kids_short.py --upload --publish-at 2026-10-04T14:00:00Z   # geplante Veröffentlichung (UTC)
  python run_kids_short.py --upload --public              # sofort öffentlich
  python run_kids_short.py --mail                         # zusätzlich Report-Mail per Gmail-API (GMAIL_REFRESH_TOKEN)
  python run_kids_short.py --theme "kitten and a bouncing ball of yarn"   # Thema vorgeben
  python run_kids_short.py --no-drive                     # ohne Ablage in Google Drive (Standard: Ablage unter „Giggle Meadow Shorts/<Datum – Titel>“)

Ergebnis: <out>/result.json (url, video_id, story, Kosten, QC), <out>/short.mp4, <out>/thumbnail.jpg,
<out>/contact_sheet.jpg (Prüfbild), <out>/costs.json, <out>/story.json.
Exit-Code 0 = fertig, 2 = Budget überschritten (nichts hochgeladen), 1 = anderer Fehler.
"""
import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

from kids import config, costs, drive, fal, gemini, history, mail, render, review, sfx_library, social, story as story_mod, veo
from kids import youtube as yt

BERLIN = ZoneInfo("Europe/Berlin")


def log(msg: str) -> None:
    print(f"[{datetime.now(BERLIN).strftime('%H:%M:%S')}] {msg}", flush=True)


def dry_clip(out: Path, color: str, seconds: int = 8) -> Path:
    """Platzhalter-Clip mit Ton (ohne API) für Trockenläufe."""
    import subprocess
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", f"color=c={color}:s=1080x1920:r=30:d={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)], check=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--theme", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--private", action="store_true")
    ap.add_argument("--public", action="store_true")
    ap.add_argument("--publish-at", default=None, help="RFC3339 UTC, z. B. 2026-10-04T14:00:00Z")
    ap.add_argument("--publish-local", default=None, help="Uhrzeit Europe/Berlin HEUTE, z. B. 16:00 (wird in UTC umgerechnet)")
    ap.add_argument("--mail", action="store_true", help="Report per Gmail-API senden (GMAIL_REFRESH_TOKEN)")
    ap.add_argument("--no-music", action="store_true")
    ap.add_argument("--skip-review", action="store_true", help="Videoprüfung vor dem Upload überspringen (nur Tests)")
    ap.add_argument("--story-only", action="store_true", help="nur Story schreiben + prüfen (fast kostenlos)")
    ap.add_argument("--no-drive", action="store_true", help="nicht in Google Drive ablegen (Standard: ablegen)")
    ap.add_argument("--no-social", action="store_true", help="keine Instagram/TikTok-Posts über Metricool")
    args = ap.parse_args()

    today = datetime.now(BERLIN).strftime("%Y-%m-%d")
    if args.publish_local:
        hh, mm = (int(x) for x in args.publish_local.split(":"))
        local = datetime.now(BERLIN).replace(hour=hh, minute=mm, second=0, microsecond=0)
        if local < datetime.now(BERLIN):
            local = local.replace(minute=min(59, datetime.now(BERLIN).minute + 2))  # Zeit schon vorbei → in 2 Minuten
        args.publish_at = local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        args.upload = True
    out = Path(args.out or (config.BUILD / today))
    out.mkdir(parents=True, exist_ok=True)
    costs.start(out / "costs.json")
    t0 = time.time()
    result: dict = {"date": today, "out": str(out), "warnings": [], "dry_run": args.dry_run}

    est = costs.estimate(standard="fast" not in config.VEO_MODELS[0] and "lite" not in config.VEO_MODELS[0],
                         retries=config.MAX_CLIP_RETRIES)
    log(f"Kostenvoranschlag: {est['usd']:.2f} $ ≈ {est['eur']:.2f} € (Budget {config.BUDGET_USD:.2f} $)")
    for ln in est["lines"]:
        log("  - " + ln)
    if est["usd"] > config.BUDGET_USD:
        result["warnings"].append("Voranschlag über Budget – Lauf kann vorzeitig abbrechen")

    try:
        # 1) Bisherige Titel (keine Wiederholung)
        used: list[str] = []
        if not args.dry_run:
            try:
                used = yt.uploaded_titles()
                log(f"{len(used)} bisherige Uploads gelesen")
            except Exception as e:  # noqa: BLE001
                result["warnings"].append(f"Upload-Liste nicht lesbar: {e}")

        # 2) Story: neues Tier × neuer Lehrinhalt, strenge Prüfung vor dem Dreh (kids/story.py)
        if args.dry_run:
            st = json.loads((config.ROOT / "kids" / "example_story.json").read_text())
            if args.theme:
                st["theme"] = args.theme
        else:
            past = history.load()
            try:
                past = history.refresh_views(past)
                history.save(past)
            except Exception as e:  # noqa: BLE001
                log(f"Aufrufzahlen nicht aktualisiert ({e}) – wähle ohne Lernen aus der Wirkung")
            log(f"Verlauf: {len(past)} bisherige Shorts")
            st = story_mod.create(past, used, theme=args.theme, log=log)
        (out / "story.json").write_text(json.dumps(st, indent=2, ensure_ascii=False))
        result["story"] = st
        log(f"Story: {st['title']}  |  Figur: {st['character']['name']} ({st['character']['species']})")
        if args.story_only:
            result.update(status="ok", cost_usd=costs.total_usd(), cost_report=costs.report())
            (out / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
            log(costs.report())
            raise SystemExit(0)

        # 3) Bilder: Charakter-Sheet, Keyframe 1, Thumbnail
        if args.dry_run:
            sheet = Image.new("RGB", (1024, 1024), (240, 220, 180))
            kf1 = Image.new("RGB", (1080, 1920), (180, 220, 255))
            thumb_art = kf1
        else:
            sheet = gemini.image(story_mod.character_sheet_prompt(st), aspect="1:1", out=out / "character_sheet.png")
            kf1 = gemini.image(story_mod.keyframe_prompt(st, 0), aspect="9:16", references=[sheet],
                               out=out / "keyframe_1.png")
            thumb_art = gemini.image(story_mod.thumbnail_prompt(st), aspect="9:16", pro=True, references=[sheet, kf1],
                                     out=out / "thumbnail_art.png")
        render.make_thumbnail(thumb_art, out / "thumbnail.jpg")
        log("Charakter-Sheet, Keyframe und Thumbnail fertig")

        # 4) Video: Kling (ein 15-s-Clip, fal.ai) oder Veo (2 Clips, Clip 2 startet mit dem letzten Bild von Clip 1)
        c1, c2 = out / "clip_1.mp4", out / "clip_2.mp4"
        kling = config.VIDEO_PROVIDER == "kling" and not args.dry_run
        sfx: list = []
        if kling:
            fal.kling_clip(story_mod.kling_prompt(st), kf1, c1, seconds=15, audio=config.KLING_AUDIO)
            log(f"Kling-Clip fertig (Kling 3.0 {config.KLING_TIER}, 15 s, {'mit' if config.KLING_AUDIO else 'ohne'} Ton)")
        if kling and config.KLING_AUDIO:
            st["sfx_cues"] = []    # Kling-Ton ist schon synchron – keine nachträglichen Geräusche
        elif kling:
            try:   # Geräusche an die tatsächlich sichtbaren Aktionen anpassen (Kling hält Zeiten nicht exakt ein)
                placed = review.place_sounds(c1, st)
                if placed:
                    st["sfx_cues"] = placed
                    (out / "story.json").write_text(json.dumps(st, indent=2, ensure_ascii=False))
            except Exception as e:  # noqa: BLE001
                result["warnings"].append(f"Geräusch-Platzierung per Video übersprungen: {str(e)[:120]}")
            sfx = [(sfx_library.path(c["sound"]), c["second"]) for c in st.get("sfx_cues", [])]
            sfx = [(f, t) for f, t in sfx if f]
            cue_txt = ", ".join("%.1fs %s" % (c["second"], c["sound"]) for c in st.get("sfx_cues", []))
            log(f"Geräusche: {cue_txt}")
            if not sfx:
                result["warnings"].append("keine Geräusche aus der Bibliothek gewählt – nur Musik")
        elif args.dry_run:
            dry_clip(c1, "skyblue")
            dry_clip(c2, "pink")
        else:
            veo.generate_clip(story_mod.veo_prompt(st, 0), c1, first_frame=kf1, references=[sheet])
            log(f"Clip 1 fertig ({veo.current_model()})")
            # Clip 2 setzt nahtlos am letzten Bild von Clip 1 an (kein erzwungenes Loop-Ende mehr – das hat die
            # Handlung unlogisch gemacht)
            lf = Image.open(render.last_frame(c1, out / "clip_1_last.png"))
            veo.generate_clip(story_mod.veo_prompt(st, 1), c2, first_frame=lf, references=[sheet])
            log("Clip 2 fertig")
        result["veo_model"] = (f"kling-3.0-{config.KLING_TIER} (fal.ai)" if kling
                               else veo.current_model() or ("dry-run" if args.dry_run else ""))

        # 5) Musikbett
        music = None
        if not args.no_music:
            music = out / "music.mp3"
            if args.dry_run:
                import subprocess
                subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                                "-i", "sine=frequency=660:duration=16", "-c:a", "libmp3lame", str(music)], check=True)
            else:
                try:
                    gemini.lyria(f"{st['music']} Instrumental, no vocals, playful, light, bouncy, ukulele, "
                                 f"glockenspiel, pizzicato strings, children's cartoon, happy, 20 seconds, "
                                 f"clean start, loopable.", music)
                except Exception as e:  # noqa: BLE001
                    result["warnings"].append(f"Musikbett übersprungen: {str(e)[:120]}")
                    music = None

        # 6) Schnitt + QC
        if kling:
            final = render.assemble_single(c1, sfx, music, out / "short.mp4")
            try:   # nur bei Bibliotheks-Geräuschen: Abgleich prüfen, verrutschte Geräusche einmal nachsetzen
                if not st.get("sfx_cues"):
                    raise StopIteration
                chk = review.check_sync(final, st.get("sfx_cues", []))
                result["sound_sync"] = chk
                fixed, changed = [], False
                for c, k in zip(st.get("sfx_cues", []), chk.get("cues", [])):
                    if not k.get("in_sync") and isinstance(k.get("better_second"), (int, float)):
                        c = {**c, "second": round(float(k["better_second"]), 2)}
                        changed = True
                    fixed.append(c)
                if changed:
                    st["sfx_cues"] = fixed
                    sfx = [(sfx_library.path(c["sound"]), c["second"]) for c in fixed if sfx_library.path(c["sound"])]
                    final = render.assemble_single(c1, sfx, music, out / "short.mp4")
                    log("Geräusche nachjustiert")
                log(f"Ton-Abgleich: {'alles synchron' if chk.get('all_good') else 'nachjustiert'}")
                lv = render.cue_levels(final, st.get("sfx_cues", []))
                result["sound_levels"] = lv
                log("Geräusch-Lautstärke über Musik: " + ", ".join(f"{r['sound']} {r['above_music_db']:+.0f} dB"
                                                                  for r in lv["cues"]))
                if not lv["ok"]:
                    result["warnings"].append("mindestens ein Geräusch kaum lauter als die Musik")
            except StopIteration:
                pass
            except Exception as e:  # noqa: BLE001
                result["warnings"].append(f"Ton-Abgleich übersprungen: {str(e)[:120]}")
        else:
            final = render.assemble(c1, c2, music, out / "short.mp4")
        q = render.qc(final, min_bytes=10_000 if args.dry_run else 500_000)
        render.contact_sheet(final, out / "contact_sheet.jpg")
        result["qc"] = q
        if not q["ok"]:
            raise RuntimeError("QC fehlgeschlagen: " + "; ".join(q["reasons"]))
        log(f"Short fertig: {final} ({q['duration']:.2f} s)")

        # 6b) Strenge Videoprüfung (KI-Fehler, Story verständlich?) – unter der Mindestnote kein Upload
        if not args.dry_run and not args.skip_review:
            rv = review.review_video(final, st, out / "contact_sheet.jpg")
            result["video_review"] = rv
            log(f"Videoprüfung: {rv['scores']} → {'bestanden' if rv['passed'] else 'ABGELEHNT'}"
                + (f" | Fehler: {'; '.join(rv.get('errors', []))[:300]}" if rv.get("errors") else ""))
            if not rv["passed"]:
                try:
                    history.add(history.entry_from_story(st, today, "rejected by video review"))
                except Exception as e:  # noqa: BLE001
                    log(f"Verlauf nicht gespeichert: {e}")
                raise RuntimeError("Videoprüfung nicht bestanden – nichts veröffentlicht. Fehler: "
                                   + "; ".join(rv.get("errors", []))[:400])

        # 7) Upload
        if args.upload and not args.dry_run:
            privacy = "public" if args.public else "private"
            vid = yt.upload(final, st["title"], st["description"], st["tags"], privacy=privacy,
                            publish_at=args.publish_at)
            try:
                yt.set_thumbnail(vid, out / "thumbnail.jpg")
            except Exception as e:  # noqa: BLE001
                result["warnings"].append(f"Thumbnail nicht gesetzt: {str(e)[:120]}")
            try:
                yt.add_to_playlist(vid)
            except Exception as e:  # noqa: BLE001
                result["warnings"].append(f"Playlist nicht gesetzt: {str(e)[:120]}")
            s = yt.status(vid).get("status", {})
            result.update({"video_id": vid, "url": f"https://www.youtube.com/shorts/{vid}",
                           "privacy": s.get("privacyStatus", privacy), "publish_at": s.get("publishAt", args.publish_at)})
            when = args.publish_at
            if when:
                dt = datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone(BERLIN)
                result["published_at_local"] = dt.strftime("%d.%m.%Y %H:%M") + " (geplant)"
            else:
                result["published_at_local"] = datetime.now(BERLIN).strftime("%d.%m.%Y %H:%M")
            log(f"Hochgeladen: {result['url']} ({result['privacy']})")
            try:
                history.add(history.entry_from_story(st, today, "published", vid))
            except Exception as e:  # noqa: BLE001
                result["warnings"].append(f"Verlauf nicht gespeichert: {str(e)[:120]}")
        # 8) Google Drive: kompletter Short-Ordner unter „Giggle Meadow Shorts/<Datum – Titel>“
        if not args.no_drive and not args.dry_run:
            if drive.available():
                try:
                    (out / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
                    links = drive.upload_short_package(out, today, st["title"], result.get("video_id"))
                    result["drive"] = links
                    log(f"Drive: {links['_folder']}")
                except Exception as e:  # noqa: BLE001
                    result["warnings"].append(f"Drive-Ablage fehlgeschlagen: {str(e)[:160]}")
                    log(f"Drive-Ablage fehlgeschlagen: {e}")
            else:
                result["warnings"].append("Drive-Ablage übersprungen: DRIVE_REFRESH_TOKEN fehlt")
        # 9) Social: Instagram Reel + TikTok über Metricool (nur wenn METRICOOL_TOKEN gesetzt und Upload erfolgt)
        if not args.no_social and not args.dry_run and result.get("video_id") and result.get("drive"):
            if social.available():
                try:
                    result["social"] = social.post_short(st, result["drive"], today)
                    log("Social-Posts angemeldet: " + ", ".join(f"{n} {v.get('when')}" for n, v in result["social"].items()
                                                                if isinstance(v, dict) and "when" in v))
                except Exception as e:  # noqa: BLE001
                    result["warnings"].append(f"Social-Posts fehlgeschlagen: {str(e)[:160]}")
            else:
                result["warnings"].append("Social-Posts übersprungen: METRICOOL_TOKEN fehlt")
        result["status"] = "ok"
        rc = 0
    except costs.BudgetExceeded as e:
        result.update({"status": "budget_exceeded", "error": str(e)})
        log(f"ABBRUCH: {e}")
        rc = 2
    except Exception as e:  # noqa: BLE001
        result.update({"status": "error", "error": str(e), "trace": traceback.format_exc()[-2000:]})
        log(f"FEHLER: {e}")
        rc = 1

    result.update({"cost_usd": costs.total_usd(), "cost_eur": costs.eur(costs.total_usd()),
                   "cost_report": costs.report(), "elapsed_min": (time.time() - t0) / 60,
                   "finished_utc": datetime.now(timezone.utc).isoformat()})
    (out / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    log(result["cost_report"])

    if args.mail and mail.available():
        try:
            subj = (f"[Kids-Short] {today} – {'online' if rc == 0 and result.get('url') else result['status']}")
            body = mail.report_text(result) if rc == 0 else f"Lauf {today}: {result['status']}\n\n{result.get('error', '')}\n\n{result['cost_report']}"
            mail.send(subj, body)
            log("Report-Mail gesendet")
        except Exception as e:  # noqa: BLE001
            log(f"Report-Mail fehlgeschlagen: {e}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
