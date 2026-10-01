"""Google Drive: pro Mix ein neuer Ordner unter „AIX WALKER Mixe“, dort ZIP, Album-Cover, Metadaten.

Nutzt dieselben OAuth-Zugangsdaten wie YouTube; braucht zusätzlich den Scope drive.file
(nur Dateien, die diese App selbst anlegt – kein Zugriff auf andere Drive-Inhalte).
"""
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from . import youtube

ROOT_FOLDER = "AIX WALKER Mixe"
FOLDER_MIME = "application/vnd.google-apps.folder"


def service():
    return build("drive", "v3", credentials=youtube.credentials(), cache_discovery=False)


def _find_folder(svc, name: str, parent: str | None) -> str | None:
    q = f"name = '{name.replace(chr(39), chr(92) + chr(39))}' and mimeType = '{FOLDER_MIME}' and trashed = false"
    if parent:
        q += f" and '{parent}' in parents"
    res = svc.files().list(q=q, fields="files(id,name)", pageSize=5).execute().get("files", [])
    return res[0]["id"] if res else None


def ensure_folder(svc, name: str, parent: str | None = None) -> str:
    fid = _find_folder(svc, name, parent)
    if fid:
        return fid
    body = {"name": name, "mimeType": FOLDER_MIME}
    if parent:
        body["parents"] = [parent]
    return svc.files().create(body=body, fields="id").execute()["id"]


def upload_mix_package(folder_name: str, files: list[Path]) -> dict:
    """Legt AIX WALKER Mixe/<folder_name> an (neu je Mix) und lädt die Dateien hoch. Liefert {name: link}."""
    svc = service()
    root = ensure_folder(svc, ROOT_FOLDER)
    folder = ensure_folder(svc, folder_name, root)
    links = {"_folder": f"https://drive.google.com/drive/folders/{folder}"}
    for f in files:
        if not f.exists():
            continue
        media = MediaFileUpload(str(f), chunksize=8 * 1024 * 1024, resumable=True)
        req = svc.files().create(body={"name": f.name, "parents": [folder]}, media_body=media,
                                 fields="id,webViewLink")
        resp = None
        while resp is None:
            status, resp = req.next_chunk()
        links[f.name] = resp.get("webViewLink", f"https://drive.google.com/file/d/{resp['id']}/view")
    return links


if __name__ == "__main__":
    import sys
    print(upload_mix_package("Test " + sys.argv[1] if len(sys.argv) > 1 else "Test", [Path("README.md")]))
