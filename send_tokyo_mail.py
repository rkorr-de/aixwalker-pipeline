"""Tokyo-Work-Lounge-Mail an Rolf: Links, Thumbnail als Anhang, angepinnter Kommentar, Community-Post.

Aufruf:  python send_tokyo_mail.py <ergebnis-ordner> [--befehl] [--nachtrag]
  <ergebnis-ordner>  z. B. concepts/tokyo-mix-1/v2 (enthält result.json, thumb.jpg)
  --befehl           Block „So geht es weiter: Tokyo freigeben“ anhängen (Mix noch privat)
  --nachtrag         Betreff „Nachtrag“ (Mix ist schon freigegeben)
Rolf-Regel 18.10.2026: Thumbnail immer als Anhang, Pin-Kommentar und Community-Post immer in der Mail.
"""
import argparse
import base64
import json
import sys
from email.message import EmailMessage
from pathlib import Path

from pipeline import config, mailer

COMMUNITY = ("The Tokyo Work Lounge is open 🌃\n"
             "Slow jazz for deep work and coding: breathy sax, soft piano and a warm, quiet groove. "
             "Close the door on the noise, pick one small task and begin.\n"
             "{url}")


def community_text(url: str) -> str:
    return COMMUNITY.format(url=url)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--befehl", action="store_true")
    ap.add_argument("--nachtrag", action="store_true")
    a = ap.parse_args()
    d = Path(a.folder)
    res = json.loads((d / "result.json").read_text(encoding="utf-8"))
    sys.path.insert(0, str(Path(__file__).parent))
    import run_tokyo
    url = res["video_url"]
    short = f"https://youtube.com/shorts/{res['short_id']}"
    lines = [
        "Hallo Rolf,", "",
        ("hier der Nachtrag zum Tokyo-Mix: Thumbnail, angepinnter Kommentar und Community-Post."
         if a.nachtrag else "der Tokyo-Mix und der Short sind fertig."), "",
        f"Mix: {url}", f"Short: {short}", f"Drive-Ordner: {(res.get('drive') or {}).get('_folder', '-')}", "",
        "ANGEPINNTER KOMMENTAR (Studio → Kommentare → unter dem Mix schreiben und anpinnen; die API kann nicht anpinnen):",
        run_tokyo.PINNED, "",
        "COMMUNITY-POST (Studio → Inhalte → Community → Beitrag erstellen, Text kopieren):",
        community_text(url), "",
        "Das Thumbnail hängt als Bild an dieser Mail.", "",
    ]
    if a.befehl:
        lines += ["So geht es weiter: Wenn alles passt, schreibe mir im Chat genau diesen Befehl:", "",
                  "Tokyo freigeben", "",
                  "Dafür muss dein PC an sein und die Claude-App offen (YouTube Studio läuft über den eingebauten Browser).", ""]
    lines += ["Viele Grüße", "Claude"]
    msg = EmailMessage()
    msg["To"] = config.REPORT_EMAIL or "rolf.korr@gmail.com"
    msg["From"] = "me"
    msg["Subject"] = ("Tokyo Work Lounge – Nachtrag: Thumbnail, Pin-Kommentar, Community-Post" if a.nachtrag
                      else "Tokyo Work Lounge: Mix und Short sind fertig" + (" – Befehl: Tokyo freigeben" if a.befehl else ""))
    msg.set_content("\n".join(lines))
    thumb = d / "thumb.jpg"
    msg.add_attachment(thumb.read_bytes(), maintype="image", subtype="jpeg", filename="tokyo_thumbnail.jpg")
    svc = mailer._service()
    r = svc.users().messages().send(userId="me", body={"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}).execute()
    print("gesendet:", r.get("id"))


if __name__ == "__main__":
    main()
