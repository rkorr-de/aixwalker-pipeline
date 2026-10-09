"""Streaming-Upload zu YouTube ohne fertige Datei auf der Festplatte (Rolf 09.10.2026: Monats-Mix 8 Std. in 4K ≈ 55 GB,
die Sitzung hat aber nur ca. 27 GB frei).

ffmpeg hängt die fertig kodierten Kaminfilm-Segmente und die Tonspur ohne Neuberechnung aneinander und schreibt einen
Matroska-Strom (MKV) auf stdout. Der Strom geht in Stücken von 64 MiB über das Resumable-Upload-Protokoll von Google zu
YouTube; die Gesamtgröße ist erst am Ende bekannt („Content-Range: bytes a-b/*“). Bricht ein Stück ab, wird beim Server
nachgefragt, wie viel angekommen ist, und ab dort weitergesendet (das laufende Stück liegt im Speicher).
"""
import hashlib
import json
import subprocess
import time

import requests
from google.auth.transport.requests import Request

from . import youtube

CHUNK = 64 * 1024 * 1024          # Vielfaches von 256 KiB (Pflicht für alle Stücke außer dem letzten)
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


class _Auth:
    def __init__(self):
        self.creds = youtube.credentials()

    def header(self) -> dict:
        if not self.creds.valid or (self.creds.expiry and (self.creds.expiry.timestamp() - time.time()) < 300):
            self.creds.refresh(Request())
        return {"Authorization": f"Bearer {self.creds.token}"}


def _read_exact(stream, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        b = stream.read(n - len(buf))
        if not b:
            break
        buf += b
    return bytes(buf)


def _committed(resp: requests.Response) -> int:
    """Bytes, die der Server bestätigt hat (Range: bytes=0-N → N+1)."""
    rng = resp.headers.get("Range")
    return int(rng.split("-")[1]) + 1 if rng else 0


def _put(session_url: str, auth: _Auth, data: bytes, start: int, total: int | None) -> requests.Response:
    end = start + len(data) - 1
    size = str(total) if total is not None else "*"
    rng = f"bytes {start}-{end}/{size}" if data else f"bytes */{size}"
    return requests.put(session_url, headers={**auth.header(), "Content-Range": rng}, data=data, timeout=900)


def _query(session_url: str, auth: _Auth) -> requests.Response:
    return requests.put(session_url, headers={**auth.header(), "Content-Range": "bytes */*"}, timeout=120)


def upload_stream(cmd: list[str], title: str, description: str, tags: list[str], privacy: str = "private",
                  category_id: str = "10", ai_generated: bool = True, log=print) -> dict:
    """Startet `cmd` (ffmpeg, Ausgabe auf stdout) und lädt den Strom als YouTube-Video hoch. Liefert
    {"video_id", "bytes", "md5", "seconds"}."""
    auth = _Auth()
    body = {"snippet": {"title": title[:100], "description": description[:5000], "tags": tags[:60],
                        "categoryId": category_id, "defaultLanguage": "en"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False,
                       "containsSyntheticMedia": ai_generated}}
    r = requests.post(UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"},
                      headers={**auth.header(), "Content-Type": "application/json; charset=UTF-8",
                               "X-Upload-Content-Type": "video/x-matroska"},
                      data=json.dumps(body), timeout=120)
    if r.status_code != 200 or "Location" not in r.headers:
        raise RuntimeError(f"Upload-Sitzung nicht gestartet: HTTP {r.status_code} {r.text[:300]}")
    session = r.headers["Location"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
    md5, sent, t0 = hashlib.md5(), 0, time.time()
    chunk = _read_exact(proc.stdout, CHUNK)
    while True:
        nxt = _read_exact(proc.stdout, CHUNK) if len(chunk) == CHUNK else b""
        last = not nxt
        total = sent + len(chunk) if last else None
        offset = 0                                   # Anteil des aktuellen Stücks, den der Server schon hat
        done = None
        for attempt in range(8):
            try:
                resp = _put(session, auth, chunk[offset:], sent + offset, total)
            except requests.RequestException as e:
                resp = None
                log(f"[stream] Netzfehler ({e.__class__.__name__}), Versuch {attempt + 1}")
            if resp is not None and resp.status_code in (200, 201):
                done = resp.json()
                break
            if resp is not None and resp.status_code == 308:
                got = _committed(resp) - sent
                if got >= len(chunk):
                    break
                offset = max(0, got)                 # Server hat nur einen Teil → Rest erneut senden
                continue
            if resp is not None and resp.status_code not in (500, 502, 503, 504, 429):
                proc.kill()
                raise RuntimeError(f"Upload abgebrochen: HTTP {resp.status_code} {resp.text[:300]}")
            time.sleep(min(60, 2 ** attempt * 2))
            try:                                     # nachfragen, wie viel angekommen ist
                q = _query(session, auth)
                if q.status_code in (200, 201):
                    done = q.json()
                    break
                offset = max(0, _committed(q) - sent)
            except requests.RequestException:
                pass
        else:
            proc.kill()
            raise RuntimeError("Upload: Stück konnte nach 8 Versuchen nicht gesendet werden")
        md5.update(chunk)
        sent += len(chunk)
        log(f"[stream] {sent / 1e9:.2f} GB hochgeladen ({sent * 8 / max(1, time.time() - t0) / 1e6:.0f} Mbit/s)")
        if last:
            break
        chunk = nxt
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg endete mit Code {rc} – Video unvollständig")
    if not done or "id" not in done:
        raise RuntimeError(f"Upload ohne Video-ID beendet: {str(done)[:300]}")
    return {"video_id": done["id"], "bytes": sent, "md5": md5.hexdigest(), "seconds": round(time.time() - t0)}


def remove_incomplete(title: str, log=print) -> list[str]:
    """Entfernt eigene, nie fertig gewordene Uploads mit diesem Titel (z. B. nach einem abgebrochenen Strom-Upload –
    09.10.2026 blieb so ein Eintrag mit Länge 0 öffentlich stehen). Fertig verarbeitete Videos bleiben unberührt."""
    svc = youtube.service()
    up = svc.channels().list(part="contentDetails", mine=True).execute()["items"][0]["contentDetails"][
        "relatedPlaylists"]["uploads"]
    ids = [i["snippet"]["resourceId"]["videoId"] for i in
           svc.playlistItems().list(part="snippet", playlistId=up, maxResults=25).execute().get("items", [])]
    removed = []
    for it in (svc.videos().list(part="snippet,status,contentDetails", id=",".join(ids)).execute().get("items", [])
               if ids else []):
        if (it["snippet"]["title"] == title[:100] and it["status"].get("uploadStatus") != "processed"
                and it["contentDetails"].get("duration") in ("P0D", "PT0S")):
            svc.videos().delete(id=it["id"]).execute()
            removed.append(it["id"])
            log(f"[stream] unfertigen Upload {it['id']} entfernt")
    return removed
