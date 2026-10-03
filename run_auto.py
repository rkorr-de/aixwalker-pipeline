#!/usr/bin/env python3
"""Vollautomatischer Lauf (Dienstag + Freitag): Gedächtnis lesen → Mix planen → Konzept erzeugen → produzieren →
öffentlich auf YouTube (Mix + 2 Shorts) → Drive → Gedächtnis fortschreiben → Bericht per E-Mail.

  python run_auto.py                      # alles, ohne Rückfragen
  python run_auto.py --dry-run            # synthetisches Audio, prozedurale Bilder, kein Upload, kein Drive, keine Kosten
  python run_auto.py --private            # wie normal, aber Uploads privat
  python run_auto.py --concept concepts/x.json   # fertiges Konzept statt Planer
  python run_auto.py --genre "Slow Gym Beats"    # Genre erzwingen, Rest automatisch

Bricht ein Lauf ab, einfach denselben Befehl erneut starten: das Konzept des Tages (concepts/<datum>-*.json) und
fertige Tracks in build/<slug>/raw werden wiederverwendet.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from pipeline import config, costs, mailer, memory, planner


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] [auto] {msg}", flush=True)


def check_env(dry_run: bool) -> list[str]:
    need = ["GOOGLE_API_KEY", "YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN", "DRIVE_REFRESH_TOKEN",
            "GMAIL_REFRESH_TOKEN"]
    missing = [v for v in need if not os.environ.get(v)]
    if missing:
        log(f"fehlende Umgebungsvariablen: {missing}" + (" (dry-run: nur Hinweis)" if dry_run else ""))
    return missing


def todays_concept() -> Path | None:
    hits = sorted((config.ROOT / "concepts").glob(f"{date.today().isoformat()}-*.json"))
    return hits[-1] if hits else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--concept", default=None)
    ap.add_argument("--genre", default=None, choices=list(planner.GENRES))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--private", action="store_true", help="Uploads privat statt öffentlich")
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--seed", type=int, default=None, help="Zufall für die Planung festlegen (Tests)")
    args = ap.parse_args()
    use_drive = not args.dry_run and bool(os.environ.get("DRIVE_REFRESH_TOKEN"))
    missing = check_env(args.dry_run)

    # 1) Gedächtnis + Analytics
    mem = memory.load(use_drive=use_drive)
    log(f"Gedächtnis: {len(mem.get('mixes', []))} Mixe, Stand {mem.get('updated', 'Startwissen')}")
    rows, hours = [], None
    if not args.dry_run and os.environ.get("YT_REFRESH_TOKEN"):
        try:
            from pipeline import youtube
            hours = youtube.channel_watch_hours()
            rows = youtube.recent_performance(days=90)
            memory.record_analytics(mem, hours, rows)
            log(f"Analytics: {hours:.1f} Wiedergabestunden (365 Tage), {len(rows)} Videos mit Kennzahlen")
        except Exception as e:  # noqa: BLE001
            log(f"Analytics nicht verfügbar: {str(e)[:160]}")
            rows = (mem.get("analytics") or [{}])[-1].get("videos", [])

    # 2) Konzept: vorgegeben, vom heutigen Tag (Neustart) oder neu geplant
    concept_path = Path(args.concept) if args.concept else todays_concept()
    if concept_path:
        log(f"Konzept wird verwendet: {concept_path}")
        concept = json.loads(concept_path.read_text(encoding="utf-8"))
        brief = concept.get("_brief")
    else:
        brief = planner.choose_brief(mem, rows, seed=args.seed, force_genre=args.genre)
        log("Briefing:\n" + planner.brief_text(brief))
        concept = planner.generate_concept(mem, brief, log=log)
        concept["_brief"] = {k: v for k, v in brief.items() if k != "scores"}
        concept_path = planner.write_concept(concept)
        log(f"Konzept geschrieben: {concept_path}")
    slug = concept["slug"]
    out = config.ROOT / "build" / slug

    # 3) Kosten-Obergrenze (kein Mensch zum Freigeben → harte Grenze)
    est = costs.estimate(concept)
    limit = float(os.environ.get("BUDGET_MAX_USD", config.BUDGET_MAX_USD))
    log(f"Kostenvoranschlag {est['usd']:.2f} $ ≈ {est['eur']:.2f} € (Obergrenze {limit:.2f} $)")
    if est["usd"] > limit and not args.dry_run:
        log("ABBRUCH: Voranschlag über BUDGET_MAX_USD")
        return 2

    # 4) Produktion (Unterprozess, damit Neustart/Resume sauber funktioniert); ein automatischer Neuversuch
    cmd = [sys.executable, str(config.ROOT / "run_mix.py"), str(concept_path), "--out", str(out)]
    if args.dry_run:
        cmd.append("--dry-run")
    else:
        if not args.no_upload:
            cmd.append("--upload")
            if not args.private:
                cmd.append("--public")
        if use_drive:
            cmd.append("--drive")
    for attempt in (1, 2):
        log(f"Start run_mix (Versuch {attempt}): {' '.join(cmd[1:])}")
        rc = subprocess.call(cmd, cwd=config.ROOT)
        if rc == 0:
            break
        log(f"run_mix endete mit Code {rc}")
        time.sleep(30)
    else:
        log("ABBRUCH: Produktion zweimal fehlgeschlagen – Konzept und fertige Tracks bleiben für einen Neustart erhalten")
        return 3

    # 5) Prüfen
    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    problems = []
    if result.get("duration_min", 0) < config.MIN_MIX_MINUTES:
        problems.append(f"Dauer {result.get('duration_min')} Min < {config.MIN_MIX_MINUTES}")
    if not args.dry_run and not args.no_upload:
        if not result.get("video_id"):
            problems.append("kein Video hochgeladen")
        if len([s for s in result.get("shorts", []) if s.get("video_id")]) < config.SHORTS_COUNT:
            problems.append("weniger als 2 Shorts hochgeladen")
        if use_drive and "error" in (result.get("drive") or {}):
            problems.append("Drive-Ablage fehlgeschlagen")
    log("Prüfung: " + (", ".join(problems) if problems else "alles vorhanden"))

    # 6) Gedächtnis fortschreiben (auch bei Problemen, damit nichts doppelt produziert wird; nicht im Dry-Run)
    report_text = mailer.build_report(concept, result, est["usd"])
    if args.dry_run:
        log("Dry-Run: Gedächtnis wird nicht fortgeschrieben")
    else:
        entry = memory.record_mix(mem, concept, result)
        entry["problems"] = problems
        if problems:
            memory.add_learning(mem, f"{date.today().isoformat()} {concept['album']}: {'; '.join(problems)}")
        try:
            link = memory.save(mem, use_drive=use_drive, extra_files={
                f"{slug}.concept.json": json.dumps(concept, indent=2, ensure_ascii=False),
                f"{slug}.report.md": report_text})
            log(f"Gedächtnis gespeichert: {link or memory.LOCAL}")
        except Exception as e:  # noqa: BLE001
            log(f"Gedächtnis nicht in Drive gespeichert (lokal: {memory.LOCAL}): {str(e)[:160]}")

    # 7) Bericht per E-Mail
    mail = {"sent": False, "reason": "übersprungen"}
    if not args.no_email and not args.dry_run:
        try:
            mail = mailer.send_report(concept, result, out, est["usd"])
        except Exception as e:  # noqa: BLE001
            mail = {"sent": False, "reason": str(e)[:200], "file": str(out / "report.md")}
    else:
        (out / "report.md").write_text(report_text, encoding="utf-8")
        mail["file"] = str(out / "report.md")
    log(f"E-Mail: {mail}")

    summary = {"slug": slug, "album": concept["album"], "genre": concept["genre"], "bpm": concept["bpm"],
               "video_url": result.get("video_url"), "shorts": [s.get("url") for s in result.get("shorts", [])],
               "drive": (result.get("drive") or {}).get("_folder"), "duration_min": result.get("duration_min"),
               "cost_usd": result.get("cost_usd"), "estimate_usd": est["usd"], "problems": problems, "mail": mail,
               "missing_env": missing, "report": str(out / "report.md")}
    (out / "auto_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    log("Zusammenfassung:\n" + json.dumps(summary, indent=2, ensure_ascii=False))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
