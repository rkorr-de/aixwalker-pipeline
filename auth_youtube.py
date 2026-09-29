#!/usr/bin/env python3
"""Einmalige YouTube-Freigabe: erzeugt die Zustimmungs-URL und tauscht den Code gegen ein Refresh-Token.

Aufruf 1:  python auth_youtube.py url            → URL öffnen, Kanal AIX WALKER wählen, Warnung bestätigen
Aufruf 2:  python auth_youtube.py token "<komplette localhost-Adresse aus der Adressleiste>"
Ausgabe:   eine Zeile YT_REFRESH_TOKEN=…  (in die Umgebungsvariablen eintragen)
"""
import sys
import urllib.parse

import requests

from pipeline import config
from pipeline.youtube import SCOPES

REDIRECT = "http://localhost:1"


def auth_url() -> str:
    q = {"client_id": config.require("YT_CLIENT_ID"), "redirect_uri": REDIRECT, "response_type": "code",
         "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent", "include_granted_scopes": "true"}
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
    if len(sys.argv) >= 2 and sys.argv[1] == "url":
        print(auth_url())
    elif len(sys.argv) >= 3 and sys.argv[1] == "token":
        print(f"YT_REFRESH_TOKEN={exchange(sys.argv[2])}")
    else:
        print(__doc__)
