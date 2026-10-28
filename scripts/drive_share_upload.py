#!/usr/bin/env python3
"""Legt einen Drive-Ordnerpfad NEBEN einem vorhandenen Ordner an, lädt Dateien hoch und gibt Ordner und Dateien für
„Jeder mit dem Link“ (Leser) frei. Nutzt dieselbe Drive-Anbindung wie die Pipeline (pipeline.drive, DRIVE_REFRESH_TOKEN).

  python scripts/drive_share_upload.py --path "YOIN Rooms/Songtest 2026-10-28" --next-to "AIX WALKER Mixe" a.mp3 b.mp3

Ausgabe: JSON mit Ordner-Link, Datei-Links und der geprüften Freigabe. Vorhandene Dateien gleichen Namens im Zielordner werden
nicht doppelt angelegt, sondern ersetzt (Inhalt aktualisiert), so dass ein erneuter Lauf dieselben Links liefert.
"""
import argparse
import json
import sys
from pathlib import Path

from googleapiclient.http import MediaFileUpload

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from pipeline import drive  # noqa: E402


def share_anyone_reader(svc, file_id: str) -> None:
    """Freigabe „Jeder mit dem Link“ (Leser), nur wenn sie noch fehlt."""
    perms = svc.permissions().list(fileId=file_id, fields="permissions(id,type,role)").execute().get("permissions", [])
    if not any(p["type"] == "anyone" and p["role"] in ("reader", "commenter", "writer") for p in perms):
        svc.permissions().create(fileId=file_id, body={"type": "anyone", "role": "reader"}, fields="id").execute()


def link_access(svc, file_id: str) -> str:
    perms = svc.permissions().list(fileId=file_id, fields="permissions(type,role)").execute().get("permissions", [])
    return next((f"anyone/{p['role']}" for p in perms if p["type"] == "anyone"), "nicht frei")


def upload(svc, f: Path, parent: str) -> dict:
    existing = drive.find_file(svc, f.name, parent)
    media = MediaFileUpload(str(f), mimetype="audio/mpeg" if f.suffix.lower() == ".mp3" else None,
                            chunksize=8 * 1024 * 1024, resumable=True)
    if existing:
        req = svc.files().update(fileId=existing, media_body=media, fields="id,webViewLink,size")
    else:
        req = svc.files().create(body={"name": f.name, "parents": [parent]}, media_body=media, fields="id,webViewLink,size")
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return resp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True, help='Ordnerpfad, z. B. "YOIN Rooms/Songtest 2026-10-28"')
    ap.add_argument("--next-to", default=drive.ROOT_FOLDER, help="der neue oberste Ordner entsteht im selben Elternordner wie dieser Ordner")
    ap.add_argument("files", nargs="+", type=Path)
    a = ap.parse_args()

    svc = drive.service()
    ref = drive._find_folder(svc, a.next_to, None)
    parent = None
    if ref:
        parents = svc.files().get(fileId=ref, fields="parents").execute().get("parents") or []
        parent = parents[0] if parents else None
    print(f"Referenzordner „{a.next_to}“: {ref or 'nicht gefunden'}; Elternordner: {parent or 'Mein Drive (Wurzel)'}", file=sys.stderr)

    ids = []
    for seg in [s for s in a.path.split("/") if s]:
        parent = drive.ensure_folder(svc, seg, parent)
        ids.append(parent)
    top, leaf = ids[0], ids[-1]

    out = {"top_folder": f"https://drive.google.com/drive/folders/{top}", "folder": f"https://drive.google.com/drive/folders/{leaf}",
           "next_to": a.next_to, "files": {}}
    for f in a.files:
        r = upload(svc, f, leaf)
        share_anyone_reader(svc, r["id"])
        out["files"][f.name] = {"id": r["id"], "link": r.get("webViewLink", f"https://drive.google.com/file/d/{r['id']}/view"),
                                "bytes": int(r.get("size", 0)), "access": link_access(svc, r["id"]),
                                "local_bytes": f.stat().st_size}
    for fid in ids:                      # jeder Ordner des Pfads wird freigegeben, damit der Link auch von oben her funktioniert
        share_anyone_reader(svc, fid)
    out["folder_access"] = link_access(svc, leaf)
    out["top_folder_access"] = link_access(svc, top)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
