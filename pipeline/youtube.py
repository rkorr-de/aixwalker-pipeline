"""YouTube Data API v3 + Analytics: Upload (privat), Thumbnail, Playlist, KI-Label, Kennzahlen."""
from datetime import date, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from . import config

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def credentials() -> Credentials:
    creds = Credentials(
        token=None,
        refresh_token=config.require("YT_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.require("YT_CLIENT_ID"),
        client_secret=config.require("YT_CLIENT_SECRET"),
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def service():
    return build("youtube", "v3", credentials=credentials(), cache_discovery=False)


def analytics():
    return build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)


def my_channel() -> dict:
    r = service().channels().list(part="snippet,statistics", mine=True).execute()
    return r["items"][0]


def upload_video(video: Path, title: str, description: str, tags: list[str], category_id: str = "10",
                 privacy: str = "private", publish_at: str | None = None, made_for_kids: bool = False,
                 ai_generated: bool = True, default_language: str = "en") -> str:
    """Lädt das Video hoch (Standard: privat). Liefert die Video-ID. publish_at = RFC3339 für geplante Veröffentlichung."""
    body = {
        "snippet": {"title": title[:100], "description": description[:5000], "tags": tags[:60],
                    "categoryId": category_id, "defaultLanguage": default_language},
        "status": {"privacyStatus": "private" if publish_at else privacy,
                   "selfDeclaredMadeForKids": made_for_kids,
                   "containsSyntheticMedia": ai_generated},
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


def add_to_playlist(video_id: str, playlist_id: str) -> None:
    service().playlistItems().insert(part="snippet", body={
        "snippet": {"playlistId": playlist_id, "resourceId": {"kind": "youtube#video", "videoId": video_id}}
    }).execute()


def set_public(video_id: str) -> None:
    service().videos().update(part="status", body={"id": video_id, "status": {"privacyStatus": "public"}}).execute()


def recent_performance(days: int = 28, max_videos: int = 15) -> list[dict]:
    """Kennzahlen der zuletzt hochgeladenen Videos: Aufrufe, Wiedergabezeit, Ø Dauer, Bindung."""
    yt = service()
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    items = yt.playlistItems().list(part="snippet", playlistId=uploads, maxResults=max_videos).execute()["items"]
    ids = [i["snippet"]["resourceId"]["videoId"] for i in items]
    titles = {i["snippet"]["resourceId"]["videoId"]: i["snippet"]["title"] for i in items}
    end = date.today()
    start = end - timedelta(days=days)
    rows = analytics().reports().query(
        ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
        metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage",
        dimensions="video", filters=f"video=={','.join(ids)}", sort="-estimatedMinutesWatched",
    ).execute().get("rows", [])
    return [{"videoId": r[0], "title": titles.get(r[0], r[0]), "views": r[1], "minutesWatched": r[2],
             "avgViewSec": r[3], "avgViewPct": r[4]} for r in rows]


def channel_watch_hours(days: int = 365) -> float:
    end = date.today()
    start = end - timedelta(days=days)
    r = analytics().reports().query(ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
                                    metrics="estimatedMinutesWatched").execute()
    rows = r.get("rows", [[0]])
    return rows[0][0] / 60.0


if __name__ == "__main__":
    c = my_channel()
    print("Kanal:", c["snippet"]["title"], "| Abos:", c["statistics"].get("subscriberCount"))
    print("Wiedergabestunden 365 Tage:", round(channel_watch_hours(), 1))
    for row in recent_performance():
        print(row)
