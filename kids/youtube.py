"""YouTube für den Kids-Kanal: eigener Refresh-Token, Upload als „für Kinder“, geplante Veröffentlichung, Löschen."""
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from pipeline.youtube import credentials

from . import config


def service():
    return build("youtube", "v3", credentials=credentials(config.KIDS_TOKEN_VAR), cache_discovery=False)


def my_channel() -> dict:
    r = service().channels().list(part="snippet,statistics,contentDetails", mine=True).execute()
    if not r.get("items"):
        raise RuntimeError("Kein Kanal für diesen Token gefunden")
    return r["items"][0]


def uploaded_titles(max_items: int = 200) -> list[str]:
    """Titel aller bisherigen Uploads (zur Vermeidung von Wiederholungen)."""
    yt = service()
    ch = my_channel()
    pl = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    titles, token = [], None
    while len(titles) < max_items:
        r = yt.playlistItems().list(part="snippet", playlistId=pl, maxResults=50, pageToken=token).execute()
        titles += [i["snippet"]["title"] for i in r.get("items", [])]
        token = r.get("nextPageToken")
        if not token:
            break
    return titles


def upload(video: Path, title: str, description: str, tags: list[str], privacy: str = "private",
           publish_at: str | None = None) -> str:
    """Upload als „für Kinder“ + KI-Label. publish_at (RFC3339, UTC) = geplante Veröffentlichung."""
    body = {
        "snippet": {"title": title[:100], "description": description[:5000], "tags": tags[:60],
                    "categoryId": config.CATEGORY_ID, "defaultLanguage": config.DEFAULT_LANGUAGE,
                    "defaultAudioLanguage": "zxx"},  # zxx = kein sprachlicher Inhalt
        "status": {"privacyStatus": "private" if publish_at else privacy,
                   "selfDeclaredMadeForKids": True,
                   "containsSyntheticMedia": True,
                   "license": "youtube", "embeddable": True},
    }
    if publish_at:
        body["status"]["publishAt"] = publish_at
    media = MediaFileUpload(str(video), chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    req = service().videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"[youtube] Upload {int(status.progress() * 100)}%")
    return resp["id"]


def set_thumbnail(video_id: str, thumb: Path) -> None:
    service().thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumb))).execute()


def status(video_id: str) -> dict:
    r = service().videos().list(part="status,snippet,statistics", id=video_id).execute()
    return r["items"][0] if r.get("items") else {}


def set_public(video_id: str) -> None:
    service().videos().update(part="status", body={"id": video_id, "status": {
        "privacyStatus": "public", "selfDeclaredMadeForKids": True}}).execute()


def delete(video_id: str) -> None:
    service().videos().delete(id=video_id).execute()


if __name__ == "__main__":
    c = my_channel()
    print("Kanal:", c["snippet"]["title"], "| Abos:", c["statistics"].get("subscriberCount"),
          "| Token-Variable:", config.KIDS_TOKEN_VAR)
    for t in uploaded_titles(10):
        print(" -", t)
