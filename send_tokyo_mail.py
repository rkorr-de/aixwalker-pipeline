"""Tokyo-Work-Lounge-Mail an Rolf: Links, Thumbnail als Anhang, angepinnter Kommentar, Community-Post.

Aufruf:  python send_tokyo_mail.py <ergebnis-ordner> --pin "<Text>" --community "<Text>" [--befehl] [--nachtrag]
  <ergebnis-ordner>  z. B. concepts/tokyo-mix-1/v2 (enthält result.json, thumb.jpg)
  --pin / --community  neu geschriebene Texte (Pflicht, Claude schreibt sie pro Mix neu; Community darf {url} enthalten)
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

def community_text(text: str, url: str) -> str:
    """Community-Text, den Claude pro Mix neu schreibt; {url} wird durch den Mix-Link ersetzt (fehlt er, wird er angehängt)."""
    return text.replace("{url}", url) if "{url}" in text else f"{text}\n\n{url}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--pin", required=True)
    ap.add_argument("--community", required=True)
    ap.add_argument("--quote", default="", help="Spruch des Mixes (Zeilen mit | oder Leerzeichen), erscheint in der Mail")
    ap.add_argument("--befehl", action="store_true")
    ap.add_argument("--nachtrag", action="store_true")
    a = ap.parse_args()
    d = Path(a.folder)
    res = json.loads((d / "result.json").read_text(encoding="utf-8"))
    sys.path.insert(0, str(Path(__file__).parent))
    url = res["video_url"]
    short = f"https://youtube.com/shorts/{res['short_id']}"
    lines = [
        "Hallo Rolf,", "",
        ("hier der Nachtrag zum Tokyo-Mix: Thumbnail, angepinnter Kommentar und Community-Post."
         if a.nachtrag else "der Tokyo-Mix und der Short sind fertig."), "",
        f"Mix: {url}", f"Short: {short}", f"Drive-Ordner: {(res.get('drive') or {}).get('_folder', '-')}", "",
        "NEUER SPRUCH IM VIDEO UND IM SHORT:",
        a.quote or "(siehe result.json)", "",
        "PIN-KOMMENTAR (neu für diesen Mix – schreibe ihn unter den Mix und pinne ihn danach selbst fest):",
        a.pin, "",
        "COMMUNITY-POST (neu für diesen Mix – Text kopieren und selbst posten):",
        community_text(a.community, url), "",
        "DEINE HANDGRIFFE (alles in dieser einen Mail, in der Cloud gibt es keinen Browser):",
        "1. Pin-Kommentar: Mix-Link öffnen, ins Feld „Kommentar hinzufügen“ klicken, Text einfügen, „Kommentieren“, "
        "dann bei deinem Kommentar auf die drei Punkte und „Anpinnen“.",
        "2. Community-Post: YouTube Studio → Inhalte → Community → Beitrag erstellen, Text einfügen, Posten.",
        "3. Abspann ohne Infokarten: im Studio beim Video „Details“ öffnen und den Abspann selbst setzen.", "",
        "Thumbnail und Album-Cover hängen als Bilder an dieser Mail.", "",
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
    if not thumb.exists():
        thumb = d / "thumb" / "thumb.jpg"   # run_tokyo.py legt das Thumbnail im Unterordner thumb/ ab
    msg.add_attachment(thumb.read_bytes(), maintype="image", subtype="jpeg", filename="tokyo_thumbnail.jpg")
    album = d / "img" / "album_3000.png"
    if album.exists():                     # Rolf 19.10.2026: Album-Cover immer mit in die Mail (als JPEG, sonst zu groß)
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.open(album).convert("RGB").save(buf, "JPEG", quality=90)
        msg.add_attachment(buf.getvalue(), maintype="image", subtype="jpeg", filename="tokyo_album_cover.jpg")
    svc = mailer._service()
    r = svc.users().messages().send(userId="me", body={"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}).execute()
    print("gesendet:", r.get("id"))


if __name__ == "__main__":
    main()
