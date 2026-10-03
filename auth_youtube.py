#!/usr/bin/env python3
"""Einmalige Freigaben: erzeugt die Zustimmungs-URL und tauscht den Code gegen ein Refresh-Token.

YouTube (Upload, Verwaltung, Analytics):
  python auth_youtube.py url            → URL öffnen, Kanal AIX WALKER wählen, Warnung bestätigen
  python auth_youtube.py token "<komplette localhost-Adresse aus der Adressleiste>"
  Ausgabe: YT_REFRESH_TOKEN=…

Google Drive (eigene Freigabe, weil Google YouTube- und Drive-Scopes nicht zusammen erlaubt):
  python auth_youtube.py url drive
  python auth_youtube.py token drive "<komplette localhost-Adresse>"
  Ausgabe: DRIVE_REFRESH_TOKEN=…

Gmail (Bericht nach jedem Mix per E-Mail, Scope gmail.send):
  python auth_youtube.py url gmail
  python auth_youtube.py token gmail "<komplette localhost-Adresse>"
  Ausgabe: GMAIL_REFRESH_TOKEN=…

Alle Zeilen in die Umgebungsvariablen (Umgebung AixWalker) eintragen.
"""
import sys
import urllib.parse

import requests

from pipeline import config
from pipeline.youtube import DRIVE_SCOPES, GMAIL_SCOPES, SCOPES

REDIRECT = "http://localhost:1"


def auth_url(scopes: list[str]) -> str:
    q = {"client_id": config.require("YT_CLIENT_ID"), "redirect_uri": REDIRECT, "response_type": "code",
         "scope": " ".join(scopes), "access_type": "offline", "prompt": "consent"}
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(q)


def exchange(redirected_url: str) -> str:
    code = urllib.parse.parse_qs(urllib.parse.urlparse(redirected_url).query)["code"][0]
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code, "client_id": config.require("YT_CLIENT_ID"), "client_secret": config.require("YT_CLIENT_SECRET"),
        "redirect_uri": REDIRECT, "grant_type": "authorization_code"}, timeout=30)
    r.raise_for_status()
    tok = r.json().get("refresh_token")
    if not tok:
        raise SystemExit(f"Kein refresh_token in Antwort: {r.text}")
    return tok


if __name__ == "__main__":
    args = sys.argv[1:]
    kind = "drive" if "drive" in args else "gmail" if "gmail" in args else "yt"
    args = [a for a in args if a not in ("drive", "gmail")]
    scopes = {"drive": DRIVE_SCOPES, "gmail": GMAIL_SCOPES, "yt": SCOPES}[kind]
    if args and args[0] == "url":
        print(auth_url(scopes))
    elif len(args) >= 2 and args[0] == "token":
        print(f"{kind.upper()}_REFRESH_TOKEN={exchange(args[1])}")
    else:
        print(__doc__)
