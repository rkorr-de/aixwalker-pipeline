"""WÄCHTER – prüft dreimal täglich alles rund um ALLE Mixe des Kanals (Tokyo detailliert, alle anderen allgemein; YouTube, Drive, Gedächtnis), repariert Harmloses selbst
und schickt Rolf einen Bericht per E-Mail.

Aufruf:  python waechter.py [--mail] [--fix] [--days 3] [--selftest]
  --fix     darf reparieren (nur Umkehrbares, kostenlos: Thumbnail, Playlist, Sichtbarkeit des heutigen Mixes, Vol.-Nummer des NEUESTEN Mixes)
  --mail    Bericht per E-Mail an Rolf
Exit-Code 0 = alles in Ordnung, 1 = Auffälligkeiten (stehen im Bericht), 2 = Wächter konnte selbst nicht prüfen.

Grenzen (bewusst): löscht nie etwas, erzeugt nie Musik/Bilder (kostet Geld), reicht nie bei DistroKid ein, ändert keine Beschreibungen.
Er sieht nur, was YouTube-API, Drive und das Gedächtnis hergeben; was er nicht lesen kann, steht im Bericht als „nicht prüfbar“.
"""
import argparse
import base64
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "concepts"))

BERLIN = ZoneInfo("Europe/Berlin")
PLAYLIST = ("Tokyo Work Lounge · Slow Jazz for Work and Coding",)
LEGACY_TITLES = {"lantern hours", "quiet circuit", "slow neon", "paper window", "midnight tab", "soft compile", "tea steam", "late commit",
                 "shoji glow", "low bandwidth", "evening syntax", "still desk", "warm cache", "rain on glass", "cedar shelf", "gentle deploy",
                 "amber standby", "idle cursor", "velvet terminal", "nightshift loop", "calm refactor", "tatami light"}
NEW_TITLE_RULE_FROM_VOL = 11          # Rolf 26.10.2026: ab Vol. 11 nie ein Songtitel doppelt
REPORT_TO = "rolf.korr@gmail.com"


@dataclass
class Finding:
    level: str            # OK | WARN | FEHLER | INFO
    text: str
    fixed: str = ""       # was der Wächter selbst repariert hat


@dataclass
class Report:
    findings: list = field(default_factory=list)
    did: list = field(default_factory=list)       # was heute passiert ist (Zeitleiste)

    def add(self, level, text, fixed=""):
        self.findings.append(Finding(level, text, fixed))

    @property
    def problems(self):
        return [f for f in self.findings if f.level in ("WARN", "FEHLER")]


# ------------------------------------------------------------------ reine Hilfsfunktionen (selbsttestbar)
def parse_vol(title: str):
    m = re.search(r"Vol\.\s*(\d+)", title or "")
    return int(m.group(1)) if m else None


def parse_chapters(desc: str) -> list[str]:
    out, on = [], False
    for line in (desc or "").splitlines():
        if re.match(r"^\s*chapters\s*$", line, re.I):
            on = True
            continue
        if on:
            m = re.match(r"^\s*(?:\d+:)?\d{1,2}:\d{2}\s+(.+?)\s*$", line)
            if m:
                out.append(m.group(1))
            elif out:
                break
    return out


def iso_minutes(d: str) -> float:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return 0.0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 60 + mi + s / 60


def check_vols(videos: list[dict], rep: Report) -> dict | None:
    """videos: Tokyo-Tagesmixe (title, id, published). Liefert das neueste Video mit falscher Nummer (oder None)."""
    vs = sorted([v for v in videos if parse_vol(v["title"])], key=lambda v: v["published"])
    seen = {}
    bad = None
    for v in vs:
        n = parse_vol(v["title"])
        if n in seen:
            rep.add("FEHLER", f"Doppelte Titelnummer Vol. {n}: {seen[n]['id']} und {v['id']}")
            bad = v
        seen[n] = v
    nums = [parse_vol(v["title"]) for v in vs]
    for a, b, v in zip(nums, nums[1:], vs[1:]):
        if b != a + 1 and b not in (a,):
            rep.add("WARN", f"Titelnummern springen: Vol. {a} → Vol. {b} ({v['id']})")
    return bad


def check_titles(chaps: dict[str, list[str]], vols: dict[str, int], rep: Report) -> None:
    """chaps: video_id → Kapiteltitel. Ab Vol. 11 darf kein Titel in einem anderen Tokyo-Mix vorkommen und keiner aus der alten Liste."""
    owner: dict[str, str] = {}
    for vid, titles in chaps.items():
        for t in titles:
            owner.setdefault(t.lower(), vid)
    for vid, titles in chaps.items():
        vol = vols.get(vid) or 0
        if vol < NEW_TITLE_RULE_FROM_VOL:
            continue
        legacy = [t for t in titles if t.lower() in LEGACY_TITLES]
        dup_other = [t for t in titles if owner.get(t.lower()) != vid]
        dup_self = len(titles) - len({t.lower() for t in titles})
        if legacy or dup_other or dup_self:
            rep.add("FEHLER", f"Vol. {vol} ({vid}): Songtitel nicht neu – alte Liste: {legacy[:5]}, in anderem Mix schon benutzt: {dup_other[:5]}, doppelt im Mix: {dup_self}")
        elif len(titles) < 20:
            rep.add("WARN", f"Vol. {vol} ({vid}): nur {len(titles)} Kapitel in der Beschreibung")
        else:
            rep.add("OK", f"Vol. {vol}: {len(titles)} neue, nie benutzte Songtitel")


# ------------------------------------------------------------------ Genre-Prüfungen (Italienisch, Cabin, Ibiza, Sleep/Spa/Lounge, Mega-Mixe)
GENRES = {   # Plan Rolf 26.10.2026: Italien Di, Cabin Mi (je wöchentlich) + Samstags-Mega → Höchstabstand 8 Tage. Schlüssel: (Anzeigename, Stichwörter in Titel/Beschreibung, Mindestdauer Min, erwartete Playlist (Titel), Höchstabstand in Tagen, Kostengrenze USD)
    "cabin": ("Winter Cabin", ("cabin", "fireplace"), 120, "Cozy Winter Cabin · Relaxing Fireplace Chillout 4K", 8, 15.0),
    "italian": ("Italian Chillout", ("italian", "amalfi", "lake como", "dolce vita"), 25, "Italian Chillout Music", 8, 9.0),
    "ibiza": ("Ibiza Sunset Lounge", ("ibiza", "balearic"), 25, "Ibiza Sunset Lounge", 14, 9.0),
    "sleep": ("Sleep/Spa/Lounge", ("sleep", "spa ", "massage", "lounge", "ambient"), 25, "Chillout, Lounge & Sleep · Aix Walker", 14, 9.0),
}


# Bewusst pausierte Linien (ROUTINE_PROMPT.md: pausiert seit 13.10.2026, bis Rolf sie freigibt) – kein Alarm bei fehlenden Mixen
PAUSED_GENRES = {
    "ibiza": "bewusst pausiert seit 13.10.2026 (Freigabe durch Rolf nötig)",
    "sleep": "bewusst pausiert seit 13.10.2026 (Auto-Mix/Sleep/Spa, Freigabe durch Rolf nötig)",
}


def classify_genre(title: str, desc: str = "") -> str | None:
    t = (title or "").lower()
    for key, (_n, words, *_r) in GENRES.items():
        if any(w in t for w in words):
            return key
    d = (desc or "")[:300].lower()
    for key, (_n, words, *_r) in GENRES.items():
        if any(w in d for w in words):
            return key
    return None


def genre_findings(mixes: list[dict], now: datetime, pl_titles: dict[str, set], mem_cost: dict[str, float]) -> list[tuple[str, str]]:
    """mixes: Videos ≥ 25 Min (ohne Tokyo-Tagesmixe) mit title, desc, minutes, id, published, privacy.
    pl_titles: Playlist-Titel → Video-IDs. mem_cost: video_id → Kosten USD. Liefert (Level, Text)."""
    out = []
    last: dict[str, datetime] = {}
    by_genre: dict[str, list[dict]] = {}
    for v in mixes:
        mega = "hours long" in v["title"].lower() or "long mix" in v["title"].lower()
        g = classify_genre(v["title"], v["desc"])
        pub = datetime.fromisoformat(v["published"].replace("Z", "+00:00"))
        if "{" in v["title"] or "{" in v["desc"][:3000] or "TODO" in v["desc"]:
            out.append(("FEHLER", f"{v['title'][:50]}: Platzhalter oder Entwurfsrest im Titel/in der Beschreibung (z. B. geschweifte Klammern)"))
        if not v["desc"].strip():
            out.append(("FEHLER", f"{v['title'][:50]}: Beschreibung ist leer"))
        if g is None and re.search(r"\bgym\b|workout|night drive", (v["title"] + " " + v["desc"][:300]).lower()):
            out.append(("INFO", f"{v['title'][:40]}: Gym/Night Drive – Genre seit 08.10.2026 bewusst eingestellt, nur Grundprüfung"))
            continue
        if g is None:
            out.append(("INFO", f"{v['title'][:60]}: Genre nicht erkannt – nur allgemein geprüft"))
            continue
        name, _w, min_min, plname, _gap, cost_max = GENRES[g]
        if not mega:
            last[g] = max(last.get(g, pub), pub)
            by_genre.setdefault(g, []).append(v)
            if v["minutes"] < min_min:
                out.append(("WARN", f"{name}: {v['title'][:40]} dauert nur {v['minutes']:.0f} Min (Mindestlänge {min_min})"))
            ids = pl_titles.get(plname)
            if ids is not None and v["id"] not in ids and v["privacy"] == "public":
                out.append(("FEHLER", f"{name}: {v['title'][:40]} steht nicht in der Playlist „{plname}“"))
        else:
            if v["minutes"] < 240:
                out.append(("WARN", f"Mega-Mix {name}: nur {v['minutes'] / 60:.1f} Std. (erwartet mindestens 4 Std.)"))
        c = mem_cost.get(v["id"])
        if c and c > cost_max:
            out.append(("WARN" if (now - pub).days <= 2 else "INFO", f"{name}: {v['title'][:40]} kostete {c:.2f} $ (Grenze {cost_max:.0f} $)"))
    for g, (name, _w, _m, _p, gap, _c) in GENRES.items():
        if g in last:
            days = (now - last[g]).days
            if g in PAUSED_GENRES and days > gap:
                out.append(("INFO", f"{name}: seit {days} Tagen kein Mix – {PAUSED_GENRES[g]}"))
            elif days > gap:
                out.append(("WARN", f"{name}: seit {days} Tagen kein neuer Mix (üblich höchstens {gap} Tage Abstand) – bewusst pausiert oder ausgefallen?"))
            else:
                out.append(("OK", f"{name}: letzter Mix vor {days} Tag(en), {len(by_genre[g])} Mix(e) in den letzten Tagen"))
    # Songtitel dürfen nicht in mehreren Mixen derselben Linie vorkommen
    for g, vs in by_genre.items():
        seen: dict[str, str] = {}
        dups = []
        for v in sorted(vs, key=lambda v: v["published"]):
            for c in parse_chapters(v["desc"]):
                k = c.lower()
                if k in seen and seen[k] != v["id"]:
                    dups.append(c)
                seen.setdefault(k, v["id"])
        if dups:
            out.append(("WARN", f"{GENRES[g][0]}: Songtitel in mehreren Mixen benutzt: {sorted(set(dups))[:5]}"))
    return out


def selftest() -> int:
    r = Report()
    assert parse_vol("... - Vol. 12🎷") == 12 and parse_vol("kein Titel") is None
    d = "Text\nChapters\n00:00 A One\n02:57 B Two\n01:00:51 C Three\n\nMusic by"
    assert parse_chapters(d) == ["A One", "B Two", "C Three"], parse_chapters(d)
    assert round(iso_minutes("PT1H3M45S"), 2) == 63.75
    vids = [{"title": "Vol. 8", "id": "a", "published": "1"}, {"title": "Vol. 8", "id": "b", "published": "2"}]
    assert check_vols(vids, r)["id"] == "b" and r.problems
    r2 = Report()
    check_titles({"x": ["Lantern Hours"] + [f"T{i}" for i in range(21)], "y": [f"U{i}" for i in range(22)]}, {"x": 11, "y": 12}, r2)
    assert any("alte Liste" in f.text for f in r2.problems) and any(f.level == "OK" for f in r2.findings)
    assert classify_genre("Cozy Winter Cabin · 3 Hours Relaxing Fireplace") == "cabin" and classify_genre("Italian Amalfi Coast Dinner") == "italian"
    t0 = datetime(2026, 10, 26, tzinfo=timezone.utc)
    gv = [{"title": "Cozy Winter Cabin Fireplace", "desc": "x", "minutes": 90, "id": "c1", "published": "2026-10-10T08:00:00Z", "privacy": "public"}]
    gf = genre_findings(gv, t0, {"Cozy Winter Cabin · Relaxing Fireplace Chillout 4K": set()}, {"c1": 20.0})
    assert any("nur 90 Min" in t for _l, t in gf) and any("Playlist" in t for _l, t in gf) and any("Grenze" in t for _l, t in gf) and any("seit 15 Tagen" in t for _l, t in gf), gf
    print("Selbsttest bestanden")
    return 0


# ------------------------------------------------------------------ Lesen
def dhash(img, n=16):
    from PIL import Image
    g = img.convert("L").resize((n + 1, n), Image.LANCZOS)
    px = list(g.getdata())
    return [1 if px[y * (n + 1) + x] > px[y * (n + 1) + x + 1] else 0 for y in range(n) for x in range(n)]


def dist(a, b):
    return sum(x != y for x, y in zip(a, b))


def thumb_state(video_id: str, ref_thumb: bytes | None, ref_master: bytes | None):
    """True = eigenes Thumbnail (Text), False = automatisches Standbild, None = nicht prüfbar."""
    import io
    import requests
    from PIL import Image
    if not ref_thumb or not ref_master:
        return None
    try:
        r = requests.get(f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg", timeout=30)
        if r.status_code != 200:
            return None
        h = dhash(Image.open(io.BytesIO(r.content)))
        d_t = dist(h, dhash(Image.open(io.BytesIO(ref_thumb))))
        d_m = dist(h, dhash(Image.open(io.BytesIO(ref_master))))
        return d_t < d_m
    except Exception:  # noqa: BLE001
        return None


def load_videos(yt, days: int):
    up = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, tok = [], None
    for _ in range(3):
        r = yt.playlistItems().list(part="contentDetails", playlistId=up, maxResults=50, pageToken=tok).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        tok = r.get("nextPageToken")
        if not tok:
            break
    out = []
    for i in range(0, len(ids), 50):
        for d in yt.videos().list(part="snippet,status,contentDetails", id=",".join(ids[i:i + 50])).execute()["items"]:
            out.append({"id": d["id"], "title": d["snippet"]["title"], "desc": d["snippet"].get("description", ""),
                        "published": d["snippet"]["publishedAt"], "privacy": d["status"]["privacyStatus"],
                        "minutes": iso_minutes(d["contentDetails"]["duration"]), "publish_at": d["status"].get("publishAt")})
    return out


def playlist_ids(yt, pid):
    s, tok = set(), None
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=pid, maxResults=50, pageToken=tok).execute()
        s |= {i["contentDetails"]["videoId"] for i in r["items"]}
        tok = r.get("nextPageToken")
        if not tok:
            return s


def drive_folders(svc):
    """Alle Tokyo-Tagesmix-Ordner (nicht Mega-Mix): name, id, createdTime."""
    q = "name contains 'Tokyo Work Lounge' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    res, tok = [], None
    while True:
        r = svc.files().list(q=q, fields="nextPageToken,files(id,name,createdTime,parents)", pageSize=100, pageToken=tok).execute()
        res += r.get("files", [])
        tok = r.get("nextPageToken")
        if not tok:
            break
    return [f for f in res if "MEGAMIX" not in f["name"].upper() and re.match(r"^\d{4}-\d{2}-\d{2} – Tokyo Work Lounge", f["name"])]


def folder_contents(svc, fid):
    kids = svc.files().list(q=f"'{fid}' in parents and trashed = false", fields="files(id,name,mimeType,size)", pageSize=100).execute()["files"]
    mp3 = None
    for k in kids:
        if k["name"] == "mp3" and k["mimeType"].endswith("folder"):
            mp3 = svc.files().list(q=f"'{k['id']}' in parents and trashed = false", fields="files(id,name,size,md5Checksum)", pageSize=100).execute()["files"]
    return kids, mp3 or []


# ------------------------------------------------------------------ Hauptprüfung
def run(args) -> Report:
    from pipeline import drive, memory, youtube
    rep = Report()
    now = datetime.now(BERLIN)
    today = now.date().isoformat()
    yt = youtube.service()
    vids = load_videos(yt, args.days)
    # Shorts (kurz, "#shorts" im Titel) sind KEINE Mixe (Fehler 26.10.2026: Wächter hat Shorts als Mix bewertet und in die Mix-Playlist eingetragen)
    def is_short(v):
        return v["minutes"] < 20 or "#shorts" in v["title"].lower()
    tokyo = [v for v in vids if "Tokyo Work Lounge" in v["title"] and "Hours Long Mix" not in v["title"] and not is_short(v)]
    tokyo_shorts = [v for v in vids if "Tokyo Work Lounge" in v["title"] and is_short(v)]
    mega = [v for v in vids if "Tokyo Work Lounge" in v["title"] and "Hours Long Mix" in v["title"]]
    tokyo.sort(key=lambda v: v["published"], reverse=True)
    vols = {v["id"]: parse_vol(v["title"]) for v in tokyo}
    mem = memory.load()
    svc = drive.service()
    pid = youtube.ensure_playlist(*PLAYLIST) if args.fix else None
    if pid is None:
        r = yt.playlists().list(part="snippet", mine=True, maxResults=50).execute()
        pid = next((p["id"] for p in r["items"] if p["snippet"]["title"] == PLAYLIST[0]), None)
    in_pl = playlist_ids(yt, pid) if pid else set()
    if not pid:
        rep.add("WARN", "Playlist „Tokyo Work Lounge · Slow Jazz for Work and Coding“ nicht gefunden")

    # 0) Shorts gehören nicht in die Mix-Playlist: entfernen (reversibel)
    if pid and args.fix and tokyo_shorts:
        sids = {v["id"] for v in tokyo_shorts}
        tok = None
        try:
            while True:
                r = yt.playlistItems().list(part="contentDetails", playlistId=pid, maxResults=50, pageToken=tok).execute()
                for it in r["items"]:
                    if it["contentDetails"]["videoId"] in sids:
                        yt.playlistItems().delete(id=it["id"]).execute()
                        rep.add("FEHLER", f"Short {it['contentDetails']['videoId']} stand in der Mix-Playlist", fixed="entfernt")
                tok = r.get("nextPageToken")
                if not tok:
                    break
        except Exception as e:  # noqa: BLE001
            rep.add("WARN", f"Shorts in der Mix-Playlist nicht entfernbar: {str(e)[:120]}")

    # 1) Mix von heute
    def local_date(v):
        return datetime.fromisoformat(v["published"].replace("Z", "+00:00")).astimezone(BERLIN).date().isoformat()
    todays = [v for v in tokyo if local_date(v) == today]
    if now.hour >= 8:
        if todays:
            v = todays[0]
            rep.add("OK", f"Heutiger Tokyo-Mix ist online: {v['title']} (https://youtu.be/{v['id']}, {v['minutes']:.0f} Min)")
            rep.did.append(f"{local_date(v)} Tokyo-Mix {v['title'][-12:]} hochgeladen")
        else:
            rep.add("FEHLER", "Heute ist noch KEIN Tokyo-Mix auf YouTube (Tagesmix läuft um 6:07 und braucht ca. 1 Std.)")

    # 2) je Mix der letzten Tage: Sichtbarkeit, Dauer, Playlist, Thumbnail
    recent = [v for v in tokyo if (now - datetime.fromisoformat(v["published"].replace("Z", "+00:00"))).days < args.days]
    folders = drive_folders(svc)
    for v in recent:
        d = local_date(v)
        tag = f"Vol. {vols[v['id']]} ({d})"
        if v["privacy"] != "public":
            if args.fix and d == today and v["privacy"] == "private":
                try:
                    youtube.set_public(v["id"])
                    rep.add("FEHLER", f"{tag}: war noch privat", fixed="auf öffentlich gestellt")
                except Exception as e:  # noqa: BLE001
                    rep.add("FEHLER", f"{tag}: privat, Umstellen schlug fehl: {str(e)[:150]}")
            else:
                rep.add("WARN", f"{tag}: Sichtbarkeit {v['privacy']}")
        if not 55 <= v["minutes"] <= 75:
            rep.add("WARN", f"{tag}: Dauer {v['minutes']:.0f} Min (erwartet 55–75)")
        if pid and v["id"] not in in_pl:
            if args.fix:
                ok, err = youtube.retry(lambda: youtube.add_to_playlist(v["id"], pid), tries=2, wait=20, label="Wächter Playlist")
                rep.add("FEHLER", f"{tag}: nicht in der Playlist", fixed="eingetragen" if ok else f"Eintragen fehlgeschlagen: {err[:120]}")
            else:
                rep.add("FEHLER", f"{tag}: nicht in der Playlist")
        # Thumbnail
        fl = next((f for f in folders if f["name"].startswith(d)), None)
        ref_t = ref_m = None
        if fl:
            kids, _ = folder_contents(svc, fl["id"])
            by = {k["name"]: k["id"] for k in kids}
            try:
                if "thumb.jpg" in by and "master.jpg" in by:
                    ref_t = svc.files().get_media(fileId=by["thumb.jpg"]).execute()
                    ref_m = svc.files().get_media(fileId=by["master.jpg"]).execute()
            except Exception:  # noqa: BLE001
                pass
        st = thumb_state(v["id"], ref_t, ref_m)
        if st is False:
            if args.fix and ref_t:
                import tempfile
                p = Path(tempfile.mkdtemp()) / "thumb.jpg"
                p.write_bytes(ref_t)
                ok, err = youtube.retry(lambda: youtube.set_thumbnail(v["id"], p), tries=2, wait=20, label="Wächter Thumbnail")
                rep.add("FEHLER", f"{tag}: Thumbnail fehlte", fixed="gesetzt" if ok else f"Setzen fehlgeschlagen: {err[:120]}")
            else:
                rep.add("FEHLER", f"{tag}: Thumbnail fehlt (automatisches Standbild)")
        elif st is None:
            rep.add("INFO", f"{tag}: Thumbnail nicht prüfbar")

    # 3) Titelnummern
    bad = check_vols(tokyo, rep)
    if bad and args.fix and bad["id"] == tokyo[0]["id"]:
        newv = max(v for v in vols.values() if v) + 1
        if newv - 1 == vols[bad["id"]]:
            newv = newv  # nächste freie Nummer
        new_title = re.sub(r"Vol\.\s*\d+", f"Vol. {newv}", bad["title"])
        try:
            sn = yt.videos().list(part="snippet", id=bad["id"]).execute()["items"][0]["snippet"]
            sn["title"] = new_title
            yt.videos().update(part="snippet", body={"id": bad["id"], "snippet": sn}).execute()
            rep.add("FEHLER", f"Neuester Mix hatte doppelte Nummer", fixed=f"Titel auf Vol. {newv} geändert")
        except Exception as e:  # noqa: BLE001
            rep.add("FEHLER", f"Titel-Korrektur fehlgeschlagen: {str(e)[:150]}")

    # 4) Songtitel (Kapitel in den Beschreibungen aller Tokyo-Tagesmixe)
    chaps = {v["id"]: parse_chapters(v["desc"]) for v in tokyo}
    check_titles(chaps, vols, rep)
    leg = [f"Vol. {vols[i]}" for i, c in chaps.items() if (vols.get(i) or 0) < NEW_TITLE_RULE_FROM_VOL and c]
    if leg:
        rep.add("INFO", f"{len(leg)} ältere Mixe (bis Vol. 10, Titel stammen aus der alten festen Liste) – bekannt, bleiben unverändert")

    # 5) Drive: Pakete und doppelte Audiodateien
    md5_owner: dict[str, str] = {}
    dup_pairs = []
    for f in sorted(folders, key=lambda f: f["name"], reverse=True)[:args.drive_folders]:
        kids, mp3 = folder_contents(svc, f["id"])
        names = {k["name"] for k in kids}
        miss = [n for n in ("album_3000.png", "thumb.jpg", "master.jpg", "metadata.txt") if n not in names]
        v2 = " v2" in f["name"]
        if len(mp3) != 22 or miss:
            if f["name"][:10] == today and now.hour < 8:
                continue
            rep.add("WARN", f"Drive „{f['name'][:48]}“: {len(mp3)} MP3, fehlend: {miss}")
        for m in mp3:
            h = m.get("md5Checksum")
            if not h:
                continue
            if h in md5_owner and md5_owner[h] != f["name"] and not v2 and " v2" not in md5_owner[h]:
                dup_pairs.append((m["name"], md5_owner[h][:10], f["name"][:10]))
            md5_owner.setdefault(h, f["name"])
    if dup_pairs:
        rep.add("FEHLER", f"Identische Audiodateien in verschiedenen Mixen: {dup_pairs[:6]} (insgesamt {len(dup_pairs)})")
    else:
        rep.add("OK", f"Drive: keine identischen Audiodateien in den letzten {args.drive_folders} Tokyo-Ordnern")

    # 6) Gedächtnis
    entries = [e for e in mem.get("tokyo", []) if e.get("date") == today]
    if todays and not entries and now.hour >= 9:
        rep.add("WARN", "Heutiger Mix fehlt im Gedächtnis (memory.json, Liste „tokyo“)")
    for e in entries:
        v = next((x for x in tokyo if x["id"] == e.get("video_id")), None)
        if v and e.get("vol") != vols.get(v["id"]):
            rep.add("WARN", f"Gedächtnis: Vol. {e.get('vol')} ≠ YouTube Vol. {vols.get(v['id'])}")
        if (e.get("vol") or 0) >= NEW_TITLE_RULE_FROM_VOL and len(e.get("track_titles") or []) != 22:
            rep.add("WARN", f"Gedächtnis: Vol. {e.get('vol')} ohne 22 gespeicherte Songtitel")
        if (e.get("cost_usd") or 0) > 4.0:
            rep.add("WARN", f"Kosten heute {e.get('cost_usd')} $ (normal ca. 1,8–2,5 $)")
        rep.did.append(f"Gedächtnis: Eintrag {e.get('date')} Raum {e.get('room')}, {e.get('songs')} Songs, {e.get('cost_usd')} $")

    # 7) Short des Tages (abends Pflicht: öffentlich)
    sh = [e for e in mem.get("shorts2", []) if e.get("tokyo") and e.get("date") == today]
    if sh and now.hour >= 21:
        d = yt.videos().list(part="status", id=sh[0]["video_id"]).execute()["items"]
        if d and d[0]["status"]["privacyStatus"] != "public":
            fixed_short = False
            if getattr(args, "fix", False):
                try:   # Abendaufgabe 19:45 lief nicht: Short selbst öffentlich schalten (umkehrbar, kostenlos; Related-Link nur in Studio möglich)
                    st = d[0]["status"]
                    st.pop("publishAt", None)
                    st["privacyStatus"] = "public"
                    yt.videos().update(part="status", body={"id": sh[0]["video_id"], "status": st}).execute()
                    fixed_short = True
                except Exception as ex:  # noqa: BLE001
                    rep.add("INFO", f"Short konnte nicht öffentlich geschaltet werden: {str(ex)[:80]}")
            if fixed_short:
                rep.add("WARN", f"Tokyo-Short von heute war um {now:%H:%M} noch privat (Verknüpfung 19:45 lief nicht) – Wächter hat ihn öffentlich geschaltet; Related-Video-Link fehlt (nur in Studio setzbar)", fixed="Short öffentlich geschaltet")
            else:
                rep.add("WARN", f"Tokyo-Short von heute ist um {now:%H:%M} noch {d[0]['status']['privacyStatus']} (Verknüpfung 19:45 lief nicht?)")
        elif d:
            rep.add("OK", "Tokyo-Short von heute ist öffentlich")
    elif not sh and now.hour >= 9 and todays:
        rep.add("WARN", "Kein Tokyo-Short von heute im Gedächtnis (shorts2)")

    # 8) Mega-Mix (Sonntag)
    for v in sorted(mega, key=lambda v: v["published"], reverse=True)[:1]:
        if local_date(v) == today:
            rep.add("OK" if v["minutes"] >= 360 and v["privacy"] == "public" else "WARN",
                    f"Tokyo-Mega-Mix heute: {v['minutes'] / 60:.1f} Std., {v['privacy']}")
    if now.weekday() == 6 and now.hour >= 12 and not any(local_date(v) == today for v in mega):
        rep.add("FEHLER", "Sonntag: Tokyo-Mega-Mix fehlt (läuft 8:07, mehrere Stunden)")

    # 9) ALLE ANDEREN MIXE (Italienisch, Cabin, Ibiza, Sleep, Mega-Mixe …): allgemeine Prüfung
    other = [v for v in vids if v not in tokyo and v["minutes"] >= 25 and
             (now - datetime.fromisoformat(v["published"].replace("Z", "+00:00"))).days < max(args.days, 7)]
    playlists, pl_titles = {}, {}
    try:
        pls = yt.playlists().list(part="snippet", mine=True, maxResults=50).execute()["items"]
    except Exception as e:  # noqa: BLE001
        pls = []
        rep.add("INFO", f"Playlists nicht lesbar: {str(e)[:100]}")
    unreadable, unread_err = [], []
    for pl in pls:   # jede Playlist einzeln: eine nicht lesbare (z. B. private/Systemliste) darf die anderen nicht blockieren
        try:
            playlists[pl["id"]] = playlist_ids(yt, pl["id"])
            pl_titles[pl["snippet"]["title"]] = playlists[pl["id"]]
        except Exception as e:  # noqa: BLE001
            unreadable.append(pl["snippet"]["title"][:30])
            unread_err.append(str(e))
    if unreadable and any("quota" in x.lower() for x in unread_err):
        rep.add("WARN", f"YouTube-Tageskontingent (Quota) aufgebraucht: {len(unreadable)} Playlists konnten nicht gelesen werden – Playlist-Prüfungen (z. B. Cabin/Italienisch in der Playlist) sind in diesem Lauf NICHT zuverlässig")
    elif unreadable:
        rep.add("INFO", f"{len(unreadable)} Playlists nicht lesbar (YouTube-Fehler, übersprungen), z. B.: {', '.join(unreadable[:4])}. Letzter Fehler: {unread_err[-1][:90]}")
    all_mem_ids = {e.get("video_id") for k, lst in mem.items() if isinstance(lst, list) for e in lst if isinstance(e, dict)}
    for v in sorted(other, key=lambda v: v["published"], reverse=True):
        tag = f"{v['title'][:60]} ({local_date(v)}, {v['minutes']:.0f} Min, https://youtu.be/{v['id']})"
        if v["privacy"] != "public":
            sched = v.get("publish_at")
            rep.add("INFO" if sched else "WARN", f"{tag}: {v['privacy']}" + (f", geplant für {sched}" if sched else " – bewusst?"))
        if playlists and not any(v["id"] in ids for ids in playlists.values()):
            rep.add("WARN", f"{tag}: in KEINER Playlist")
        ch = parse_chapters(v["desc"])
        if len(ch) != len({c.lower() for c in ch}) and "Hours Long" not in v["title"] and "Long Mix" not in v["title"]:
            rep.add("WARN", f"{tag}: doppelte Kapiteltitel im selben Video")
        if v["id"] not in all_mem_ids and (now - datetime.fromisoformat(v["published"].replace("Z", "+00:00"))).days >= 1:
            rep.add("WARN", f"{tag}: nicht im Gedächtnis (memory.json)")
    # Thumbnail aller Mixe: automatisches Standbild erkennen (maxres fehlt)
    import requests
    for v in other:
        try:
            if requests.get(f"https://i.ytimg.com/vi/{v['id']}/maxresdefault.jpg", timeout=20).status_code != 200:
                rep.add("WARN", f"{v['title'][:50]}: kein hochauflösendes Thumbnail (maxres fehlt)")
        except Exception:  # noqa: BLE001
            pass
    # Genre-Prüfungen (Cabin, Italienisch, Ibiza, Sleep/Spa/Lounge, Mega-Mixe) über die letzten 21 Tage
    wide = [v for v in vids if v not in tokyo and v["minutes"] >= 25 and "Tokyo Work Lounge" not in v["title"]
            and (now - datetime.fromisoformat(v["published"].replace("Z", "+00:00"))).days < 21]
    mem_cost = {e.get("video_id"): float(e.get("cost_usd") or 0) for k, lst in mem.items() if isinstance(lst, list) for e in lst if isinstance(e, dict) and e.get("video_id")}
    for lvl, txt in genre_findings(wide, now, pl_titles, mem_cost):
        rep.add(lvl, txt)
    wd = now.weekday()
    if wd == 5 and now.hour >= 14 and not any(local_date(v) == today and v["minutes"] >= 240 for v in vids):
        rep.add("WARN", "Samstag: kein Mega-Mix (≥ 4 Std.) von heute gefunden")
    n_ok = len([v for v in other if v["privacy"] == "public"])
    rep.add("INFO", f"Weitere Mixe der letzten 7 Tage geprüft: {len(other)} (davon öffentlich: {n_ok})")

    return rep


# ------------------------------------------------------------------ Bericht
# Erklärungen in einfacher Sprache: (Suchtext im Fund, „Was heißt das?“, „Warum ist das wichtig?“, „Was ist zu tun, wenn es nicht repariert wurde?“)
EXPLAIN = [
    ("nicht in der Playlist", "Das Video steht nicht in der Playlist „Tokyo Work Lounge“.",
     "Zuschauer, die eine Folge fertig geschaut haben, bekommen sonst nicht automatisch die nächste angezeigt; das kostet Wiedergabezeit.",
     "Der Wächter trägt das Video selbst ein. Schlägt das fehl, steht der YouTube-Fehlertext dabei."),
    ("Thumbnail fehl", "Das Video hat kein eigenes Vorschaubild, YouTube zeigt nur ein zufälliges Standbild.",
     "Das Vorschaubild entscheidet, ob jemand klickt. Ohne eigenes Bild gehen Aufrufe verloren.",
     "Der Wächter lädt das Bild `thumb.jpg` aus dem Drive-Ordner des Mixes hoch."),
    ("Dauer", "Die Länge des Videos passt nicht zum Erwarteten (ein Tokyo-Mix dauert normal 55 bis 75 Minuten).",
     "Ist der Mix zu kurz, fehlen Songs oder der Bau ist abgebrochen; ist er viel zu lang, ist etwas doppelt gemischt.",
     "Prüfen, ob Songs fehlen (Drive-Ordner, Kapitelliste) und ob der Lauf abgebrochen wurde."),
    ("Sichtbarkeit", "Das Video ist nicht öffentlich.",
     "Nicht öffentliche Videos sehen Zuschauer nicht und bringen keine Aufrufe.",
     "Gehört es zum heutigen Mix, stellt der Wächter es selbst auf öffentlich. Shorts bleiben bis 19:45 bewusst privat."),
    ("Doppelte Titelnummer", "Zwei Mixe tragen dieselbe Vol.-Nummer.",
     "Doppelte Nummern verwirren Zuschauer und DistroKid-Alben und wirken unprofessionell.",
     "Der Wächter ändert die Nummer des neuesten Mixes auf die nächste freie."),
    ("Titelnummern springen", "Die Nummern der Mixe sind nicht lückenlos (z. B. Vol. 8, dann Vol. 10).",
     "Eine Lücke kann ein fehlender oder umbenannter Mix sein.",
     "Prüfen, ob ein Mix fehlt oder von Hand umbenannt wurde."),
    ("Songtitel nicht neu", "Songtitel wiederholen sich (alte Standardliste oder schon in einem anderen Mix benutzt).",
     "Du hast festgelegt: kein Songtitel wird zweimal benutzt. Doppelte Titel können bei DistroKid und YouTube Ärger machen.",
     "Neue Titel erzeugen und in Beschreibung, Kapiteln und MP3-Namen ersetzen."),
    ("keine identischen Audio", "Es gibt keine identischen Audiodateien in verschiedenen Mixen.", "So ist sichergestellt, dass jeder Mix neue Musik hat.", ""),
    ("Identische Audiodateien", "Dieselbe Musikdatei steckt in mehreren Mixen.",
     "Wiederverwendete Musik unter neuem Namen wäre ein ernstes Problem bei DistroKid und YouTube.",
     "Ursache klären (bewusste Kopie wie ein v2-Mix oder Fehler im Lauf) und beheben."),
    ("Drive", "Das Drive-Paket eines Mixes ist nicht vollständig (erwartet: 22 MP3s, Cover, Thumbnail, Hauptbild, metadata.txt).",
     "Das Paket brauchst du für DistroKid und als Sicherung.",
     "Fehlende Dateien aus dem Bau nachladen. Bei alten Ordnern (vor dem 19.10.) ist ein fehlendes Cover bekannt und kein neuer Fehler."),
    ("gespeicherte Songtitel", "Im Gedächtnis fehlen die 22 Songtitel dieses Mixes.",
     "Ohne gespeicherte Titel kann der nächste Mix nicht sicher prüfen, ob ein Titel schon benutzt wurde.",
     "Titel aus Drive-Ordner oder Beschreibung nachtragen."),
    ("Gedächtnis", "Der Mix steht nicht oder falsch im Gedächtnis (Datei memory.json).",
     "Das Gedächtnis steuert Nummern, Räume, Sprüche und Songtitel der nächsten Mixe; Lücken führen zu Doppelungen.",
     "Eintrag nachtragen."),
    ("kostete", "Dieser Lauf hat mehr gekostet als die Grenze für dieses Genre.", "Dein Budget ist begrenzt (Cabin 9 €, Tokyo ca. 2 $).",
     "Bei älteren Läufen (z. B. Cabin vom 21.10., Ursache: zu viele Veo-Clips) ist es bekannt und seit 21.10. per Kostengrenze im Code abgesichert; nur frische Läufe (letzte 2 Tage) gelten als Warnung."),
    ("Kosten", "Der Lauf hat mehr gekostet als üblich.", "Dein Budget ist begrenzt (Tokyo ca. 2 $, Cabin 9 €).",
     "Ursache finden (Bild mehrfach erzeugt? Neustart?). Mehrkosten über dem Budget meldet der Wächter dir."),
    ("Short", "Zum heutigen Mix fehlt der Short oder er ist nicht wie geplant öffentlich.",
     "Shorts bringen neue Zuschauer; sie sollen ab 19:45 öffentlich und mit dem Mix verknüpft sein.",
     "Die Abendaufgabe (19:45) verknüpft ihn; fehlt sie, startet der Wächter eine Vertretung."),
    ("kein neuer Mix", "Von diesem Genre ist länger kein neuer Mix erschienen als üblich.",
     "Jedes Genre hat eine Zielzahl pro Woche (Italienisch etwa alle 2 Tage, Cabin 2× pro Woche). Ausfälle kosten Aufrufe und Wiedergabezeit.",
     "Die Wächter-Sitzung prüft, ob die geplante Aufgabe gelaufen ist, und startet bei Bedarf eine Vertretung, sofern es noch keinen Upload gibt."),
    ("Platzhalter", "Im Titel oder in der Beschreibung steht noch ein Entwurfsrest (z. B. {URL} oder TODO).",
     "Zuschauer sehen den Rest öffentlich; das wirkt unfertig.", "Der Wächter korrigiert Beschreibung/Titel (Umbenennen ist ihm erlaubt) und meldet es."),
    ("Beschreibung ist leer", "Das Video hat keine Beschreibung.", "Ohne Beschreibung fehlen Kapitel, Stichwörter und Links; YouTube versteht das Video schlechter.", "Beschreibung ergänzen."),
    ("Genre nicht erkannt", "Der Wächter konnte nicht erkennen, zu welchem Genre das Video gehört.", "Er prüft es dann nur allgemein.", "Stichwort in `GENRES` in waechter.py ergänzen."),
    ("steht nicht in der Playlist", "Das Video steht nicht in der Playlist seines Genres.", "Zuschauer finden es dort nicht, und die Playlist verliert Wiedergabezeit.", "Der Wächter trägt es ein."),
    ("Songtitel in mehreren Mixen", "Derselbe Songtitel kommt in mehreren Mixen desselben Genres vor.", "Du willst keine doppelten Songnamen.", "Ursache klären; bei neuen Mixen neue Titel erzeugen."),
    ("Mega-Mix", "Es geht um den langen Mega-Mix (Samstag/Sonntag).", "Er soll mehrere Stunden lang und öffentlich sein.", "Länge und Sichtbarkeit prüfen."),
    ("Tageskontingent", "YouTube erlaubt pro Tag nur eine begrenzte Menge an Abfragen (Quota); sie ist heute aufgebraucht.", "Solange das Kontingent leer ist, kann der Wächter Playlists nicht prüfen und Reparaturen (Thumbnail, Playlist) scheitern.", "Das Kontingent füllt sich täglich um Mitternacht kalifornischer Zeit wieder auf (in Berlin 8:00 Uhr, ab dem 2.11. 9:00 Uhr; es kann danach noch einige Zeit dauern); der nächste Lauf prüft dann alles. Reparaturen werden dann nachgeholt."),
    ("nicht lesbar", "Der Wächter konnte eine einzelne Playlist nicht von YouTube lesen (Fehler 403 = YouTube verweigert den Zugriff auf genau diese Liste, z. B. eine private oder vom System geführte Liste).",
     "Das betrifft nur diese eine Liste; die Freigabe des Kanals ist vollständig. Alle anderen Playlists werden normal geprüft.",
     "Nichts zu tun, solange die Mix-Playlists lesbar sind."),
    ("nicht prüfbar", "Der Wächter konnte diesen Punkt nicht lesen.", "Was er nicht lesen kann, kann er nicht bestätigen.", "Bleibt offen und wird von Hand oder nach einer Berechtigungs-Erweiterung geprüft."),
    ("Der Wächter konnte selbst nicht prüfen", "Der Wächter selbst ist über einen Fehler gestolpert.",
     "In diesem Lauf wurde nichts richtig geprüft, du siehst den Kanal also im Blindflug.",
     "Die Wächter-Sitzung untersucht die Ursache und repariert den Code; die nächste Meldung zeigt, ob es klappt."),
]


def explain(f: Finding):
    if "tageskontingent" in f.text.lower():   # Quota hat Vorrang (Text enthält auch „nicht lesbar“)
        for key, was, warum, tun in EXPLAIN:
            if key == "Tageskontingent":
                return was, warum, tun
    if "nicht lesbar" in f.text.lower():   # sonst greift fälschlich „Short“ bei Playlist-Namen
        for key, was, warum, tun in EXPLAIN:
            if key == "nicht lesbar":
                return was, warum, tun
    for key, was, warum, tun in EXPLAIN:
        if key.lower() in f.text.lower():
            return was, warum, tun
    return ("", "", "") if f.level in ("OK", "INFO") else ("Das ist eine Auffälligkeit, für die der Wächter noch keine Standarderklärung hat.", "Sie weicht von deinen Regeln ab.", "Die Wächter-Sitzung untersucht sie; ihr Ergebnis steht oben unter „Ermittlung der Wächter-Sitzung“.")


def render(rep: Report, now: datetime, notes: str = ""):
    order = {"FEHLER": 0, "WARN": 1, "OK": 2, "INFO": 3}
    fs = sorted(rep.findings, key=lambda f: order[f.level])
    errs = [f for f in fs if f.level == "FEHLER" and not f.fixed]
    fixed = [f for f in fs if f.fixed]
    warns = [f for f in fs if f.level == "WARN"]
    oks = [f for f in fs if f.level == "OK"]
    infos = [f for f in fs if f.level == "INFO"]
    n_err, n_fix, n_warn = len(errs), len(fixed), len(warns)
    status = "ALLES IN ORDNUNG" if not (n_err or n_warn or n_fix) else f"{n_err} offene Fehler, {n_warn} Warnungen, {n_fix} selbst repariert"
    subj = f"[Wächter] {now:%d.%m. %H:%M} · {status}"
    if not (n_err or n_warn or n_fix):
        kurz = "Ich habe alles geprüft, was ich lesen kann. Es ist nichts schiefgegangen."
    else:
        kurz = (f"Selbst behoben: {n_fix}. Noch offene Fehler: {n_err}. Auffälligkeiten (Warnungen): {n_warn}. "
                + ("Offene Fehler brauchen Aufmerksamkeit: Details unten. " if n_err else "Es gibt keine offenen Fehler. ")
                + "Zu jedem Punkt steht unten, was es bedeutet, warum es wichtig ist und was passiert ist.")
    def block(f):
        was, warum, tun = explain(f)
        out = [f"• {f.text}"]
        if was: out.append(f"  Was heißt das? {was}")
        if warum: out.append(f"  Warum ist das wichtig? {warum}")
        if f.fixed: out.append(f"  Was habe ich getan? {f.fixed} – das ist erledigt.")
        elif tun: out.append(f"  Was passiert jetzt / was ist zu tun? {tun}")
        return out
    L = [f"WÄCHTER-BERICHT {now:%d.%m.%Y %H:%M} Uhr", status, "", "KURZ UND KLAR", kurz, ""]
    if notes.strip():
        L += ["ERMITTLUNG DER WÄCHTER-SITZUNG (selbst nachgeforscht: Befund, Beweis, Schluss, Maßnahme)", "", notes.strip(), ""]
    for title, items in (("SELBST REPARIERT", fixed), ("OFFENE FEHLER", errs), ("WARNUNGEN", warns)):
        if items:
            L += [title, ""]
            for f in items:
                L += block(f) + [""]
    if oks:
        L += ["DAS IST IN ORDNUNG", ""] + [f"• {f.text}" for f in oks] + [""]
    if infos:
        L += ["HINWEISE UND NICHT PRÜFBARES", ""]
        for f in infos:
            L += block(f) + [""]
    if rep.did:
        L += ["WAS HEUTE PASSIERT IST"] + [f"- {x}" for x in rep.did] + [""]
    L += ["GRENZEN: Der Wächter liest YouTube, Drive und das Gedächtnis. DistroKid, Instagram und TikTok kann er von hier nicht lesen; "
          "das steht dann als Hinweis im Bericht. Löschen und Umbenennen entscheidet er selbst und schreibt es dann hier hinein."]
    text = "\n".join(L)
    col = {"FEHLER": "#B31E1A", "WARN": "#B36B00", "OK": "#3F7D33", "INFO": "#5E5C55"}
    from html import escape as e
    H = [f"<div style='font-family:-apple-system,Arial,sans-serif;max-width:680px;color:#23211C;line-height:1.45'><h2 style='margin:0'>Wächter · {now:%d.%m.%Y %H:%M}</h2>",
         f"<p style='font-size:16px;font-weight:bold;margin:6px 0'>{e(status)}</p><p style='margin:0 0 14px'>{e(kurz)}</p>"]
    if notes.strip():
        H.append("<h3 style='margin:16px 0 4px'>Ermittlung der Wächter-Sitzung</h3><div style='white-space:pre-wrap;border:1px solid #E2DFD5;padding:8px'>" + e(notes.strip()) + "</div>")
    def hblock(f):
        was, warum, tun = explain(f)
        h = f"<div style='border-top:1px solid #E2DFD5;padding:8px 0'><b style='color:{col[f.level]}'>{e(f.text)}</b>"
        if was: h += f"<br><b>Was heißt das?</b> {e(was)}"
        if warum: h += f"<br><b>Warum ist das wichtig?</b> {e(warum)}"
        if f.fixed: h += f"<br><b style='color:#3F7D33'>Was habe ich getan?</b> {e(f.fixed)} – erledigt."
        elif tun: h += f"<br><b>Was passiert jetzt?</b> {e(tun)}"
        return h + "</div>"
    for title, items in (("Selbst repariert", fixed), ("Offene Fehler", errs), ("Warnungen", warns)):
        if items:
            H.append(f"<h3 style='margin:16px 0 4px'>{title}</h3>" + "".join(hblock(f) for f in items))
    if oks:
        H.append("<h3 style='margin:16px 0 4px'>Das ist in Ordnung</h3><ul>" + "".join(f"<li>{e(f.text)}</li>" for f in oks) + "</ul>")
    if infos:
        H.append("<h3 style='margin:16px 0 4px'>Hinweise und nicht Prüfbares</h3>" + "".join(hblock(f) for f in infos))
    if rep.did:
        H.append("<h3>Was heute passiert ist</h3><ul>" + "".join(f"<li>{e(x)}</li>" for x in rep.did) + "</ul>")
    H.append("<p style='color:#5E5C55;font-size:12px'>Grenzen: liest YouTube, Drive und Gedächtnis; DistroKid, Instagram und TikTok kann er von hier nicht lesen. Löschen und Umbenennen entscheidet er selbst und schreibt es dann hier hinein.</p></div>")
    return subj, text, "".join(H), bool(n_err or n_warn)


def send_mail(subj, text, html):
    from pipeline import mailer
    m = EmailMessage()
    m["To"], m["From"], m["Subject"] = REPORT_TO, "me", subj
    m.set_content(text)
    m.add_alternative(html, subtype="html")
    mailer._service().users().messages().send(userId="me", body={"raw": base64.urlsafe_b64encode(m.as_bytes()).decode()}).execute()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mail", action="store_true")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--drive-folders", type=int, default=12)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--notes-file", default="", help="Ermittlungen der Sitzung (Befund/Beweis/Schluss/Maßnahme je Fund); kommen in den Bericht")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    now = datetime.now(BERLIN)
    notes = Path(args.notes_file).read_text(encoding="utf-8") if args.notes_file and Path(args.notes_file).exists() else ""
    try:
        rep = run(args)
        rounds = [len(rep.problems)]
        while args.fix and any(f.fixed for f in rep.findings) and len(rounds) < 4:   # Sofort-Regel: nach Reparatur neu messen
            fixed_before = [f.fixed for f in rep.findings if f.fixed]
            rep2 = run(args)
            rounds.append(len(rep2.problems))
            rep2.findings += [Finding("INFO", f"Reparatur in Runde {len(rounds) - 1}: {x}") for x in fixed_before]
            rep2.did += rep.did
            rep = rep2
            if not any(f.fixed for f in rep.findings):
                break
        rep.did.append(f"Messrunden: {len(rounds)} (Probleme je Runde: {' → '.join(map(str, rounds))}); Vorher → Nachher: {rounds[0]} → {rounds[-1]}")
    except Exception as e:  # noqa: BLE001
        rep = Report()
        if "quota" in str(e).lower() or "exceeded your" in str(e).lower():
            rep.add("WARN", "YouTube-Tageskontingent (Quota) aufgebraucht: die Videoliste war nicht lesbar, dieser Lauf prüft YouTube NICHT (Tagesmix laut Gedächtnis vorhanden, siehe Notizen)")
            subj, text, html, issues = render(rep, now, notes)
            print(text)
            if args.mail:
                send_mail(subj, text, html)
            return 1
        rep.add("FEHLER", f"Der Wächter konnte selbst nicht prüfen: {type(e).__name__}: {str(e)[:300]}")
        subj, text, html, _ = render(rep, now, notes)
        print(text)
        if args.mail:
            try:
                send_mail(subj, text, html)
            except Exception as e2:  # noqa: BLE001
                print("Mail fehlgeschlagen:", e2)
        return 2
    subj, text, html, issues = render(rep, now, notes)
    print(text)
    try:   # Verlauf ins Gedächtnis (damit der nächste Lauf weiß, was der vorige gesehen hat)
        from pipeline import memory
        mem = memory.load()
        mem.setdefault("waechter", []).append({"at": now.isoformat(timespec="minutes"), "problems": len(rep.problems),
                                               "fixed": [f.fixed for f in rep.findings if f.fixed], "subject": subj})
        mem["waechter"] = mem["waechter"][-60:]
        memory.save(mem)
    except Exception as e:  # noqa: BLE001
        print("Gedächtnis nicht gespeichert:", str(e)[:120])
    if args.mail:
        send_mail(subj, text, html)
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
