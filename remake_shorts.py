#!/usr/bin/env python3
"""Shorts eines schon veröffentlichten Mixes im aktuellen Short-Look neu bauen und hochladen (Rolf 11.10.2026).

    # 1) bauen + PRIVAT hochladen, Vorschau und Ergebnis landen im Drive-Ordner des Mixes
    python remake_shorts.py --folder-id <Drive-Ordner des Mixes> --concept-id <Drive-ID der concept.json> \
        --video-url https://youtu.be/<Mix-ID> --clip "01:13:08|Ultimate Infinity Pool|White Architecture" \
        --clip "01:32:54|Your Ocean Retreat|Coastal White"
    # 2) nach Sichtprüfung öffentlich schalten
    python remake_shorts.py --set-public <ID1> <ID2>

Hauptbild: master.jpg aus dem Drive-Ordner; fehlt es (ältere Mixe), wird es per KI aus album_3000.png zurückgeholt
(Schrift entfernt) und als master.jpg im Ordner abgelegt. Musik: Ausschnitt aus dem Mix-Video im Drive-Ordner.
Alte Shorts löscht dieses Skript NICHT – das macht Rolf selbst in YouTube Studio.
"""
import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image

from pipeline import config, drive, images, shorts, visuals, youtube


def secs(t: str) -> float:
    parts = [float(p) for p in t.strip().split(":")]
    return sum(p * 60 ** i for i, p in enumerate(reversed(parts)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder-id")
    ap.add_argument("--concept-id")
    ap.add_argument("--video-url", default="")
    ap.add_argument("--clip", action="append", default=[], help='"hh:mm:ss|Hook|Tracktitel"')
    ap.add_argument("--privacy", default="private")
    ap.add_argument("--out", default="build/remake_shorts")
    ap.add_argument("--set-public", nargs="*")
    args = ap.parse_args()

    if args.set_public:
        for vid in args.set_public:
            youtube.set_public(vid)
            print(f"ÖFFENTLICH: https://youtube.com/shorts/{vid}")
        return 0

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    svc = drive.service()
    kids = {f["name"]: f["id"] for f in drive.list_children(svc, args.folder_id, folders=False)}
    print("Drive-Ordner:", sorted(kids))
    concept = json.loads(drive.read_text(svc, args.concept_id))
    genre = concept.get("genre", "")

    # Hauptbild
    if "master.jpg" in kids:
        master = Image.open(drive.download(svc, kids["master.jpg"], out / "master.jpg")).convert("RGB")
        print("Hauptbild: master.jpg aus Drive")
    else:
        cover = Image.open(drive.download(svc, kids["album_3000.png"], out / "album_3000.png")).convert("RGB")
        master = images.remove_text(cover)
        master.save(out / "master.jpg", "JPEG", quality=92)
        drive._upload(svc, out / "master.jpg", args.folder_id)
        print(f"Hauptbild: aus album_3000.png zurückgeholt (Schrift entfernt), {master.size}, in Drive abgelegt")

    # Mix-Video (Tonspur)
    mp4_name = next(n for n in kids if n.endswith(".mp4"))
    mix = drive.download(svc, kids[mp4_name], out / mp4_name)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(mix)], capture_output=True, text=True, check=True).stdout)
    total_min = round(dur / 60)
    print(f"Mix: {mp4_name}, {total_min} Min")

    results, frames = [], []
    for k, spec in enumerate(args.clip):
        start_s, hook, track = [x.strip() for x in spec.split("|")]
        start = secs(start_s)
        end = start + config.SHORT_CLIP_SEC
        frame = shorts.make_short_frame(master, None, hook, track, out / f"short_{k + 1}_frame.png",
                                        total_min=total_min, album=concept["album"],
                                        keyword=config.THUMB_KEYWORD.get(genre), note=config.vocal_note(genre))
        clip = visuals.build_short_animated(frame, mix, start, end, out / f"short_{k + 1}.mp4")
        title, desc, tags = shorts.short_metadata({**concept, "total_min": total_min}, k,
                                                  {"start": start, "end": end}, track, hook, args.video_url)
        vid = youtube.upload_video(clip, title, desc, tags, privacy=args.privacy)
        try:
            youtube.set_thumbnail(vid, frame)
        except Exception as e:  # noqa: BLE001
            print(f"Short-Thumbnail nicht gesetzt: {e}")
        results.append({"video_id": vid, "url": f"https://youtube.com/shorts/{vid}", "title": title,
                        "privacy": args.privacy, "hook": hook, "start": start_s})
        frames.append(frame)
        print(f"Short {k + 1} hochgeladen ({args.privacy}): https://youtube.com/shorts/{vid} – {title}")

    # Vorschau (klein) + Ergebnis in den Drive-Ordner
    tiles = [Image.open(f).convert("RGB").resize((432, 768), Image.LANCZOS) for f in frames]
    sheet = Image.new("RGB", (len(tiles) * 444 + 12, 780), (20, 20, 20))
    for i, t in enumerate(tiles):
        sheet.paste(t, (12 + i * 444, 6))
    prev = out / "shorts_neu_vorschau.jpg"
    sheet.save(prev, "JPEG", quality=80)
    m_small = out / "master_vorschau.jpg"
    master.resize((512, 512), Image.LANCZOS).save(m_small, "JPEG", quality=80)
    for f in (prev, m_small):
        drive._upload(svc, f, args.folder_id)
    drive.write_text(svc, "shorts_neu.json", json.dumps(results, indent=2, ensure_ascii=False), args.folder_id)
    print("ERGEBNIS:", json.dumps(results, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
