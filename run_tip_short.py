#!/usr/bin/env python3
"""Tipp-Short erzeugen und veröffentlichen (Wachstumsplan 2026/27, Säulen 2 + 3, Rolf 15.10.2026).

  python run_tip_short.py --kind wellness      # nächster „Sleep & Relax“-Tipp → Short → öffentlich auf AIX WALKER
  python run_tip_short.py --kind dolcevita     # nächster „Dolce Vita“-Ort → Short → öffentlich
  python run_tip_short.py --kind wellness --dry-run   # prozedurales Bild, synthetische Musik, kein Upload/Drive
  python run_tip_short.py --add neue_tipps.json       # Einträge prüfen und an die Warteschlange (Drive) anhängen
  python run_tip_short.py --list                      # Warteschlange anzeigen

Musik: ein Track aus dem neuesten Mix des Eintrags („music_genre“) aus Drive; der Short verlinkt genau diesen Mix.
Kosten: ein Nano-Banana-Bild (ca. 0,04 $). Ist die Warteschlange leer, endet der Lauf sofort ohne Kosten.
"""
import argparse
import json
import os
import random
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from pipeline import config, costs, images, memory, shorts, tipcalm, tipshorts

CLIP_SEC = 25
GROUP = {"Chillout Sleep": ("Chillout Sleep", "Dark Ambient Spa", "Mediterranean Spa Lounge"),
         "Dark Ambient Spa": ("Dark Ambient Spa", "Mediterranean Spa Lounge", "Chillout Sleep"),
         "Mediterranean Spa Lounge": ("Mediterranean Spa Lounge", "Dark Ambient Spa", "Chillout Sleep"),
         "Italian Chillout": ("Italian Chillout",)}
CATEGORY = {"wellness": "26", "dolcevita": "19"}   # Howto & Style · Travel & Events


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] [tip] {msg}", flush=True)


def pick_mix(mem: dict, genre: str) -> dict | None:
    """Neuester veröffentlichter Mix (mit Video-ID und Drive-Ordner) des Genres, sonst eines verwandten Genres."""
    mixes = [m for m in mem.get("mixes", []) if m.get("video_id") and m.get("drive")]
    for g in GROUP.get(genre, (genre,)):
        hits = [m for m in mixes if m.get("genre") == g and (m.get("duration_min") or 0) >= 30]
        if hits:
            return hits[-1]
    return None


def fetch_track(mix: dict, out: Path, seed: str) -> Path:
    """Lädt einen zufälligen (aber je Eintrag festen) Track aus mp3/ des Mix-Ordners und wandelt ihn in WAV."""
    from pipeline import drive
    svc = drive.service()
    folder = mix["drive"].rstrip("/").rsplit("/", 1)[-1]
    sub = next((f for f in drive.list_children(svc, folder, folders=True) if f["name"] == "mp3"), None)
    if not sub:
        raise RuntimeError(f"kein mp3-Ordner in {mix['drive']}")
    mp3s = [f for f in drive.list_children(svc, sub["id"], folders=False) if f["name"].lower().endswith(".mp3")]
    if not mp3s:
        raise RuntimeError(f"keine MP3s in {mix['drive']}")
    f = random.Random(seed).choice(mp3s)
    mp3 = drive.download(svc, f["id"], out / "track.mp3")
    wav = out / "track.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp3), "-ac", "2", "-ar", "44100", str(wav)], check=True)
    log(f"Musik: {f['name']} aus „{mix.get('album')}“")
    return wav


def duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def upload_drive(out: Path, entry: dict, files: list[Path]) -> str:
    from pipeline import drive
    svc = drive.service()
    root = drive.ensure_folder(svc, drive.ROOT_FOLDER)
    base = drive.ensure_folder(svc, "_tip_shorts", root)
    folder = drive.ensure_folder(svc, f"{date.today().isoformat()} – {entry['id']}", base)
    for f in files:
        drive._upload(svc, f, folder)
    return f"https://drive.google.com/drive/folders/{folder}"


def produce(kind: str, args) -> int:
    use_drive = not args.dry_run and bool(os.environ.get("DRIVE_REFRESH_TOKEN"))
    queue = tipshorts.load_queue(use_drive)
    entry = tipshorts.next_entry(queue, kind)
    if not entry:
        log(f"Warteschlange für „{kind}“ ist leer – heute kein Tipp-Short (keine Kosten). "
            f"Die Sonntags-Recherche füllt sie wieder auf.")
        return 0
    probs = tipshorts.validate_entry(entry)
    if probs:
        log(f"Eintrag {entry['id']} ungültig ({'; '.join(probs)}) – wird übersprungen und markiert")
        entry["used"] = f"skipped {date.today().isoformat()}"
        tipshorts.save_queue(queue, use_drive)
        return 1
    out = config.ROOT / "build" / "tips" / f"{date.today().isoformat()}-{entry['id']}"
    out.mkdir(parents=True, exist_ok=True)
    costs.start(out / "costs.json")
    log(f"Eintrag: {entry['id']} – „{entry['hook']}“ (Musik/Ziel: {entry['music_genre']})")

    mem = memory.load(use_drive=use_drive)
    mix = pick_mix(mem, entry["music_genre"])
    log(f"Ziel-Mix: {mix.get('yt_title') if mix else '(keiner gefunden – Link auf den Kanal)'}")

    # Musik
    if args.dry_run or not mix:
        from run_mix import synthetic_track
        wav = synthetic_track(out / "track.wav", 70, 80, 7)
    else:
        wav = fetch_track(mix, out, entry["id"])
    total = duration(wav)

    def passage(sec: float) -> float:
        try:
            return shorts.find_passages(wav, [0.0], total, int(sec) + 1, 1)[0]["start"]
        except Exception as e:  # noqa: BLE001
            log(f"Passagensuche fehlgeschlagen ({e}) – Start bei 20 s")
            return min(20.0, max(0.0, total - sec - 1))

    # Bild (9:16, Stil des Ziel-Genres; Italien mit sanftem Orange-&-Teal-Look)
    style = images.style_for(entry["music_genre"])
    if args.dry_run:
        art = images.procedural_art("9:16", seed=7)
    else:
        art = images.generate_art(entry["scene"] + " Vertical 9:16 composition, calm and uncluttered in the middle, "
                                  "cinematic, inviting, peaceful.", aspect="9:16", style=style)
    art = images.color_grade(art, entry["music_genre"])
    art.save(out / "art.jpg", quality=92)

    # Video im RUHIGEN Wellness-Look (Rolf 15.10.2026, 21:57: „chillig, schön, zum Betrachten einladen“) –
    # ein Text nach dem anderen, je ~6 s, Cinzel/Manrope, sanfte Kamerafahrt, Atem-Kreis bei Box-Atmung
    clip_path = out / f"{entry['id']}.mp4"
    try:
        built = tipcalm.build(art, entry, out / "layers", album=(mix or {}).get("album"))
        frame = built["preview"]
        clip = tipcalm.render(built, wav, passage(built["dur"]), clip_path)
    except Exception as e:  # noqa: BLE001 – im Zweifel der einfache Standbild-Short statt gar keiner
        log(f"Ruhiger Short fehlgeschlagen ({str(e)[:200]}); Fallback auf Standbild-Short")
        start = passage(CLIP_SEC)
        frame = tipshorts.make_tip_frame(art, entry["label"], entry["hook"], entry["lines"], out / "frame.png")
        clip = shorts.build_short(frame, wav, start, start + CLIP_SEC, clip_path)

    title = tipshorts.short_title(entry)
    desc = tipshorts.short_description(entry, mix)
    tags = tipshorts.TAGS[kind]
    (out / "metadata.txt").write_text(f"{title}\n\n{desc}\n\nTags: {', '.join(tags)}\n", encoding="utf-8")
    result = {"id": entry["id"], "kind": kind, "hook": entry["hook"], "title": title, "file": str(clip),
              "mix_video_id": (mix or {}).get("video_id"), "video_id": None, "url": None, "drive": None}

    if not args.dry_run and not args.no_upload and os.environ.get("YT_REFRESH_TOKEN"):
        from pipeline import youtube
        privacy = "private" if args.private else "public"
        vid = youtube.upload_video(clip, title, desc, tags, category_id=CATEGORY[kind], privacy=privacy,
                                   ai_generated=True)
        result["video_id"], result["url"] = vid, f"https://youtube.com/shorts/{vid}"
        log(f"Hochgeladen ({privacy}, KI-gekennzeichnet): {result['url']}")
    if use_drive:
        try:
            result["drive"] = upload_drive(out, entry, [clip, frame, out / "metadata.txt"])
            log(f"Drive: {result['drive']}")
        except Exception as e:  # noqa: BLE001
            log(f"Drive-Ablage fehlgeschlagen: {str(e)[:160]}")
    result["cost_usd"] = costs.total_usd()
    log(costs.report())

    if not args.dry_run:
        if result["video_id"] or args.no_upload:
            entry["used"] = date.today().isoformat()
            entry["video_id"] = result["video_id"]
            tipshorts.save_queue(queue, use_drive)
        mem.setdefault("tip_shorts", []).append({"date": date.today().isoformat(), **{k: result[k] for k in (
            "id", "kind", "hook", "title", "video_id", "mix_video_id", "cost_usd")}})
        try:
            memory.save(mem, use_drive=use_drive)
        except Exception as e:  # noqa: BLE001
            log(f"Gedächtnis nicht gespeichert: {str(e)[:160]}")
    (out / "summary.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    left = sum(1 for e in queue if e.get("kind") == kind and not e.get("used"))
    log(f"Fertig. Noch {left} „{kind}“-Einträge in der Warteschlange.\n" + json.dumps(result, indent=2,
                                                                                         ensure_ascii=False))
    return 0 if (result["video_id"] or args.dry_run or args.no_upload) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=tipshorts.KINDS)
    ap.add_argument("--add", default=None, help="JSON-Datei mit neuen Einträgen (Liste) an die Warteschlange hängen")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--private", action="store_true")
    ap.add_argument("--no-upload", action="store_true")
    args = ap.parse_args()
    use_drive = not args.dry_run and bool(os.environ.get("DRIVE_REFRESH_TOKEN"))
    if args.add:
        queue = tipshorts.load_queue(use_drive)
        new = json.loads(Path(args.add).read_text(encoding="utf-8"))
        n, msgs = tipshorts.add_entries(queue, new if isinstance(new, list) else [new])
        for m in msgs:
            log(m)
        if n:
            tipshorts.save_queue(queue, use_drive)
        log(f"{n} Einträge angehängt; offen: " + ", ".join(
            f"{k} {sum(1 for e in queue if e.get('kind') == k and not e.get('used'))}" for k in tipshorts.KINDS))
        return 0
    if args.list:
        for e in tipshorts.load_queue(use_drive):
            print(f"{e.get('used') or 'offen':>12}  {e['kind']:<9}  {e['id']:<34}  {e['hook']}")
        return 0
    if not args.kind:
        ap.error("--kind, --add oder --list angeben")
    return produce(args.kind, args)


if __name__ == "__main__":
    sys.exit(main())
