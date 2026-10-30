"""YouTube für den Kanal YOIN Rooms: eigener Refresh-Token, Kanal-Prüfung, Upload (Standard: privat).

  python -m yoin.youtube      # Token-Prüfung: ein channels.list-Aufruf, meldet Kanalname und Kanal-ID
"""
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from pipeline.youtube import credentials

from . import config


def service():
    return build("youtube", "v3", credentials=credentials(config.TOKEN_VAR), cache_discovery=False)


def my_channel(yt=None) -> dict:
    r = (yt or service()).channels().list(part="snippet", mine=True).execute()
    if not r.get("items"):
        raise RuntimeError("Kein Kanal für diesen Token gefunden")
    return r["items"][0]


def check_channel(yt=None) -> dict:
    """Bricht ab, wenn der Token nicht zum Kanal YOIN Rooms gehört."""
    ch = my_channel(yt)
    if ch["id"] != config.CHANNEL_ID:
        raise RuntimeError(f"Token gehört zu „{ch['snippet']['title']}“ ({ch['id']}), "
                           f"erwartet {config.CHANNEL_NAME} ({config.CHANNEL_ID})")
    return ch


def upload(video: Path, title: str, description: str, tags: list[str], privacy: str = "private",
           publish_at: str | None = None, location: dict | None = None) -> str:
    """Lädt das Video auf YOIN Rooms hoch (Standard: privat, KI-Label gesetzt). Liefert die Video-ID.
    publish_at = RFC3339 für geplante Veröffentlichung; location z. B. pipeline.youtube.TOKYO. Prüft vorher den Kanal."""
    yt = service()
    check_channel(yt)
    body = {
        "snippet": {"title": title[:100], "description": description[:5000], "tags": tags[:60],
                    "categoryId": config.CATEGORY_ID, "defaultLanguage": config.DEFAULT_LANGUAGE},
        "status": {"privacyStatus": "private" if publish_at else privacy,
                   "selfDeclaredMadeForKids": False,
                   "containsSyntheticMedia": True},
    }
    if publish_at:
        body["status"]["publishAt"] = publish_at
    part = "snippet,status"
    if location:
        body["recordingDetails"] = {"locationDescription": location["description"],
                                    "location": {"latitude": location["latitude"], "longitude": location["longitude"]}}
        part += ",recordingDetails"
    media = MediaFileUpload(str(video), chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part=part, body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"[yoin] Upload {int(status.progress() * 100)}%")
    return resp["id"]


def set_thumbnail(video_id: str, thumb: Path) -> None:
    service().thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumb))).execute()


if __name__ == "__main__":
    ch = check_channel()
    print(f"Kanal: {ch['snippet']['title']} · ID: {ch['id']}")
