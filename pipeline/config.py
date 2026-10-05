"""Zentrale Konfiguration: Umgebungsvariablen, Pfade, Kanal-Konstanten."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONT_DISPLAY = ASSETS / "fonts" / "BebasNeue-Regular.ttf"
FONT_BODY = ASSETS / "fonts" / "Manrope.ttf"

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
YT_CLIENT_ID = os.environ.get("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN", "")
DRIVE_REFRESH_TOKEN = os.environ.get("DRIVE_REFRESH_TOKEN", "")
GMAIL_REFRESH_TOKEN = os.environ.get("GMAIL_REFRESH_TOKEN", "")   # Bericht per E-Mail (auth_youtube.py url gmail)
REPORT_EMAIL = os.environ.get("REPORT_EMAIL", "")                 # leer = Adresse des Gmail-Kontos der Freigabe
DISTROKID_SONGWRITER = os.environ.get("DISTROKID_SONGWRITER", "")  # Klarname für die DistroKid-Angaben im Bericht

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
LYRIA_MODEL = os.environ.get("LYRIA_MODEL", "lyria-3.5")
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "gemini-2.5-flash-image")
IMAGE_MODEL_PRO = os.environ.get("IMAGE_MODEL_PRO", "gemini-3-pro-image-preview")
TEXT_MODEL = os.environ.get("TEXT_MODEL", "gemini-3.1-pro-preview")            # Konzept-/Titelgenerierung (Planer)
TEXT_MODEL_FALLBACK = os.environ.get("TEXT_MODEL_FALLBACK", "gemini-3.8-flash")

ARTIST = "Aix Walker"
CHANNEL_HANDLE = "@AIXWALKER"
CHANNEL_URL = "https://www.youtube.com/@AIXWALKER"

PLAYLISTS = {
    "gym": "PLVJixyQyNYDc",
    "chillout": "PLQyvcKUee6e8",
    "songs": "PLZUHXQMXYvmo",
    "aachen": "PLAPYXyJDsfd4",
    "mallorca": "PLCl2AgQDWKzk",
}

# Kanalfarben
BG = (11, 20, 22)
BG2 = (15, 34, 38)
TEAL = (95, 201, 187)
TEAL_DIM = (77, 122, 128)
WHITE = (242, 247, 246)
GREY = (185, 207, 208)

TARGET_LUFS = -14.0
MIN_MIX_MINUTES = 60      # jeder Mix mindestens so lang
DEFAULT_MINUTES_PER_TRACK = 5
SHORTS_COUNT = 2
SHORT_CLIP_SEC = 45

# Preise (USD) laut Google-Preisliste – bei Änderung hier pflegen (ai.google.dev/pricing)
PRICES_USD = {
    "lyria_track": 0.08,     # Lyria 3.5, ein Track (ca. 3–6 Min)
    "image_flash": 0.039,    # Nano Banana (gemini-2.5-flash-image), ein Bild
    "image_pro": 0.134,      # Nano Banana Pro (gemini-3-pro-image-preview), ein Bild bis 2K
}
USD_EUR_RATE = 0.92
BUDGET_WARN_USD = 5.0        # Warnschwelle je Lauf (Umgebungsvariable BUDGET_WARN_USD überschreibt)
BUDGET_MAX_USD = 9.0         # harte Obergrenze je automatischem Lauf: darüber bricht run_auto.py ab (BUDGET_MAX_USD)
MEMORY_FOLDER = "_memory"    # Unterordner in „AIX WALKER Mixe“ mit memory.json (Gedächtnis des Planers)
PLANNED_TRACKS = 20          # Lyria liefert ca. 3 Min je Track → 20 Tracks + Reserve für ≥ 60 Min ohne Wiederholung
EXTRA_TRACKS = 8
# Lang-Format (Sonntag, Sleep/Spa): Stufe 2 = 3 Stunden (seit 05.10.2026); Umgebungsvariable LONG_MIN_MINUTES überschreibt
LONG_MIN_MINUTES = int(os.environ.get("LONG_MIN_MINUTES", "180"))
LONG_PLANNED_TRACKS = 28
LONG_EXTRA_TRACKS = 40
LONG_MAX_TRACKS = 90
LONG_ART_GROUP = 4           # ein Cover-Bild je 4 Tracks (Kosten), Titel/Nummer wechseln trotzdem
BILLING_URL = "https://console.cloud.google.com/billing?project=bodydashboard-fde82"
MP3_BITRATE = "192k"


def require(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        raise RuntimeError(f"Umgebungsvariable {name} fehlt")
    return val
