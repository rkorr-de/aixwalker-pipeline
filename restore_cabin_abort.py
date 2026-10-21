#!/usr/bin/env python3
"""Nach einem Winter-Cabin-Kostenabbruch (Exit-Code 4): holt aus dem Drive-Ordner „… – ABGEBROCHEN (Clips zur Prüfung)“
das Konzept, die fertigen Tracks (raw/) und das Hauptbild zurück nach build/<slug>/, damit
  python run_auto.py --concept concepts/<slug>.json --clip <Rolfs-Clip.mp4>
den Film aus Rolfs eigenem (z. B. mit Gemini erzeugten) Clip baut – ohne neue Tracks, ohne Veo, ohne neues Bild.

  python restore_cabin_abort.py <slug> <Drive-Ordner-ID oder -Link>
"""
import re
import sys
from pathlib import Path

from pipeline import config, drive


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    slug = sys.argv[1]
    m = re.search(r"folders/([\w-]+)", sys.argv[2])
    folder = m.group(1) if m else sys.argv[2]
    svc = drive.service()
    out = config.ROOT / "build" / slug
    (out / "raw").mkdir(parents=True, exist_ok=True)
    (out / "img").mkdir(parents=True, exist_ok=True)
    (config.ROOT / "concepts").mkdir(exist_ok=True)
    got = {"tracks": 0}
    for f in drive.list_children(svc, folder):
        name, fid = f["name"], f["id"]
        if name.endswith(".concept.json") or name == f"{slug}.json":
            drive.download(svc, fid, config.ROOT / "concepts" / f"{slug}.json")
            got["concept"] = name
        elif name in ("frame_4k.png", "master.jpg"):
            drive.download(svc, fid, out / "img" / name)
            got[name] = True
        elif f.get("mimeType") == drive.FOLDER_MIME and name == "tracks":
            for t in drive.list_children(svc, fid):
                drive.download(svc, t["id"], out / "raw" / t["name"])
                got["tracks"] += 1
    print(got)
    if "concept" not in got:
        print("WARNUNG: kein Konzept im Ordner – aus Drive „_memory“ (<slug>.concept.json) holen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
