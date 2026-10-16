#!/usr/bin/env python3
"""Shorts-Konzept 2.0 – Beispiel-Material erzeugen (Rolf 15.10.2026, 22:26).

Erzeugt für jedes Beispiel in specs.json ein Hochkant-Bild (Nano Banana Pro, 9:16) und daraus einen 8-s-Clip
(Veo 3.1 Fast, Bild-zu-Video, 1080p) und lädt alles nach Google Drive „AIX WALKER Mixe/_shorts_v2_beispiele“.
Harte Kostengrenze: 16 $ (KIDS_BUDGET_USD). Erwartet: ca. 11 Clips × 0,96 $ + 12 Bilder × 0,134 $ ≈ 12,20 $.

  python examples/shorts_v2/generate_assets.py
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

os.environ.setdefault("KIDS_BUDGET_USD", "16")
os.environ.setdefault("KIDS_MAX_CLIP_RETRIES", "1")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from kids import config as kconfig  # noqa: E402
from kids import costs as kcosts  # noqa: E402
from kids import veo  # noqa: E402
from pipeline import drive, images  # noqa: E402

# Für diese Beispiele: echte Menschen erwünscht – eigene Negativliste statt der Kids-Liste
kconfig.NEGATIVE_PROMPT = ("text, letters, captions, subtitles, watermark, logo, talking, lip sync, distorted face, "
                           "extra fingers, extra limbs, deformed hands, morphing, melting, scene cut, jump cut, "
                           "fast camera movement, shaky camera, flicker, glitch, cartoon, illustration")

OUT = ROOT / "build" / "shorts_v2"
SPECS = json.loads((Path(__file__).parent / "specs.json").read_text(encoding="utf-8"))


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def make(spec: dict, key: str, mkey: str, suffix: str) -> dict:
    sid = spec["id"] + suffix
    img_p = OUT / f"{sid}.png"
    clip_p = OUT / f"{sid}.mp4"
    res = {"id": sid, "image": None, "clip": None, "error": None}
    try:
        if not img_p.exists():
            img = images.generate_art(spec[key], aspect="9:16", pro=True, style="", image_size="2K")
            kcosts.count("image_pro")
            img.save(img_p)
            log(f"Bild fertig: {sid} {img.size}")
        res["image"] = str(img_p)
        if not clip_p.exists():
            from PIL import Image
            veo.generate_clip(spec[mkey] + " Photorealistic, natural motion, no text.", clip_p,
                              first_frame=Image.open(img_p).convert("RGB"))
            log(f"Clip fertig: {sid}")
        res["clip"] = str(clip_p)
    except Exception as e:  # noqa: BLE001
        res["error"] = str(e)[:300]
        log(f"FEHLER {sid}: {res['error']}")
    return res


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    kcosts.start(OUT / "costs.json")
    jobs = []
    for s in SPECS:
        jobs.append((s, "image", "motion", ""))
        if s.get("split"):
            jobs.append((s, "image_b", "motion_b", "-b"))
    with ThreadPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(lambda j: make(*j), jobs))
    (OUT / "manifest.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    log(f"Kosten: {kcosts.total_usd():.2f} $")

    svc = drive.service()
    root = drive.ensure_folder(svc, drive.ROOT_FOLDER)
    folder = drive.ensure_folder(svc, "_shorts_v2_beispiele", root)
    for f in sorted(OUT.glob("*")):
        if f.suffix in (".png", ".mp4", ".json"):
            drive._upload(svc, f, folder)
            log(f"Drive: {f.name}")
    ok = sum(1 for r in results if r["clip"])
    log(f"FERTIG: {ok}/{len(results)} Clips, Ordner https://drive.google.com/drive/folders/{folder}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
