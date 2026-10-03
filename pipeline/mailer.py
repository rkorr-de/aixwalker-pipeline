"""Bericht nach jedem Mix per E-Mail (Gmail API, Scope gmail.send; eigenes Refresh-Token GMAIL_REFRESH_TOKEN).

Inhalt: Links (Mix, Shorts, Drive), Titel, Beschreibung, Kapitel, Kosten, Community-Beitrag, angepinnter Kommentar
und alle Formularangaben für DistroKid. Anhänge: Thumbnail A und Album-Cover (verkleinert).
Ohne GMAIL_REFRESH_TOKEN wird der Bericht nur als Datei geschrieben (build/<slug>/report.md) – die Routine liefert
ihn dann im Chat.
"""
import base64
import io
import json
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from googleapiclient.discovery import build
from PIL import Image

from . import config, metadata


def _service():
    from . import youtube
    return build("gmail", "v1", credentials=youtube.credentials("GMAIL_REFRESH_TOKEN"), cache_discovery=False)


def _track_list(result: dict) -> list[tuple[str, str]]:
    rows = []
    for ln in (result.get("chapters") or "").splitlines():
        if " " in ln:
            ts, title = ln.split(" ", 1)
            rows.append((ts, title))
    return rows


def distrokid_block(concept: dict, result: dict) -> str:
    tracks = _track_list(result)
    drive = result.get("drive") or {}
    genre_map = {"gym": ("Electronic", "Trap / Beats"), "chillout": ("Electronic", "Ambient")}
    primary, secondary = genre_map.get(concept.get("playlist", "chillout"), ("Electronic", "Ambient"))
    short1 = (result.get("shorts") or [{}])[0]
    lines = [
        "DISTROKID – FORMULARANGABEN",
        f"Release-Typ: Album ({len(tracks)} Tracks)",
        f"Artist: {config.ARTIST}   (bestehendes Künstlerprofil wählen, kein neues anlegen)",
        f"Release-Titel: {concept['album']}",
        f"Label: {config.ARTIST}",
        f"Hauptgenre: {primary}   Nebengenre: {secondary}",
        "Sprache: Instrumental   Explicit: Nein   Compilation: Nein",
        f"Veröffentlichungsdatum: so bald wie möglich (Vorschlag {date.today().isoformat()})",
        f"Cover: album_3000.png (3000×3000) → {drive.get('album_3000.png', 'Drive-Ordner')}",
        f"Audio: alle Dateien aus dem Drive-Unterordner mp3/ in Reihenfolge 01–{len(tracks):02d}",
        "Songwriter/Komponist je Track: " + (config.DISTROKID_SONGWRITER or "dein bürgerlicher Name (DistroKid verlangt Klarnamen; Umgebungsvariable DISTROKID_SONGWRITER)"),
        "KI-Frage („Was AI used?“): JA – Musik mit Lyria 3.5 erzeugt, Cover mit Gemini Image",
        "Stores: alle, inkl. Spotify, Apple Music, YouTube Music, Amazon, TikTok, Instagram",
        f"Spotify-Preview-Start (Tipp): Track „{short1.get('track_title', '-')}“ bei der Stelle, aus der Short 1 geschnitten ist",
        "",
        "TRACKLISTE (Titel exakt so eintragen):",
    ]
    for i, (_, title) in enumerate(tracks, 1):
        lines.append(f"  {i:02d}. {title}")
    return "\n".join(lines)


def build_report(concept: dict, result: dict, estimate_usd: float | None = None) -> str:
    """Bericht als Markdown-Text (auch Mail-Text)."""
    shorts = result.get("shorts") or []
    drive = result.get("drive") or {}
    desc = result.get("description") or "(siehe metadata.txt)"
    eur = result.get("cost_eur")
    parts = [
        f"# {concept['album']} – {concept['genre']}, {concept['bpm']} BPM, {result.get('duration_min')} Min",
        "",
        f"Mix (ÖFFENTLICH): {result.get('video_url')}",
        *[f"Short {i + 1} (ÖFFENTLICH): {s.get('url')}  –  „{s.get('overlay')}“, {metadata.fmt_ts(s['start'])}–{metadata.fmt_ts(s['end'])}, Track {s.get('track_title')}"
          for i, s in enumerate(shorts)],
        f"Drive-Ordner: {drive.get('_folder', drive.get('error', '-'))}",
        "",
        f"Kosten des Laufs: {result.get('cost_usd', 0):.2f} $ ≈ {eur if eur is not None else '-'} €"
        + (f" (Voranschlag {estimate_usd:.2f} $)" if estimate_usd else ""),
        "",
        "## YouTube-Titel", result.get("title", ""),
        "", "## Beschreibung", desc,
        "", "## Kapitel", result.get("chapters", ""),
        "", "## Angepinnter Kommentar (in Studio anpinnen – API kann nicht pinnen)",
        concept.get("pinned_comment", ""),
        "", "## Community-Beitrag (Studio → Community, Text kopieren)",
        metadata.community_post(concept, result.get("video_url", "")),
        "", "## " + distrokid_block(concept, result),
        "", "## Noch zu tun (nur das, was die API nicht kann)",
        "- Kommentar anpinnen (Studio → Kommentare)",
        "- Community-Beitrag posten",
        "- Endscreen setzen: letzte 20 s → Playlist + Abonnieren",
        "- DistroKid-Release anlegen (Angaben oben)",
    ]
    return "\n".join(parts)


def _attach_image(msg: EmailMessage, path: Path, max_side: int = 1400) -> None:
    if not path or not Path(path).exists():
        return
    img = Image.open(path).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    msg.add_attachment(buf.getvalue(), maintype="image", subtype="jpeg", filename=Path(path).stem + ".jpg")


def send_report(concept: dict, result: dict, out_dir: Path, estimate_usd: float | None = None) -> dict:
    text = build_report(concept, result, estimate_usd)
    report_path = Path(out_dir) / "report.md"
    report_path.write_text(text, encoding="utf-8")
    if not config.GMAIL_REFRESH_TOKEN:
        return {"sent": False, "reason": "GMAIL_REFRESH_TOKEN fehlt (python auth_youtube.py url gmail)", "file": str(report_path)}
    svc = _service()
    to = config.REPORT_EMAIL
    if not to:
        try:   # gmail.send allein erlaubt getProfile nicht – dann muss REPORT_EMAIL gesetzt sein
            to = svc.users().getProfile(userId="me").execute()["emailAddress"]
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"REPORT_EMAIL fehlt und Gmail-Profil nicht lesbar ({str(e)[:80]})") from e
    msg = EmailMessage()
    msg["To"] = to
    msg["From"] = "me"
    msg["Subject"] = f"AIX WALKER neu online: {concept['album']} ({concept['genre']}, {result.get('duration_min')} Min)"
    msg.set_content(text)
    html = "<pre style='font-family:Manrope,Segoe UI,sans-serif;font-size:14px;white-space:pre-wrap'>" + \
           text.replace("&", "&amp;").replace("<", "&lt;") + "</pre>"
    for url in [result.get("video_url"), *[s.get("url") for s in result.get("shorts") or []],
                (result.get("drive") or {}).get("_folder")]:
        if url:
            html = html.replace(url, f"<a href='{url}'>{url}</a>")
    msg.add_alternative(html, subtype="html")
    thumbs = result.get("thumbnails") or []
    _attach_image(msg, Path(thumbs[0]) if thumbs else None)
    _attach_image(msg, Path(out_dir) / "covers" / "album_3000.png")
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    r = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"sent": True, "to": to, "id": r.get("id"), "file": str(report_path)}


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1])
    concept = json.loads((config.ROOT / "concepts" / f"{out.name}.json").read_text(encoding="utf-8"))
    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    print(send_report(concept, result, out))
