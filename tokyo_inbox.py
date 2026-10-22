"""Tokyo-Mix mit Rolfs eigenem Hauptbild (Rolf 22.10.2026).

Phase A (`run_tokyo.py --prompt-only ...`): Claude baut das komplette Bildprompt, legt Plan + Prompt in Drive ab und mailt Rolf den Prompt samt Anleitung.
Phase B (`run_tokyo.py --from-inbox ...`): holt Plan und Rolfs fertiges Bild aus dem Drive-Ordner „Tokyo Hauptbild“ und baut den Mix (keine Bild-Erzeugung).
Signal „Bild ist fertig“ = Rolf legt das Bild in den Ordner (stündliche Prüfung ab 9:30) oder schreibt Claude im Chat „Tokyo Bild fertig“.
"""
import base64
import json
from datetime import datetime, timezone
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from pipeline import config, drive, mailer

FOLDER = "Tokyo Hauptbild"
IMG_MIMES = ("image/png", "image/jpeg", "image/webp")
EARLIEST = "9:30"


def today() -> str:
    return datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d")


def inbox(svc) -> str:
    return drive.ensure_folder(svc, FOLDER, drive.ensure_folder(svc, drive.ROOT_FOLDER))


def folder_url(fid: str) -> str:
    return f"https://drive.google.com/drive/folders/{fid}"


def gemini_text(plan: dict) -> str:
    return ("Create ONE photorealistic, cinematic widescreen image in 16:9 landscape format, as large as possible (4K if available). Do not add any text or letters to the image.\n\n"
            + plan["prompt"] + plan["style"])


def save_plan(svc, plan: dict) -> str:
    fid = inbox(svc)
    d = plan["date"]
    drive.write_text(svc, f"plan_{d}.json", json.dumps(plan, indent=2, ensure_ascii=False), fid)
    drive.write_text(svc, f"bildprompt_{d}.txt", gemini_text(plan), fid, "text/plain")
    return fid


def load_plan(svc, date: str | None = None) -> tuple[dict | None, str, str | None]:
    """(Plan, Ordner-ID, Datei-ID des Plans) für das Datum (Standard: heute, Berlin)."""
    fid = inbox(svc)
    pid = drive.find_file(svc, f"plan_{date or today()}.json", fid)
    return (json.loads(drive.read_text(svc, pid)) if pid else None), fid, pid


def mark(svc, plan: dict, fid: str, **kw) -> None:
    plan.update(kw)
    drive.write_text(svc, f"plan_{plan['date']}.json", json.dumps(plan, indent=2, ensure_ascii=False), fid)


def newest_image(svc, fid: str, after_iso: str) -> dict | None:
    """Neueste Bilddatei im Ordner, die NACH dem Plan hochgeladen wurde."""
    pics = [c for c in drive.list_children(svc, fid, folders=False) if c.get("mimeType") in IMG_MIMES and c.get("createdTime", "") > after_iso]
    pics.sort(key=lambda c: c.get("createdTime", ""), reverse=True)
    return pics[0] if pics else None


def send_prompt_mail(plan: dict, fid: str) -> str:
    url = folder_url(fid)
    lines = [
        "Hallo Rolf,", "",
        f"das Bildprompt für den Tokyo-Mix von heute ({plan['date']}) ist fertig. Der Mix selbst startet erst, wenn dein Bild da ist – frühestens um {EARLIEST} Uhr.", "",
        f"RAUM: {plan['room']} (Tokyo) · Schreibtisch {plan['side']} · Person: {plan['person']} · {plan.get('place_text', '')}",
        f"SPRUCH IM VIDEO: {plan['quote'].replace('|', ' / ')}", "",
        "SO GEHT ES (nur 3 Schritte):", "",
        "1. BILD ERZEUGEN: Öffne Gemini (dein Gemini-Pro-Konto), wähle die Bild-Erzeugung (Nano Banana Pro) und füge den Text aus dem Kasten unten komplett ein. "
        "Das Format muss 16:9 (Querformat) sein. Du darfst so oft neu erzeugen, wie du willst. Nimm das schönste Bild und lade es in der GRÖSSTEN Größe herunter (am besten PNG).", "",
        f"2. BILD HOCHLADEN: Öffne diesen Drive-Ordner: {url}",
        "   Klicke links oben auf „Neu“ → „Datei-Upload“ und wähle dein Bild. Der Dateiname ist egal. Lege nur EIN fertiges Bild für heute dort ab. (Das Bildprompt und der Plan liegen schon in diesem Ordner, bitte nichts löschen.)", "",
        f"3. FERTIG MELDEN – du musst nichts weiter tun: Ich schaue ab {EARLIEST} Uhr jede volle halbe Stunde (9:30, 10:30, 11:30, 12:30, 13:30) in den Ordner. Sobald dein Bild dort liegt, "
        "starte ich den Mix automatisch. Willst du, dass es SOFORT losgeht (ab 9:30 Uhr), schreibe mir im Chat genau: Tokyo Bild fertig", "",
        "Danach läuft alles wie immer: Musik, Video, Short, Beschreibung mit den Amazon-Links; der Mix wird direkt nach Fertigstellung öffentlich geschaltet und du bekommst die Mail mit Pin-Kommentar und Community-Post.", "",
        "KOSTEN HEUTE: nur die Musik (22 Tracks ≈ 1,76 $ ≈ 1,62 €), keine Bild-Erzeugung auf meiner Seite.", "",
        "=========== BILDPROMPT (alles zwischen den Linien in Gemini einfügen) ===========", "",
        gemini_text(plan), "",
        "=================================================================================", "",
        "Das gleiche Prompt hängt als Textdatei an. Viele Grüße", "Claude",
    ]
    msg = EmailMessage()
    msg["To"] = config.REPORT_EMAIL or "rolf.korr@gmail.com"
    msg["From"] = "me"
    msg["Subject"] = f"Tokyo Work Lounge {plan['date']}: Bildprompt für Gemini – bitte Bild in Drive ablegen"
    msg.set_content("\n".join(lines))
    msg.add_attachment(gemini_text(plan).encode("utf-8"), maintype="text", subtype="plain", filename=f"tokyo_bildprompt_{plan['date']}.txt")
    r = mailer._service().users().messages().send(userId="me", body={"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}).execute()
    return r.get("id", "")
