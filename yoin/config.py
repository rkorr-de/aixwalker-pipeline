"""Konfiguration für den Kanal YOIN Rooms (@yoinrooms): ruhiger Tokyo-Café-Jazz, eigener Kanal im selben Google-Konto."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build" / "yoin"

# ---- Kanal / Zugang ---------------------------------------------------------------------------------------------
# Refresh-Token mit `python auth_youtube.py url yoin` / `token yoin "<localhost-Adresse>"` (beim Google-Dialog den Kanal
# „YOIN Rooms“ wählen). Anders als beim Kids-Kanal gibt es KEINEN Ausweich-Token: fehlt die Variable, bricht alles ab,
# damit nie versehentlich auf AIX WALKER (YT_REFRESH_TOKEN) hochgeladen wird.
TOKEN_VAR = "YOIN_YT_REFRESH_TOKEN"
CHANNEL_NAME = "YOIN Rooms"
CHANNEL_ID = "UCjz1OHf67_NfXGA709EOQiw"      # bei der Token-Prüfung am 30.10.2026 bestätigt
CHANNEL_HANDLE = "@yoinrooms"
CHANNEL_URL = f"https://www.youtube.com/{CHANNEL_HANDLE}"

# ---- YouTube-Voreinstellungen -----------------------------------------------------------------------------------
CATEGORY_ID = "10"                            # Musik
DEFAULT_LANGUAGE = "en"                       # YouTube-Metadaten bleiben Englisch
