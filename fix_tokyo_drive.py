"""Einmalig: DistroKid-Paket für den Tokyo-Mix v2 im Drive vervollständigen (Rolf 18.10.2026, autark).

1. 22 MP3s aus dem v1-Ordner per Drive-Kopie (serverseitig) in v2/mp3 – vorher Abgleich der Namen mit den Kapiteln.
2. album_3000.png (3000x3000) aus album_cover.jpg erzeugen und in den v2-Ordner legen.
3. metadata.txt im v2-Ordner aktualisieren (neuer Titel, neuer Pin-Kommentar).
4. v2-Ordner umbenennen, so dass er auf "(Genre, BPM)" endet (Format wie alle anderen Mix-Ordner).
Ergebnis: build/fix_tokyo_drive.json
"""
import json
import re
import sys
from pathlib import Path

from PIL import Image

from pipeline import drive

HERE = Path(__file__).parent
V2 = "18L04N_HDO4cBLTlJFtlwmHdXaDQRCaAE"      # Mix-Ordner v2
V2_MP3 = "1KQ22CSgwTq3ZnH2r7uycCsr70NUaHexT"  # v2/mp3 (leer)
V1_MP3 = "1eAAToZGgei8J1DrhWaKHOzIZuBMB0UHR"  # v1/mp3 (22 MP3s)
FOLDER_NAME = "2026-10-18 – Tokyo Work Lounge – shinjuku-sky-loft v2 (Slow Jazz, 70 BPM)"
SRC = HERE / "concepts" / "tokyo-mix-1" / "v2"
out = {"steps": []}


def log(msg):
    print(msg, flush=True)
    out["steps"].append(msg)


def main() -> int:
    svc = drive.service()

    # 1) MP3s
    meta = (SRC / "metadata.txt").read_text(encoding="utf-8")
    chapters = re.findall(r"^\d\d?:\d\d(?::\d\d)? (.+)$", meta, flags=re.M)
    v1 = [f for f in drive.list_children(svc, V1_MP3, folders=False) if f["name"].endswith(".mp3")]
    expected = [f"{i:02d} - Aix Walker - {t}.mp3" for i, t in enumerate(chapters, 1)]
    names = sorted(f["name"] for f in v1)
    log(f"v1: {len(v1)} MP3s, erwartet laut Kapiteln: {len(expected)}")
    if names != sorted(expected):
        out["abweichung"] = {"nur_v1": sorted(set(names) - set(expected)), "nur_kapitel": sorted(set(expected) - set(names))}
        log("ABBRUCH: MP3-Namen in v1 passen nicht zu den Kapiteln von v2")
        return finish(1)
    have = {f["name"] for f in drive.list_children(svc, V2_MP3, folders=False)}
    copied = 0
    for f in sorted(v1, key=lambda x: x["name"]):
        if f["name"] in have:
            continue
        svc.files().copy(fileId=f["id"], body={"name": f["name"], "parents": [V2_MP3]}, fields="id").execute()
        copied += 1
    log(f"MP3s kopiert: {copied} (schon vorhanden: {len(have)})")

    # 2) Cover 3000x3000
    have_top = {f["name"] for f in drive.list_children(svc, V2, folders=False)}
    if "album_3000.png" not in have_top:
        im = Image.open(SRC / "album_cover.jpg").convert("RGB")
        if im.size != (3000, 3000):
            im = im.resize((3000, 3000), Image.LANCZOS)
        png = HERE / "build" / "album_3000.png"
        png.parent.mkdir(exist_ok=True)
        im.save(png, "PNG", optimize=True)
        drive._upload(svc, png, V2)
        png.unlink()
        log("album_3000.png (3000x3000) hochgeladen")
    else:
        log("album_3000.png war schon da")

    # 3) metadata.txt aktualisieren (Titel + Pin-Kommentar wie aktuell auf YouTube)
    sys.path.insert(0, str(HERE))
    import run_tokyo
    new = re.sub(r"(?<=TITEL\n).*", run_tokyo.TITLE, meta, count=1)
    new = re.sub(r"ANGEPINNTER KOMMENTAR\n.*?\n\nSPRUCH", "SPRUCH", new, flags=re.S)
    drive.write_text(svc, "metadata.txt", new, V2, mime="text/plain")
    log("metadata.txt im Drive aktualisiert")

    # 4) Ordner umbenennen
    svc.files().update(fileId=V2, body={"name": FOLDER_NAME}).execute()
    log(f"Ordner umbenannt: {FOLDER_NAME}")

    # Kontrolle
    out["v2_top"] = sorted(f["name"] for f in drive.list_children(svc, V2, folders=False))
    out["v2_mp3"] = sorted(f["name"] for f in drive.list_children(svc, V2_MP3, folders=False))
    out["ok"] = len(out["v2_mp3"]) == len(expected) and "album_3000.png" in out["v2_top"]
    return finish(0 if out["ok"] else 1)


def finish(code: int) -> int:
    p = HERE / "build" / "fix_tokyo_drive.json"
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
