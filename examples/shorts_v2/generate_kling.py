#!/usr/bin/env python3
"""Shorts 2.0 – ruckelfreie Clips mit Kling 3.0 Standard, 15 s am Stück (Rolf 15.10.2026, 23:57).

Statt Veo 8 s + Zeitlupe (ruckelt) kommt jeder Clip in voller Short-Länge direkt aus Kling – keine Interpolation nötig.
Startbilder: die freigegebenen Bilder aus Drive „AIX WALKER Mixe/_shorts_v2_beispiele“; Bild 02 (Paar) wird neu
erzeugt mit natürlichem, romantischem rot-rosa Sonnenuntergang. Ergebnis nach Drive „_shorts_v2_kling“.
Kosten: 11 × 15 s × 0,084 $ + 1 Bild × 0,134 $ ≈ 14,00 $; harte Grenze 16 $.

  python examples/shorts_v2/generate_kling.py
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

os.environ.setdefault("KIDS_BUDGET_USD", "16")
os.environ["KIDS_KLING_TIER"] = "standard"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from kids import config as kconfig  # noqa: E402
from kids import costs as kcosts  # noqa: E402
from kids import fal  # noqa: E402
from pipeline import drive, images  # noqa: E402

kconfig.NEGATIVE_PROMPT = ("text, letters, captions, subtitles, watermark, logo, talking, lip sync, distorted face, "
                           "extra fingers, extra limbs, deformed hands, morphing, melting, scene cut, jump cut, "
                           "fast camera movement, shaky camera, flicker, glitch, cartoon, illustration, oversaturated")
OUT = ROOT / "build" / "shorts_v2_kling"
SPECS = json.loads((Path(__file__).parent / "specs.json").read_text(encoding="utf-8"))
NEW_IMAGE = {"02-send-couple"}          # diese Startbilder neu erzeugen
SUFFIX = (" Very slow, smooth and steady camera movement, natural gentle motion, photorealistic, consistent faces "
          "and bodies, no cuts, one continuous 15-second shot, no text.")


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    kcosts.start(OUT / "costs.json")
    svc = drive.service()
    root = drive.ensure_folder(svc, drive.ROOT_FOLDER)
    src = drive.ensure_folder(svc, "_shorts_v2_beispiele", root)
    dst = drive.ensure_folder(svc, "_shorts_v2_kling", root)
    have = {f["name"]: f["id"] for f in drive.list_children(svc, src)}

    jobs = []
    for s in SPECS:
        jobs.append((s, s["id"], "image", "motion"))
        if s.get("split"):
            jobs.append((s, s["id"] + "-b", "image_b", "motion_b"))

    # Startbilder bereitstellen (seriell: Drive-Client ist nicht threadsicher)
    for s, sid, ikey, _ in jobs:
        img_p = OUT / f"{sid}.png"
        if img_p.exists():
            continue
        if s["id"] in NEW_IMAGE and ikey == "image":
            img = images.generate_art(s[ikey], aspect="9:16", pro=True, style="", image_size="2K")
            kcosts.count("image_pro")
            img.save(img_p)
            log(f"Neues Bild: {sid} {img.size}")
        elif f"{sid}.png" in have:
            drive.download(svc, have[f"{sid}.png"], img_p)
            log(f"Bild aus Drive: {sid}")
        else:
            log(f"FEHLT: {sid}.png")

    def make(job):
        s, sid, ikey, mkey = job
        img_p, clip_p = OUT / f"{sid}.png", OUT / f"{sid}.mp4"
        res = {"id": sid, "clip": None, "error": None}
        try:
            if not clip_p.exists():
                from PIL import Image
                fal.kling_clip(s[mkey] + SUFFIX, Image.open(img_p).convert("RGB"), clip_p, seconds=15,
                               tier="standard")
                log(f"Clip fertig: {sid}")
            res["clip"] = str(clip_p)
        except Exception as e:  # noqa: BLE001
            res["error"] = str(e)[:300]
            log(f"FEHLER {sid}: {res['error']}")
        return res

    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(make, jobs))
    (OUT / "manifest.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    log(f"Kosten: {kcosts.total_usd():.2f} $")
    for f in sorted(OUT.glob("*")):
        if f.suffix in (".mp4", ".json") or f.stem in NEW_IMAGE:
            drive._upload(svc, f, dst)
            log(f"Drive: {f.name}")
    ok = sum(1 for r in results if r["clip"])
    log(f"FERTIG: {ok}/{len(results)} Clips, Ordner https://drive.google.com/drive/folders/{dst}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
