"""Verlauf aller bisherigen Kids-Shorts – damit sich Tiere, Figuren, Lehrinhalte und Geschichten nicht wiederholen.

Die Datei liegt in Google Drive unter „Giggle Meadow Shorts/_verlauf.json“ (jeder Lauf startet in einem frischen
Container, deshalb nicht im Build-Ordner). Ohne Drive-Zugang wird ersatzweise build/kids/_verlauf.json benutzt.
Zusätzlich fließen die Titel der YouTube-Uploads ein, falls ein Eintrag fehlen sollte.

Eintrag: {date, species, name, lesson, theme, summary, title, video_id, status}
"""
import io
import json
from pathlib import Path

from . import config

FILE_NAME = "_verlauf.json"
LOCAL = config.BUILD / FILE_NAME

# Bereits vor Einführung des Verlaufs gedrehte Geschichten (03.10.2026: Test + erster Lauf, beide Goldfisch)
SEED = [
    {"date": "2026-10-03", "species": "baby goldfish", "name": "Finny", "lesson": "",
     "theme": "goldfish jumping between two bowls", "summary": "A goldfish jumps from one fish bowl to another.",
     "title": "Baby Goldfish Tries to Jump Bowls!", "status": "test"},
    {"date": "2026-10-03", "species": "baby goldfish", "name": "Pip", "lesson": "",
     "theme": "goldfish jumping between two bowls",
     "summary": "A goldfish uses a spring leaf to launch itself into another bowl to catch a food pellet.",
     "title": "Brave Goldfish Bounces for a Snack!", "status": "rejected by Rolf"},
]


def _drive():
    from pipeline import drive as base
    from . import drive as kdrive
    if not kdrive.available():
        return None, None, None
    svc = base.service()
    root = base.ensure_folder(svc, kdrive.ROOT_FOLDER)
    q = f"name = '{FILE_NAME}' and '{root}' in parents and trashed = false"
    files = svc.files().list(q=q, fields="files(id)", pageSize=1).execute().get("files", [])
    return svc, root, (files[0]["id"] if files else None)


def load() -> list[dict]:
    """Alle bisherigen Einträge, ältester zuerst (mindestens SEED)."""
    entries: list[dict] = []
    try:
        svc, _root, fid = _drive()
        if svc and fid:
            entries = json.loads(svc.files().get_media(fileId=fid).execute().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"[verlauf] Drive nicht lesbar ({e}) – nutze lokale Datei")
    if not entries and LOCAL.exists():
        entries = json.loads(LOCAL.read_text())
    if not entries:
        entries = list(SEED)
    return entries


def save(entries: list[dict]) -> None:
    LOCAL.parent.mkdir(parents=True, exist_ok=True)
    LOCAL.write_text(json.dumps(entries, indent=1, ensure_ascii=False))
    svc, root, fid = _drive()
    if not svc:
        return
    from googleapiclient.http import MediaIoBaseUpload
    media = MediaIoBaseUpload(io.BytesIO(json.dumps(entries, indent=1, ensure_ascii=False).encode()),
                              mimetype="application/json")
    if fid:
        svc.files().update(fileId=fid, media_body=media).execute()
    else:
        svc.files().create(body={"name": FILE_NAME, "parents": [root]}, media_body=media, fields="id").execute()


def add(entry: dict) -> None:
    entries = load()
    entries.append(entry)
    save(entries)


def entry_from_story(st: dict, date: str, status: str, video_id: str | None = None) -> dict:
    return {"date": date, "species": st["character"]["species"], "name": st["character"]["name"],
            "lesson": st.get("lesson", ""), "theme": st.get("theme", ""), "summary": st.get("summary", st.get("theme", "")),
            "title": st.get("title", ""), "video_id": video_id, "status": status}


if __name__ == "__main__":
    for e in load():
        print(e["date"], "|", e["species"], "|", e.get("lesson", ""), "|", e.get("title", ""), "|", e.get("status", ""))
