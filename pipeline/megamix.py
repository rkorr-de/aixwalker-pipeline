"""Samstags-Mega-Mix (Rolf, 17.10.2026): lange Mixe (bis 8 Std.) aus vorhandenen Genre-Mixen, Songs in Zufallsreihenfolge,
pro Mix KEIN Song doppelt. Dieses Modul enthält die reine Logik (Mischen, Kapitel, Zeitplan) – ohne Netz und ohne ffmpeg,
damit sie sich einfach testen lässt."""
import random
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

XFADE = 1.5            # Überblendung zwischen zwei Songs in Sekunden (wie bei den übrigen Zusammenschnitten)
MAX_HOURS = 8.0
BERLIN = ZoneInfo("Europe/Berlin")

# Genre-Gruppen des Mega-Mixes → Genres der Quell-Mixe (Ordnernamen enden auf „(Genre, BPM)“)
GROUPS = {
    "Italian Chillout": ("Italian Chillout",),
    "Mediterranean Lounge": ("Mediterranean Spa Lounge", "Ibiza Sunset Lounge", "Dark Ambient Spa"),
}
ROTATION = ("Italian Chillout", "Cozy Winter Cabin", "Mediterranean Lounge")
MIN_MIXES = {"Italian Chillout": 2, "Cozy Winter Cabin": 2, "Mediterranean Lounge": 4}


def norm_title(title: str) -> str:
    """Titel zum Vergleichen: klein, ohne Satzzeichen, ohne Klammerzusätze wie „(Extended)“."""
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", title.casefold())
    return re.sub(r"[^a-z0-9äöüß]+", " ", t).strip()


def _md5(path: Path) -> str | None:
    import hashlib
    try:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def collect_tracks(pairs: list[tuple[dict, dict]], durations: dict, by_title: bool = True) -> list[dict]:
    """Alle Songs der Quell-Mixe als flache Liste [{path, title, album, dur}] ohne doppelte Songs.
    Doppelt = gleicher normierter Titel ODER identischer Dateiinhalt (dieselbe Datei in zwei Mixen). Dateigröße und
    Länge allein reichen nicht: gleich lange CBR-MP3s haben dieselbe Größe, sind aber verschiedene Songs."""
    out, seen_titles, seen_hash = [], set(), set()
    for p, mx in pairs:
        for path, title in zip(mx["tracks"], mx["titles"]):
            path = Path(path)
            dur = float(durations[str(path)]) if str(path) in durations else float(durations[path])
            key_t = norm_title(title)
            h = _md5(path)
            if (by_title and key_t in seen_titles) or (h and h in seen_hash):   # by_title=False: Tokyo-Mixe teilen dieselben 22 Titel
                continue
            seen_titles.add(key_t)
            if h:
                seen_hash.add(h)
            out.append({"path": path, "title": title, "album": p.get("album", ""), "dur": dur})
    return out


def shuffle_unique(tracks: list[dict], seed: int, max_sec: float, xf: float = XFADE) -> list[dict]:
    """Zufallsreihenfolge. Regeln: nie zwei Songs desselben Albums direkt hintereinander (solange ein anderes Album
    noch Songs hat), Gesamtlänge (mit Überblendungen) höchstens `max_sec`. Gleicher seed = gleiche Reihenfolge."""
    rnd = random.Random(seed)
    by_album: dict[str, list[dict]] = {}
    for t in tracks:
        by_album.setdefault(t["album"], []).append(t)
    for lst in by_album.values():
        rnd.shuffle(lst)
    out, total, prev = [], 0.0, None
    while any(by_album.values()):
        choices = [a for a, lst in by_album.items() if lst and a != prev] or [a for a, lst in by_album.items() if lst]
        # Alben mit mehr übrigen Songs bevorzugen, damit am Ende nicht ein einzelnes Album übrig bleibt
        weights = [len(by_album[a]) for a in choices]
        album = rnd.choices(choices, weights=weights, k=1)[0]
        t = by_album[album].pop()
        add = t["dur"] - (xf if out else 0.0)
        if total + add > max_sec:
            # passt nicht mehr: kürzeren Song suchen, sonst Schluss
            fits = [(a, i) for a, lst in by_album.items() for i, x in enumerate(lst)
                    if total + x["dur"] - xf <= max_sec]
            if not fits:
                break
            a, i = rnd.choice(fits)
            t = by_album[a].pop(i)
            add = t["dur"] - xf
            album = a
        out.append(t)
        total += add
        prev = album
    return out


def total_seconds(tracks: list[dict], xf: float = XFADE) -> float:
    return sum(t["dur"] for t in tracks) - xf * max(0, len(tracks) - 1)


def hhmmss(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60:02d}:{sec % 60:02d}"


def chapter_text(titles: list[str], starts: list[float], max_lines: int = 60) -> str:
    """Kapitel für die Beschreibung (YouTube erlaubt dort 5.000 Zeichen). Bei mehr als `max_lines` Songs kommt nur jeder
    k-te Song als Kapitel (immer mit dem ersten, Start 00:00). Zeiten über 1 Std. als 01:02:13."""
    k = max(1, -(-len(titles) // max_lines))
    lines = []
    for i in range(0, len(titles), k):
        lines.append(f"{hhmmss(starts[i]) if starts[i] >= 3600 else hhmmss(starts[i])} {titles[i]}")
    first = lines[0].split(" ", 1)[1]
    lines[0] = f"00:00 {first}"
    if len(lines) < 3:      # YouTube braucht mindestens 3 Kapitel
        lines = [f"{hhmmss(s)} {t}" for t, s in zip(titles, starts)]
        lines[0] = f"00:00 {titles[0]}"
    return "\n".join(lines)


def tracklist_comments(titles: list[str], starts: list[float], limit: int = 9000) -> list[str]:
    """Vollständige Trackliste mit Zeiten für den angepinnten Kommentar; wird bei Bedarf auf mehrere Texte (je höchstens
    `limit` Zeichen, YouTube erlaubt 10.000) verteilt."""
    parts, cur = [], "Full tracklist:\n"
    for t, s in zip(titles, starts):
        line = f"{hhmmss(s)} {t}\n"
        if len(cur) + len(line) > limit:
            parts.append(cur.rstrip())
            cur = "Tracklist (continued):\n"
        cur += line
    parts.append(cur.rstrip())
    return parts


def publish_time_utc(hhmm: str = "14:00", now: datetime | None = None, min_lead_min: int = 15) -> str | None:
    """Heute `hhmm` Berlin als RFC3339 (UTC). Liegt der Zeitpunkt weniger als `min_lead_min` Minuten in der Zukunft,
    kommt None (= sofort öffentlich) zurück."""
    now = now or datetime.now(BERLIN)
    h, m = (int(x) for x in hhmm.split(":"))
    at = now.astimezone(BERLIN).replace(hour=h, minute=m, second=0, microsecond=0)
    if at - now < timedelta(minutes=min_lead_min):
        return None
    return at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def next_genre(done: list[dict], available: dict[str, int]) -> str | None:
    """Nächstes Genre der Rotation (Italian → Cabin → Lounge). `available` = Anzahl nutzbarer Quell-Mixe je Genre.
    Genres mit zu wenig Material werden übersprungen; ist nirgends genug da: None."""
    last = done[-1]["genre"] if done else None
    start = (ROTATION.index(last) + 1) % len(ROTATION) if last in ROTATION else 0
    for k in range(len(ROTATION)):
        g = ROTATION[(start + k) % len(ROTATION)]
        if available.get(g, 0) >= MIN_MIXES[g]:
            return g
    return None


def weekend_dates(today: date | None = None) -> tuple[date, date]:
    """(Samstag, Sonntag) des laufenden Wochenendes – an einem Samstag also (heute, morgen)."""
    today = today or date.today()
    sat = today + timedelta(days=(5 - today.weekday()) % 7)
    return sat, sat + timedelta(days=1)
