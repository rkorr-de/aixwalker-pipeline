"""Social-Posts zu jedem Short: Instagram Reel (17:00) und TikTok (18:00) über Metricool.

Zwei Wege, je nachdem was in der Umgebung vorhanden ist:

A) METRICOOL_TOKEN gesetzt (Metricool-Tarif Advanced/Custom, zahlungspflichtig):
   Dieses Skript postet direkt per REST-API (`post_short`/`schedule`).

B) Kein METRICOOL_TOKEN (Standard-/kostenloser Tarif – unser Fall): Die REST-API ist bei Metricool nur in
   bezahlten Tarifen freigeschaltet; der kostenlose Metricool-MCP-Connector (in der täglichen Claude-Code-Sitzung
   verbunden) kann aber genauso Posts anlegen. Dieses Skript bereitet dann nur die Daten vor (`plan`) und schreibt
   sie nach `social_plan.json`; die Tages-Routine (KIDS_ROUTINE_PROMPT.md, Schritt 4d) liest diese Datei und ruft
   dafür selbst das MCP-Tool `createScheduledPost` auf – ohne zusätzliche Kosten.

Ablauf in beiden Fällen (nach dem YouTube-Upload):
1. short.mp4 und thumbnail.jpg aus dem Drive-Tagesordner per Link freigeben (jeder mit Link darf lesen – das Video
   ist ohnehin öffentlich). Metricool holt die Datei über diesen Link.
2. Texte je Plattform (Gemini, mit fester Vorlage als Fallback) – englisch, Eltern-Ansprache, Hashtags.
3a. (Weg A) Posts bei Metricool per REST anmelden (Token METRICOOL_TOKEN).
3b. (Weg B) Post-Daten nach social_plan.json schreiben, für das MCP-Tool in der Tages-Sitzung.

Umgebungsvariablen: METRICOOL_TOKEN (nur Weg A), METRICOOL_USER_ID (Standard 5602673), METRICOOL_BLOG_ID
(Standard 7233482), KIDS_SOCIAL_NETWORKS (Standard "instagram,tiktok"), KIDS_SOCIAL_TIMES
(Standard "instagram=17:00,tiktok=18:00"), KIDS_SOCIAL_DRAFT=1 → nur als Entwurf anlegen (nur Weg A, Test).
"""
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from . import config

BERLIN = ZoneInfo("Europe/Berlin")
API = "https://app.metricool.com/api"
USER_ID = os.environ.get("METRICOOL_USER_ID", "5602673")
BLOG_ID = os.environ.get("METRICOOL_BLOG_ID", "7233482")
NETWORKS = [n.strip() for n in os.environ.get("KIDS_SOCIAL_NETWORKS", "instagram,tiktok").split(",") if n.strip()]
TIMES = dict(p.split("=") for p in os.environ.get("KIDS_SOCIAL_TIMES", "instagram=17:00,tiktok=18:00").split(",") if "=" in p)
DRAFT = os.environ.get("KIDS_SOCIAL_DRAFT", "0") == "1"
HANDLE = os.environ.get("KIDS_SOCIAL_HANDLE", "gigglemeadowshorts")
YT_URL = "https://www.youtube.com/@GiggleMeadowShorts"

HASHTAGS = {
    "instagram": "#toddlermom #toddlerlife #cutecartoon #babyanimals #toddleractivities #calmkids #kidsvideos "
                 "#preschoolfun #momsofinstagram #dadsofinstagram #gigglemeadow",
    "tiktok": "#toddlersoftiktok #momtok #cutecartoon #babyanimals #calmvideo #kidsvideos #toddlermom "
              "#3danimation #gigglemeadow",
}


def available() -> bool:
    return bool(os.environ.get("METRICOOL_TOKEN"))


def _headers() -> dict:
    return {"X-Mc-Auth": config.require("METRICOOL_TOKEN"), "Content-Type": "application/json"}


# ---------------------------------------------------------------- Drive-Freigabe -----------------------------------
def share_links(drive_links: dict, names: tuple[str, ...] = ("short.mp4", "thumbnail.jpg")) -> dict:
    """Macht die genannten Dateien aus einem Drive-Ordner per Link lesbar; liefert direkte Download-URLs.
    `names` sind die Schlüssel in `drive_links` (wie von pipeline.drive/_upload zurückgegeben)."""
    from pipeline import drive as base
    svc = base.service()
    out = {}
    for name in names:
        link = drive_links.get(name, "")
        m = re.search(r"/d/([A-Za-z0-9_-]+)", link) or re.search(r"id=([A-Za-z0-9_-]+)", link)
        if not m:
            continue
        fid = m.group(1)
        try:
            svc.permissions().create(fileId=fid, body={"type": "anyone", "role": "reader"}, fields="id").execute()
        except Exception as e:  # noqa: BLE001
            print(f"[social] Freigabe {name}: {e}")
        out[name] = f"https://drive.google.com/uc?export=download&id={fid}"
    return out


# ---------------------------------------------------------------- Texte ----------------------------------------------
def _fallback_texts(story: dict) -> dict:
    c = story.get("character", {})
    name, species = c.get("name", "Our little friend"), c.get("species", "baby animal")
    theme = story.get("summary") or story.get("theme") or "a tiny adventure"
    hook = f"{name} the {species}: {theme}".rstrip(".") + " 🌼"
    ig = (f"{hook}\nA calm 15-second cartoon for toddlers – no talking, just giggles. Perfect for a quiet minute. 💛\n"
          f"New story every day at 4 pm CET → YouTube: Giggle Meadow (link in bio)\n\n{HASHTAGS['instagram']}")
    tt = (f"{hook} A calm little cartoon for toddlers – no talking, just giggles. 💛 New story daily on YouTube: "
          f"Giggle Meadow\n{HASHTAGS['tiktok']}")
    return {"instagram": ig[:2200], "tiktok": tt[:2200], "tiktok_title": (f"{name} & the {theme}"[:80])}


def texts(story: dict) -> dict:
    """Plattformtexte per Gemini (≈ 0,5 Cent), sonst feste Vorlage."""
    fb = _fallback_texts(story)
    try:
        from . import gemini
        prompt = (
            "Write social captions for a wordless 15-second Pixar-style cartoon for toddlers. Audience of the caption: "
            "PARENTS of children aged 1–5 (the platforms are not for kids). English, warm, no brand names, no known "
            f"characters.\nStory: {json.dumps({k: story.get(k) for k in ('title', 'theme', 'summary', 'character', 'lesson')})}\n"
            "Return JSON {\"instagram\": str (hook line with the character's name + what happens, 1 emoji; line 2: who it is "
            "for + why parents love it; line 3: 'New story every day at 4 pm CET → YouTube: Giggle Meadow (link in bio)'; "
            f"blank line; then exactly these hashtags: {HASHTAGS['instagram']}), "
            "\"tiktok\": str (2 short lines + 'New story daily on YouTube: Giggle Meadow' + these hashtags: "
            f"{HASHTAGS['tiktok']}; under 300 characters before hashtags), "
            "\"tiktok_title\": str (< 80 chars, the story in a few words)}"
        )
        data = gemini.text_json(prompt, "You are a social media manager for a family-friendly kids channel. JSON only.",
                                temperature=0.9)
        out = {k: str(data.get(k) or fb[k]) for k in ("instagram", "tiktok", "tiktok_title")}
        for k in ("instagram", "tiktok"):
            if "#gigglemeadow" not in out[k]:
                out[k] += "\n\n" + HASHTAGS[k]
        out["tiktok_title"] = out["tiktok_title"][:80]
        return out
    except Exception as e:  # noqa: BLE001
        print(f"[social] Texte per Gemini fehlgeschlagen, Vorlage: {e}")
        return fb


# ---------------------------------------------------------------- Metricool --------------------------------------------
def _when(network: str, today: datetime) -> datetime:
    hh, mm = (int(x) for x in TIMES.get(network, "17:00").split(":"))
    t = today.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if t < datetime.now(BERLIN) + timedelta(minutes=10):
        t = datetime.now(BERLIN) + timedelta(minutes=15)
    return t


def _build_info(network: str, text: str, video_url: str, thumb_url: str | None, title: str, draft: bool = False) -> dict:
    """Post-Inhalt für ein Netzwerk – gemeinsam für den REST-Weg (Token) und den MCP-Plan genutzt."""
    info = {
        "autoPublish": not draft, "draft": draft, "descendants": [], "firstCommentText": "", "hasNotReadNotes": False,
        "media": [video_url], "mediaAltText": [], "providers": [{"network": network}],
        "shortener": False, "smartLinkData": {"ids": []}, "text": text,
    }
    if network == "instagram":
        info["instagramData"] = {"type": "REEL", "showReelOnFeed": True, "isAiGenerated": True, "collaborators": []}
        if thumb_url:
            info["videoThumbnailUrl"] = thumb_url
    elif network == "tiktok":
        info["tiktokData"] = {"disableComment": True, "disableDuet": True, "disableStitch": True,
                              "privacyOption": "PUBLIC_TO_EVERYONE", "commercialContentThirdParty": False,
                              "commercialContentOwnBrand": False, "title": title, "autoAddMusic": False,
                              "photoCoverIndex": 0, "isAigc": True}
        if thumb_url:
            info["videoThumbnailUrl"] = thumb_url
    elif network == "facebook":
        info["facebookData"] = {"type": "REEL", "title": title}
    return info


def schedule(network: str, when: datetime, text: str, video_url: str, thumb_url: str | None, title: str) -> dict:
    """Legt einen Post in Metricool an (autoPublish, außer KIDS_SOCIAL_DRAFT=1). Liefert die Antwort (id, plannerUrl).
    Nur Weg A (METRICOOL_TOKEN, bezahlter Tarif) – siehe Moduldoku."""
    body = _build_info(network, text, video_url, thumb_url, title, draft=DRAFT)
    body["publicationDate"] = {"dateTime": when.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": "Europe/Berlin"}
    r = requests.post(f"{API}/v2/scheduler/posts", params={"userId": USER_ID, "blogId": BLOG_ID},
                      headers=_headers(), json=body, timeout=120)
    if r.status_code >= 300:
        # Thumbnail kann bei nicht verifizierten/persönlichen Konten abgelehnt werden → ohne Thumbnail erneut
        if "THUMBNAIL" in r.text.upper() and "videoThumbnailUrl" in body:
            body.pop("videoThumbnailUrl")
            r = requests.post(f"{API}/v2/scheduler/posts", params={"userId": USER_ID, "blogId": BLOG_ID},
                              headers=_headers(), json=body, timeout=120)
        if r.status_code >= 300:
            raise RuntimeError(f"Metricool {network} HTTP {r.status_code}: {r.text[:400]}")
    try:
        return r.json()
    except Exception:  # noqa: BLE001
        return {"raw": r.text[:300]}


def post_short(story: dict, drive_links: dict, today: str) -> dict:
    """Komplett: Freigabe → Texte → Posts je Netzwerk. Liefert {network: {when, result|error}}."""
    urls = share_links(drive_links)
    if "short.mp4" not in urls:
        raise RuntimeError("short.mp4 nicht im Drive-Ordner gefunden – keine Social-Posts")
    tx = texts(story)
    base_day = datetime.now(BERLIN).replace(year=int(today[:4]), month=int(today[5:7]), day=int(today[8:10]))
    out: dict = {"texts": tx, "media": urls, "draft": DRAFT}
    for net in NETWORKS:
        when = _when(net, base_day)
        try:
            res = schedule(net, when, tx.get(net, tx["instagram"]), urls["short.mp4"], urls.get("thumbnail.jpg"),
                           tx.get("tiktok_title", story.get("title", ""))[:80])
            out[net] = {"when": when.strftime("%d.%m.%Y %H:%M"), "result": res}
            print(f"[social] {net} geplant für {when:%d.%m. %H:%M}")
        except Exception as e:  # noqa: BLE001
            out[net] = {"when": when.strftime("%d.%m.%Y %H:%M"), "error": str(e)[:300]}
            print(f"[social] {net} fehlgeschlagen: {e}")
    return out


def plan(story: dict, drive_links: dict, today: str) -> dict:
    """Weg B (kein METRICOOL_TOKEN, kostenloser Tarif): bereitet die Post-Daten vor, postet aber nichts selbst.
    Die Tages-Routine ruft damit direkt das Metricool-MCP-Tool `createScheduledPost` auf (kostenlos, kein
    Tarif-Upgrade nötig). Liefert {"posts": [{"network", "date", "blogId", "info"}, ...], "texts": ..., "media": ...}."""
    urls = share_links(drive_links)
    if "short.mp4" not in urls:
        raise RuntimeError("short.mp4 nicht im Drive-Ordner gefunden – kein Social-Plan")
    tx = texts(story)
    base_day = datetime.now(BERLIN).replace(year=int(today[:4]), month=int(today[5:7]), day=int(today[8:10]))
    posts = []
    for net in NETWORKS:
        when = _when(net, base_day)
        info = _build_info(net, tx.get(net, tx["instagram"]), urls["short.mp4"], urls.get("thumbnail.jpg"),
                           tx.get("tiktok_title", story.get("title", ""))[:80])
        info["publicationDate"] = {"dateTime": when.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": "Europe/Berlin"}
        posts.append({"network": net, "date": when.isoformat(timespec="seconds"), "blogId": BLOG_ID, "info": info})
    return {"texts": tx, "media": urls, "posts": posts}


def plan_longshort(meta: dict, drive_links: dict, when: datetime) -> dict:
    """Langer Short (9:16, Mo/Mi/Fr) zusätzlich auf TikTok: TikTok zahlt im Creator Rewards Program nur für Videos
    über 1 Minute – die täglichen 15-s-Shorts zählen dort nicht, der lange Short schon. Gleicher kostenloser
    MCP-Weg wie `plan()`, aber nur TikTok und ohne feste Tageszeit (`when` von außen vorgegeben). Dateien liegen
    im Drive-Unterordner `langer-short/` unter den Namen `longshort.mp4`/`thumbnail_vertical.jpg`."""
    urls = share_links(drive_links, names=("longshort.mp4", "thumbnail_vertical.jpg"))
    if "longshort.mp4" not in urls:
        raise RuntimeError("longshort.mp4 nicht im Drive-Ordner gefunden – kein TikTok-Plan für den langen Short")
    title = str(meta.get("title", "Giggle Meadow"))
    caption = (f"{title}\nA cozy string of cute cartoons for toddlers – no talking, just giggles. 💛\n"
              f"New story every day at 4 pm CET on YouTube: Giggle Meadow\n{HASHTAGS['tiktok']}")[:2200]
    info = _build_info("tiktok", caption, urls["longshort.mp4"], urls.get("thumbnail_vertical.jpg"), title[:80])
    info["publicationDate"] = {"dateTime": when.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": "Europe/Berlin"}
    post = {"network": "tiktok", "date": when.isoformat(timespec="seconds"), "blogId": BLOG_ID, "info": info}
    return {"texts": {"tiktok": caption}, "media": urls, "posts": [post]}


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "build/kids/test1")
    res = json.loads((out / "result.json").read_text())
    print(json.dumps(post_short(res["story"], res.get("drive", {}), res["date"]), indent=2, ensure_ascii=False))
