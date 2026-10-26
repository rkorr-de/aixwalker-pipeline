"""Repariert Thumbnail + Playlist der Tokyo-Mixe (Mixe der letzten N Tage ohne Eintrag in der Playlist oder ohne eigenes Thumbnail).
Aufruf: python repair_tokyo_youtube.py [--days 14] [--dry-run]
Thumbnail kommt aus dem Drive-Ordner des Mixes (thumb.jpg); Ordner wird über das Datum im Namen gefunden."""
import argparse, re, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from pipeline import drive, youtube
import run_tokyo as rt

ap = argparse.ArgumentParser(); ap.add_argument("--days", type=int, default=14); ap.add_argument("--dry-run", action="store_true")
a = ap.parse_args()
yt = youtube.service()
pid = youtube.ensure_playlist(*rt.PLAYLIST)
in_pl, tok = set(), None
while True:
    r = yt.playlistItems().list(part="contentDetails", playlistId=pid, maxResults=50, pageToken=tok).execute()
    in_pl |= {i["contentDetails"]["videoId"] for i in r["items"]}
    tok = r.get("nextPageToken")
    if not tok: break
up = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
vids = yt.playlistItems().list(part="contentDetails", playlistId=up, maxResults=50).execute()["items"]
ids = [v["contentDetails"]["videoId"] for v in vids]
det = yt.videos().list(part="snippet,status", id=",".join(ids)).execute()["items"]
svc = drive.service()
for d in det:
    sn = d["snippet"]; title = sn["title"]
    if "Tokyo Work Lounge" not in title or "Vol." not in title: continue
    vid = d["id"]; day = sn["publishedAt"][:10]
    th = sn.get("thumbnails", {})
    custom = "maxres" in th
    print(f"{day} {title[:60]} | playlist={'ja' if vid in in_pl else 'NEIN'} | maxres-thumb={'ja' if custom else 'NEIN'}", flush=True)
    if a.dry_run: continue
    if vid not in in_pl:
        ok, err = youtube.retry(lambda: youtube.add_to_playlist(vid, pid), label="Playlist")
        print("  Playlist:", "OK" if ok else err[:300])
    if not custom:
        # Drive-Ordner mit diesem Datum suchen
        q = f"name contains '{day}' and name contains 'Tokyo Work Lounge' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        fl = svc.files().list(q=q, fields="files(id,name)").execute()["files"]
        done = False
        for f in fl:
            tid = drive.find_file(svc, "thumb.jpg", f["id"])
            if tid:
                dst = Path(tempfile.mkdtemp()) / "thumb.jpg"; drive.download(svc, tid, dst)
                ok, err = youtube.retry(lambda: youtube.set_thumbnail(vid, dst), label="Thumbnail")
                print("  Thumbnail:", "OK" if ok else err[:300]); done = True; break
        if not done: print("  kein thumb.jpg im Drive gefunden")
