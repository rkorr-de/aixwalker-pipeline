#!/usr/bin/env python3
"""Shorts 2.0 – alle 10 Beispiele aus den Kling-Clips zusammensetzen (Kaushan Script, 15 s, Originaltempo).

Clips aus Drive „AIX WALKER Mixe/_shorts_v2_kling“, Musik aus den Mix-Ordnern (mp3/), Ergebnis nach
„AIX WALKER Mixe/_shorts_v2_fertig“ (+ Kontaktbogen kontakt.jpg zur Sichtprüfung). Keine Kosten (nur Rechnen).

  python examples/shorts_v2/render_all.py [id ...]
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline import drive, shorts, shortsv2  # noqa: E402

OUT = ROOT / "build" / "shorts_v2_fertig"
CLIPS = ROOT / "build" / "shorts_v2_kling"
SPECS = json.loads((Path(__file__).parent / "specs.json").read_text(encoding="utf-8"))
# (Teil des Mix-Ordnernamens, Teil des Tracknamens)
MUSIC = {
    "Mediterranean Spa Lounge": [("Turquoise Horizon", "Nautical Twilight")],
    "Italian Chillout": [("Positano Glow", "Mandolin at Sunset"), ("Praiano Evening Lounge", "Dolce Piano Chords")],
    "Dark Ambient Spa": [("Bamboo Steam Spa", "Golden Hour Mist")],
    "Chillout Sleep": [("Starlight Slumber", "Muted Starlight")],
    "Cozy Winter Cabin": [("Cabin Embers", "Fireplace Glow")],
}


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def fetch_music(svc, root: str, folder_part: str, track_part: str) -> Path:
    dst = OUT / "music" / f"{folder_part}.mp3"
    if dst.exists():
        return dst
    folders = [f for f in drive.list_children(svc, root, folders=True) if folder_part in f["name"]]
    for f in folders:
        mp3 = [c for c in drive.list_children(svc, f["id"], folders=True) if c["name"] == "mp3"]
        for m in mp3:
            for c in drive.list_children(svc, m["id"], folders=False):
                if track_part in c["name"]:
                    return drive.download(svc, c["id"], dst)
    raise FileNotFoundError(f"Musik nicht gefunden: {folder_part} / {track_part}")


def main() -> int:
    only = sys.argv[1:]
    OUT.mkdir(parents=True, exist_ok=True)
    svc = drive.service()
    root = drive.ensure_folder(svc, drive.ROOT_FOLDER)
    src = drive.ensure_folder(svc, "_shorts_v2_kling", root)
    dst = drive.ensure_folder(svc, "_shorts_v2_fertig", root)
    have = {f["name"]: f["id"] for f in drive.list_children(svc, src, folders=False)}
    it, done, sheet = 0, [], []
    for s in SPECS:
        if only and s["id"] not in only:
            continue
        t0 = time.time()
        ids = [s["id"]] + ([s["id"] + "-b"] if s.get("split") else [])
        for cid in ids:
            p = CLIPS / f"{cid}.mp4"
            if not p.exists():
                if f"{cid}.mp4" not in have:
                    raise FileNotFoundError(f"Clip fehlt: {cid}.mp4")
                drive.download(svc, have[f"{cid}.mp4"], p)
        opts = MUSIC[s["mix"]]
        fp, tp = opts[it % len(opts)] if s["mix"] == "Italian Chillout" else opts[0]
        if s["mix"] == "Italian Chillout":
            it += 1
        mp3 = fetch_music(svc, root, fp, tp)
        wav = OUT / f"{s['id']}.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp3), "-ac", "2", "-ar", "44100", str(wav)], check=True)
        total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                      str(wav)], capture_output=True, text=True).stdout)
        start = shorts.find_passages(wav, [0.0], total, 20, 1)[0]["start"]
        out = OUT / f"Short2_{s['id']}.mp4"
        shortsv2.render(CLIPS / f"{s['id']}.mp4", s["beats"], s["mix"], wav, start, out,
                        clip_b=CLIPS / f"{s['id']}-b.mp4" if s.get("split") else None,
                        breathing=bool(s.get("breathing")),
                        labels=("Amalfi", "Lake Como") if s.get("split") else None)
        wav.unlink(missing_ok=True)
        drive._upload(svc, out, dst)
        done.append(out)
        for t in (1.5, 8.5, 13.5):     # Kontaktbogen: Satz 1, Satz 2, Schluss
            fr = OUT / f"_f_{s['id']}_{t}.jpg"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(out), "-frames:v", "1",
                            "-vf", "scale=270:480", str(fr)], check=True)
            sheet.append(fr)
        log(f"FERTIG {s['id']} ({round(time.time() - t0)} s)")
    if sheet:
        from PIL import Image
        cols = 6
        rows = (len(sheet) + cols - 1) // cols
        im = Image.new("RGB", (270 * cols, 480 * rows))
        for i, f in enumerate(sheet):
            im.paste(Image.open(f), ((i % cols) * 270, (i // cols) * 480))
        im.save(OUT / "kontakt.jpg", quality=85)
        drive._upload(svc, OUT / "kontakt.jpg", dst)
    log(f"ALLES FERTIG: {len(done)} Shorts, Ordner https://drive.google.com/drive/folders/{dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
