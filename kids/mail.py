"""Report-Mail über die Gmail-API (eigener Refresh-Token GMAIL_REFRESH_TOKEN mit Scope gmail.send).

Die geplante Aufgabe nutzt bevorzugt den Gmail-Connector (mcp__Gmail__send_message). Dieses Modul ist der
Fallback, damit die Mail auch dann sicher ankommt, wenn der Connector in der Sitzung fehlt.
Token einmalig erzeugen: `python auth_youtube.py url gmail` → `python auth_youtube.py token gmail "<URL>"`.
"""
import base64
from email.message import EmailMessage

from googleapiclient.discovery import build

from pipeline.youtube import credentials

from . import config

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def available() -> bool:
    import os
    return bool(os.environ.get("GMAIL_REFRESH_TOKEN"))


def send(subject: str, body: str, to: str | None = None) -> str:
    to = to or config.REPORT_EMAIL
    msg = EmailMessage()
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    svc = build("gmail", "v1", credentials=credentials("GMAIL_REFRESH_TOKEN"), cache_discovery=False)
    r = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    return r.get("id", "")


def report_text(result: dict) -> str:
    """Klartext-Report für Rolf (deutsch)."""
    s = result.get("story", {})
    lines = [
        f"Neuer Kids-Short ist online: {result.get('url', '(kein Link)')}",
        "",
        f"Titel: {s.get('title', '')}",
        f"Figur: {s.get('character', {}).get('name', '')} ({s.get('character', {}).get('species', '')})",
        f"Story: {s.get('theme', '')}",
        f"Veröffentlicht: {result.get('published_at_local', '')}",
        f"Status laut YouTube: {result.get('privacy', '')}",
        f"Google Drive: {result.get('drive', {}).get('_folder', '(nicht abgelegt)')}",
        "",
        f"Beschreibung:\n{s.get('description', '')}",
        "",
        f"Tags: {', '.join(s.get('tags', [])[:15])}",
        "",
        f"Kosten: {result.get('cost_usd', 0):.2f} $ ≈ {result.get('cost_eur', 0):.2f} € (Budget {config.BUDGET_USD:.0f} $) – Videomodell: {result.get('veo_model', '')}",
        f"Laufzeit: {result.get('elapsed_min', 0):.1f} min",
    ]
    c = result.get("compilation")
    if c:
        lines += ["", "— Zusammenschnitt (16:9) —"]
        if c.get("status") == "ok" and c.get("url"):
            mins = round((c.get("duration_sec") or 0) / 60, 1)
            lines += [f"Online: {c['url']} ({c.get('privacy', '')})",
                      f"Titel: {c.get('title', '')}",
                      f"Modus: {c.get('mode', '')} · {c.get('count', '?')} Stories · {mins} min",
                      f"Google Drive: {c.get('drive') or '(nicht abgelegt)'}"]
        else:
            lines += [f"FEHLER: {c.get('error', 'unbekannt')}"]
        for w in c.get("warnings", []):
            lines.append(f"- {w}")
    so = result.get("social")
    if so:
        lines += ["", "— Instagram / TikTok (Metricool) —"]
        for net in ("instagram", "tiktok", "facebook"):
            v = so.get(net)
            if not v:
                continue
            if "error" in v:
                lines.append(f"{net}: FEHLER – {v['error']}")
            else:
                url = (v.get("result") or {}).get("plannerUrl") or ""
                lines.append(f"{net}: geplant {v.get('when')}{' (Entwurf)' if so.get('draft') else ''} {url}".rstrip())
    ls = result.get("longshort")
    if ls and ls.get("status") != "skipped":
        lines += ["", "— Langer Short (9:16) —"]
        if ls.get("status") == "ok" and ls.get("url"):
            lines += [f"Geplant: {ls['url']} – online {ls.get('published_at_local', '')}",
                      f"Titel: {ls.get('title', '')}",
                      f"{ls.get('count', '?')} Stories · {round((ls.get('duration_sec') or 0))} s",
                      f"Google Drive: {ls.get('drive') or '(nicht abgelegt)'}"]
        else:
            lines += [f"FEHLER: {ls.get('error', 'unbekannt')}"]
        for w in ls.get("warnings", []):
            lines.append(f"- {w}")
    if result.get("warnings"):
        lines += ["", "Hinweise:"] + [f"- {w}" for w in result["warnings"]]
    return "\n".join(lines)
