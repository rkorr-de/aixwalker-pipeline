#!/usr/bin/env python3
"""Shorts 2.0 erzeugen und veröffentlichen (Rolf 15./16.10.2026) – ersetzt die Tipp-Shorts.

Ein Short = Personen-Bild (Nano Banana Pro) → 15-s-Clip am Stück (Kling 3.0 Standard, ruckelfrei) → Text in
Kaushan Script, der sich Wort für Wort aufbaut → Schluss „Full 1-hour <Genre> mix ↓“ → Musik aus dem Ziel-Mix.

  python run_short_v2.py                       # nächster offener Eintrag der Warteschlange → öffentlich
  python run_short_v2.py --genre "Italian Chillout"   # nächster offener Eintrag dieses Genres
  python run_short_v2.py --id 03-breathe       # genau dieser Eintrag
  python run_short_v2.py --free-only --publish-at 16:00   # Routine: nur bezahlte Clips, öffentlich um 16 Uhr
  python run_short_v2.py --dry-run             # ohne API/Upload: Platzhalter-Clip, synthetische Musik
  python run_short_v2.py --add neue.json       # Einträge prüfen und an die Warteschlange (Drive) anhängen
  python run_short_v2.py --list                # Warteschlange anzeigen

Warteschlange: Drive „AIX WALKER Mixe/_memory/shorts2_queue.json“ (Start: examples/shorts_v2/specs.json +
metadata.json). Liegt für den Eintrag schon ein Clip in Drive „_shorts_v2_kling“ (die 10 freigegebenen Beispiele),
wird er wiederverwendet – keine Kosten. Sonst ca. 1,40 $ (Bild 0,134 $ + 15 s Kling 1,26 $), A/B-Format ca. 2,80 $.
Harte Grenze je Lauf: 3,50 $.
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

os.environ.setdefault("KIDS_BUDGET_USD", "3.5")
os.environ["KIDS_KLING_TIER"] = "standard"

from pipeline import config, memory, shorts, shortsv2  # noqa: E402

EX = config.ROOT / "examples" / "shorts_v2"
QUEUE_NAME = "shorts2_queue.json"
LOCAL_QUEUE = config.ROOT / "build" / QUEUE_NAME
CLIP_FOLDER = "_shorts_v2_kling"
GROUP = {"Chillout Sleep": ("Chillout Sleep", "Dark Ambient Spa", "Mediterranean Spa Lounge"),
         "Dark Ambient Spa": ("Dark Ambient Spa", "Mediterranean Spa Lounge", "Chillout Sleep"),
         "Mediterranean Spa Lounge": ("Mediterranean Spa Lounge", "Italian Chillout", "Dark Ambient Spa"),
         "Italian Chillout": ("Italian Chillout",),
         "Cozy Winter Cabin": ("Cozy Winter Cabin",)}
NEGATIVE = ("text, letters, captions, subtitles, watermark, logo, talking, lip sync, distorted face, extra fingers, "
            "extra limbs, deformed hands, morphing, melting, scene cut, jump cut, fast camera movement, shaky camera, "
            "flicker, glitch, cartoon, illustration, oversaturated")
MOTION_SUFFIX = (" Very slow, smooth and steady camera movement, natural gentle motion, photorealistic, consistent "
                 "faces and bodies, no cuts, one continuous 15-second shot, no text.")
REQUIRED = ("id", "mix", "beats", "image", "motion", "title", "description", "tags")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] [short2] {msg}", flush=True)


# ---------------------------------------------------------------- Warteschlange

def seed() -> list[dict]:
    specs = json.loads((EX / "specs.json").read_text(encoding="utf-8"))
    meta = {m["id"]: m for m in json.loads((EX / "metadata.json").read_text(encoding="utf-8"))["shorts"]}
    out = []
    for s in specs:
        e = {**s, **{k: meta.get(s["id"], {}).get(k) for k in ("title", "description", "tags")}}
        if s.get("split"):
            e.setdefault("labels", ["Amalfi", "Lake Como"])
        out.append(e)
    return out


def validate(e: dict) -> list[str]:
    p = [f"fehlt: {k}" for k in REQUIRED if not e.get(k)]
    if p:
        return p
    if not 1 <= len(e["beats"]) <= 2:
        p.append("1–2 Sätze (beats)")
    for b in e["beats"]:
        if len(b.replace("*", "")) > 46:
            p.append(f"Satz zu lang: {b}")
    if e["mix"] not in GROUP:
        p.append(f"unbekanntes Genre: {e['mix']}")
    if len(e["title"]) > 90:
        p.append("Titel zu lang")
    if e.get("split") and not (e.get("image_b") and e.get("motion_b")):
        p.append("A/B-Format braucht image_b und motion_b")
    return p


def _drive_folder():
    from pipeline import drive
    svc = drive.service()
    return drive, svc, drive.memory_folder(svc)


def load_queue(use_drive: bool) -> list[dict]:
    if use_drive:
        drive, svc, folder = _drive_folder()
        fid = drive.find_file(svc, QUEUE_NAME, folder)
        if fid:
            return json.loads(drive.read_text(svc, fid))
    elif LOCAL_QUEUE.exists():
        return json.loads(LOCAL_QUEUE.read_text(encoding="utf-8"))
    return seed()


def save_queue(queue: list[dict], use_drive: bool) -> None:
    text = json.dumps(queue, indent=2, ensure_ascii=False)
    if use_drive:
        drive, svc, folder = _drive_folder()
        drive.write_text(svc, QUEUE_NAME, text, folder)
    else:
        LOCAL_QUEUE.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_QUEUE.write_text(text, encoding="utf-8")


def next_entry(queue: list[dict], genre: str | None, eid: str | None) -> dict | None:
    for e in queue:
        if e.get("used"):
            continue
        if eid and e["id"] != eid:
            continue
        if genre and e["mix"] != genre:
            continue
        return e
    return None


# ---------------------------------------------------------------- Material

def pick_mix(mem: dict, genre: str) -> dict | None:
    mixes = [m for m in mem.get("mixes", []) if m.get("video_id") and m.get("drive")]
    for g in GROUP.get(genre, (genre,)):
        hits = [m for m in mixes if m.get("genre") == g and (m.get("duration_min") or 0) >= 30]
        if hits:
            return hits[-1]
    return None


def fetch_track(mix: dict, out: Path, seed_: str) -> Path:
    from pipeline import drive
    svc = drive.service()
    folder = mix["drive"].rstrip("/").rsplit("/", 1)[-1]
    sub = next((f for f in drive.list_children(svc, folder, folders=True) if f["name"] == "mp3"), None)
    mp3s = [f for f in drive.list_children(svc, sub["id"], folders=False)
            if f["name"].lower().endswith(".mp3")] if sub else []
    if not mp3s:
        raise RuntimeError(f"keine MP3s in {mix['drive']}")
    f = random.Random(seed_).choice(mp3s)
    mp3 = drive.download(svc, f["id"], out / "track.mp3")
    wav = out / "track.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp3), "-ac", "2", "-ar", "44100", str(wav)], check=True)
    log(f"Musik: {f['name']} aus „{mix.get('album')}“")
    return wav


def get_clip(e: dict, suffix: str, out: Path, dry: bool) -> Path:
    """Vorhandenen Clip aus Drive wiederverwenden, sonst Bild + Kling neu erzeugen."""
    cid = e["id"] + suffix
    clip = out / f"{cid}.mp4"
    if clip.exists():
        return clip
    if dry:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "gradients=s=1080x1920:d=15:speed=0.004:c0=0x1d2a4a:c1=0xd98c6a,format=yuv420p",
                        "-t", "15", "-r", "24", str(clip)], check=True)
        return clip
    from pipeline import drive
    svc = drive.service()
    root = drive.ensure_folder(svc, drive.ROOT_FOLDER)
    folder = drive.ensure_folder(svc, CLIP_FOLDER, root)
    have = {f["name"]: f["id"] for f in drive.list_children(svc, folder, folders=False)}
    if f"{cid}.mp4" in have:
        log(f"Clip {cid} schon vorhanden (bezahlt) – wird wiederverwendet")
        return drive.download(svc, have[f"{cid}.mp4"], clip)
    from kids import config as kconfig
    from kids import costs as kcosts
    from kids import fal
    from pipeline import images
    kconfig.NEGATIVE_PROMPT = NEGATIVE
    img = images.generate_art(e["image" + ("_b" if suffix else "")], aspect="9:16", pro=True, style="",
                              image_size="2K")
    kcosts.count("image_pro")
    img.save(out / f"{cid}.png")
    fal.kling_clip(e["motion" + ("_b" if suffix else "")] + MOTION_SUFFIX, img.convert("RGB"), clip, seconds=15,
                   tier="standard")
    log(f"Neuer Clip erzeugt: {cid}")
    for f in (clip, out / f"{cid}.png"):        # für spätere Wiederverwendung ablegen
        drive._upload(svc, f, folder)
    return clip


def prepaid(e: dict) -> bool:
    """Liegen alle Clips des Eintrags schon (bezahlt) in Drive?"""
    from pipeline import drive
    svc = drive.service()
    folder = drive.ensure_folder(svc, CLIP_FOLDER, drive.ensure_folder(svc, drive.ROOT_FOLDER))
    have = {f["name"] for f in drive.list_children(svc, folder, folders=False)}
    need = [e["id"]] + ([e["id"] + "-b"] if e.get("split") else [])
    return all(f"{c}.mp4" in have for c in need)


def publish_time(hhmm: str | None) -> str | None:
    """„16:00“ → RFC3339 (UTC) für heute in Berlin; liegt die Zeit < 15 Min. in der Zukunft: None (sofort)."""
    if not hhmm:
        return None
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo
    h, m = (int(x) for x in hhmm.split(":"))
    now = datetime.now(ZoneInfo("Europe/Berlin"))
    at = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if at - now < timedelta(minutes=15):
        return None
    return at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def upload_drive(out: Path, e: dict, files: list[Path]) -> str:
    from pipeline import drive
    svc = drive.service()
    root = drive.ensure_folder(svc, drive.ROOT_FOLDER)
    base = drive.ensure_folder(svc, "_shorts2", root)
    folder = drive.ensure_folder(svc, f"{date.today().isoformat()} – {e['id']}", base)
    for f in files:
        drive._upload(svc, f, folder)
    return f"https://drive.google.com/drive/folders/{folder}"


# ---------------------------------------------------------------- Lauf

def produce(args) -> int:
    use_drive = not args.dry_run and bool(os.environ.get("DRIVE_REFRESH_TOKEN"))
    queue = load_queue(use_drive)
    e = next_entry(queue, args.genre, args.id)
    if not e:
        log("Keine offenen Einträge in der Warteschlange – heute kein Short (keine Kosten).")
        return 0
    probs = validate(e)
    if probs:
        log(f"Eintrag {e['id']} ungültig ({'; '.join(probs)}) – übersprungen und markiert")
        e["used"] = f"skipped {date.today().isoformat()}"
        save_queue(queue, use_drive)
        return 1
    out = config.ROOT / "build" / "shorts2" / f"{date.today().isoformat()}-{e['id']}"
    out.mkdir(parents=True, exist_ok=True)
    from kids import costs as kcosts
    kcosts.start(out / "costs.json")
    log(f"Eintrag: {e['id']} – „{' / '.join(e['beats'])}“ (Genre {e['mix']})")

    mem = memory.load(use_drive=use_drive)
    mix = pick_mix(mem, e["mix"])
    log(f"Ziel-Mix: {mix.get('yt_title') if mix else '(keiner gefunden – Link auf den Kanal)'}")

    if args.dry_run or not mix:
        from run_mix import synthetic_track
        wav = synthetic_track(out / "track.wav", 70, 80, 7)
    else:
        wav = fetch_track(mix, out, e["id"])
    total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                  str(wav)], capture_output=True, text=True, check=True).stdout)
    try:
        start = shorts.find_passages(wav, [0.0], total, 20, 1)[0]["start"]
    except Exception as ex:  # noqa: BLE001
        log(f"Passagensuche fehlgeschlagen ({ex}) – Start bei 20 s")
        start = min(20.0, max(0.0, total - 21))

    if args.free_only and not args.dry_run and not prepaid(e):
        log(f"Nächster Eintrag {e['id']} hätte keinen bezahlten Clip – heute kein Short (--free-only, keine Kosten). "
            f"Rolf muss neue Shorts (ca. 1,40 $ je Stück) erst freigeben.")
        return 0
    clip_a = get_clip(e, "", out, args.dry_run)
    clip_b = get_clip(e, "-b", out, args.dry_run) if e.get("split") else None
    video = shortsv2.render(clip_a, e["beats"], e["mix"], wav, start, out / f"Short2_{e['id']}.mp4", clip_b=clip_b,
                            breathing=bool(e.get("breathing")),
                            labels=tuple(e["labels"]) if e.get("split") and e.get("labels") else None)

    mix_url = f"https://youtu.be/{mix['video_id']}" if mix else "https://www.youtube.com/@aixwalker"
    title, desc = e["title"], e["description"].replace("{MIX_URL}", mix_url)
    tags = [t.strip() for t in e["tags"].split(",") if t.strip()]
    (out / "metadata.txt").write_text(f"{title}\n\n{desc}\n\nTags: {', '.join(tags)}\n\n"
                                      f"Related Video (manuell in Studio setzen): {mix_url}\n", encoding="utf-8")
    result = {"id": e["id"], "title": title, "file": str(video), "mix_video_id": (mix or {}).get("video_id"),
              "video_id": None, "url": None, "drive": None}

    if not args.dry_run and not args.no_upload and os.environ.get("YT_REFRESH_TOKEN"):
        from pipeline import youtube
        privacy = "private" if args.private else "public"
        at = None if args.private else publish_time(args.publish_at)
        vid = youtube.upload_video(video, title, desc, tags, category_id="10", privacy=privacy, ai_generated=True,
                                   publish_at=at)
        result["video_id"], result["url"], result["publish_at"] = vid, f"https://youtube.com/shorts/{vid}", at
        log(f"Hochgeladen ({'geplant ' + at if at else privacy}, KI-gekennzeichnet): {result['url']}")
    if use_drive:
        try:
            result["drive"] = upload_drive(out, e, [video, out / "metadata.txt"])
            log(f"Drive: {result['drive']}")
        except Exception as ex:  # noqa: BLE001
            log(f"Drive-Ablage fehlgeschlagen: {str(ex)[:160]}")
    result["cost_usd"] = round(kcosts.total_usd(), 3)
    log(f"Kosten: {result['cost_usd']} $")

    if not args.dry_run:
        if result["video_id"] or args.no_upload:
            e["used"], e["video_id"] = date.today().isoformat(), result["video_id"]
            save_queue(queue, use_drive)
        mem.setdefault("shorts2", []).append({"date": date.today().isoformat(), **{k: result[k] for k in (
            "id", "title", "video_id", "mix_video_id", "cost_usd")}})
        try:
            memory.save(mem, use_drive=use_drive)
        except Exception as ex:  # noqa: BLE001
            log(f"Gedächtnis nicht gespeichert: {str(ex)[:160]}")
    (out / "summary.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    left = sum(1 for x in queue if not x.get("used"))
    log(f"Fertig. Noch {left} offene Einträge.\n" + json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if (result["video_id"] or args.dry_run or args.no_upload) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--genre", default=None)
    ap.add_argument("--id", default=None)
    ap.add_argument("--add", default=None, help="JSON-Datei mit neuen Einträgen (Liste)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--private", action="store_true")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--free-only", action="store_true", help="nur Einträge mit schon bezahltem Clip (keine Kosten)")
    ap.add_argument("--publish-at", default=None, help="Uhrzeit Berlin, z. B. 16:00 (geplant veröffentlichen)")
    args = ap.parse_args()
    use_drive = not args.dry_run and bool(os.environ.get("DRIVE_REFRESH_TOKEN"))
    if args.add:
        queue = load_queue(use_drive)
        known = {x["id"] for x in queue}
        new = json.loads(Path(args.add).read_text(encoding="utf-8"))
        n = 0
        for x in new if isinstance(new, list) else [new]:
            probs = validate(x) + (["id schon vorhanden"] if x.get("id") in known else [])
            if probs:
                log(f"übersprungen {x.get('id')}: {'; '.join(probs)}")
                continue
            queue.append(x)
            known.add(x["id"])
            n += 1
        if n:
            save_queue(queue, use_drive)
        log(f"{n} Einträge angehängt; offen: {sum(1 for x in queue if not x.get('used'))}")
        return 0
    if args.list:
        for x in load_queue(use_drive):
            print(f"{x.get('used') or 'offen':>12}  {x['mix']:<26}  {x['id']:<24}  {' / '.join(x['beats'])}")
        return 0
    return produce(args)


if __name__ == "__main__":
    sys.exit(main())
