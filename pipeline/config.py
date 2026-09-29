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

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
LYRIA_MODEL = os.environ.get("LYRIA_MODEL", "lyria-3.5")
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "gemini-2.5-flash-image")
IMAGE_MODEL_PRO = os.environ.get("IMAGE_MODEL_PRO", "gemini-3-pro-image-preview")

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
MP3_BITRATE = "192k"


def require(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        raise RuntimeError(f"Umgebungsvariable {name} fehlt")
    return val
