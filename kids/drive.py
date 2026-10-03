"""Google Drive für die Kids-Shorts: je Short ein Ordner unter „Giggle Meadow Shorts/<Datum – Titel>“.

Nutzt die bestehende Drive-Freigabe (DRIVE_REFRESH_TOKEN, Scope drive.file) aus pipeline/drive.py.
Standardmäßig aktiv – im Lauf abschaltbar mit --no-drive. Fehlt der Token, wird der Schritt nur als Warnung
übersprungen (der Short geht trotzdem online).
"""
import json
import os
import re
from pathlib import Path

from pipeline import drive as base

ROOT_FOLDER = os.environ.get("KIDS_DRIVE_ROOT", "Giggle Meadow Shorts")

# Dateien aus dem Build-Ordner, die abgelegt werden (Reihenfolge = Reihenfolge im Ordner)
MAIN_FILES = ["short.mp4", "thumbnail.jpg", "story.json", "result.json", "costs.json", "contact_sheet.jpg"]
SOURCE_FILES = ["clip_1.mp4", "clip_2.mp4", "character_sheet.png", "keyframe_1.png", "thumbnail_art.png",
                "clip_1_last.png", "music.mp3", "sfx.mp3"]


def available() -> bool:
    return bool(os.environ.get("DRIVE_REFRESH_TOKEN"))


def folder_name(date: str, title: str) -> str:
    """„2026-10-04 – Tiny Hamster vs GIANT Cupcake“ (ohne #shorts, ohne Dateisystem-Sonderzeichen)."""
    t = re.sub(r"#\w+", "", title)
    t = re.sub(r"[\\/:*?\"<>|]", "", t).strip(" –-")
    return f"{date} – {t[:70]}".strip()


def upload_short_package(out: Path, date: str, title: str, video_id: str | None = None) -> dict:
    """Legt den Ordner an und lädt alle vorhandenen Dateien hoch. Liefert {name: link, '_folder': link}."""
    svc = base.service()
    root = base.ensure_folder(svc, ROOT_FOLDER)
    folder = base.ensure_folder(svc, folder_name(date, title), root)
    links = {"_folder": f"https://drive.google.com/drive/folders/{folder}"}
    # kleine Infodatei mit YouTube-Link, damit man im Drive sofort sieht, welches Video es ist
    if video_id:
        info = out / "youtube_link.txt"
        info.write_text(f"https://www.youtube.com/shorts/{video_id}\n{title}\n")
        links[info.name] = base._upload(svc, info, folder)
    for name in MAIN_FILES:
        f = out / name
        if f.exists():
            links[name] = base._upload(svc, f, folder)
    src = [out / n for n in SOURCE_FILES if (out / n).exists()]
    if src:
        sub = base.ensure_folder(svc, "quellen", folder)
        for f in src:
            links[f"quellen/{f.name}"] = base._upload(svc, f, sub)
    return links


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "build/kids/dry")
    res = json.loads((out / "result.json").read_text()) if (out / "result.json").exists() else {}
    title = res.get("story", {}).get("title", "Test")
    print(json.dumps(upload_short_package(out, res.get("date", "0000-00-00"), title, res.get("video_id")), indent=2))
