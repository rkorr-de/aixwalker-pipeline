"""Nischen- und Konkurrenzanalyse über die YouTube Data API (kostenlos, nutzt das vorhandene OAuth-Token).

    python -m pipeline.research "luxury spa lounge music" --days 180 --top 15

Zeigt, welche Videos und Kanäle in einer Nische gerade stark laufen (Aufrufe pro Tag, Länge, Kanalgröße).
Kontingent: Die Suche kostet pro Aufruf deutlich mehr Einheiten als Abfragen von Video-/Kanaldaten
(Tageslimit standardmäßig 10.000 Einheiten) – darum bewusst wenige Suchen je Lauf.
"""
import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

_DUR = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def parse_duration(iso: str) -> int:
    """ISO-8601-Dauer (PT1H2M3S) in Sekunden."""
    m = _DUR.fullmatch(iso or "")
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def _chunks(items: list, n: int = 50):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def niche_videos(query: str, days: int = 180, pages: int = 1, svc=None, now: datetime | None = None) -> list[dict]:
    """Meistgesehene Videos zur Suchanfrage der letzten `days` Tage, mit Kanal- und Videokennzahlen."""
    if svc is None:
        from . import youtube
        svc = youtube.service()
    now = now or datetime.now(timezone.utc)
    after = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids, token = [], None
    for _ in range(max(1, pages)):
        res = svc.search().list(part="id", q=query, type="video", order="viewCount", maxResults=50,
                                publishedAfter=after, pageToken=token).execute()
        ids += [it["id"]["videoId"] for it in res.get("items", [])]
        token = res.get("nextPageToken")
        if not token:
            break
    videos = []
    for chunk in _chunks(ids):
        res = svc.videos().list(part="snippet,statistics,contentDetails", id=",".join(chunk)).execute()
        videos += res.get("items", [])
    channel_ids = sorted({v["snippet"]["channelId"] for v in videos})
    channels = {}
    for chunk in _chunks(channel_ids):
        res = svc.channels().list(part="snippet,statistics", id=",".join(chunk)).execute()
        channels.update({c["id"]: c for c in res.get("items", [])})
    rows = []
    for v in videos:
        pub = datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))
        age_days = max(1.0, (now - pub).total_seconds() / 86400)
        views = int(v.get("statistics", {}).get("viewCount", 0))
        ch = channels.get(v["snippet"]["channelId"], {})
        subs = ch.get("statistics", {}).get("subscriberCount")
        rows.append({
            "video_id": v["id"], "title": v["snippet"]["title"], "channel": v["snippet"]["channelTitle"],
            "channel_id": v["snippet"]["channelId"], "subscribers": int(subs) if subs is not None else None,
            "views": views, "views_per_day": round(views / age_days, 1), "age_days": round(age_days),
            "minutes": round(parse_duration(v["contentDetails"].get("duration", "")) / 60, 1),
            "url": f"https://youtube.com/watch?v={v['id']}",
        })
    rows.sort(key=lambda r: r["views_per_day"], reverse=True)
    return rows


def summarize(rows: list[dict], top: int = 15) -> str:
    lines = [f"{'Aufr./Tag':>10} {'Aufrufe':>10} {'Abos':>9} {'Min':>6} {'Alter(d)':>8}  Kanal – Titel"]
    for r in rows[:top]:
        subs = "?" if r["subscribers"] is None else f"{r['subscribers']:,}".replace(",", ".")
        lines.append(f"{r['views_per_day']:>10,.0f} {r['views']:>10,} {subs:>9} {r['minutes']:>6} {r['age_days']:>8}  "
                     f"{r['channel']} – {r['title'][:70]}".replace(",", "."))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query")
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--pages", type=int, default=1, help="Suchseiten (je 50 Treffer); jede kostet Kontingent")
    ap.add_argument("--out", type=Path, default=None, help="Ergebnis zusätzlich als JSON speichern")
    args = ap.parse_args()
    rows = niche_videos(args.query, args.days, args.pages)
    print(summarize(rows, args.top))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
