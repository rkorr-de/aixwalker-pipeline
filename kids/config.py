"""Konfiguration der täglichen Kids-Shorts (Disney-/Pixar-Look, 15 s, ohne Sprache).

Alle Werte sind per Umgebungsvariable überschreibbar. Preise laut ai.google.dev/pricing – bei Änderung hier pflegen.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build" / "kids"

# ---- Kanal / Zugang ---------------------------------------------------------------------------------------------
# Eigener Kids-Kanal im selben Google-Konto: Refresh-Token mit `python auth_youtube.py url` (Kanal „Kids“ wählen).
# Fehlt KIDS_YT_REFRESH_TOKEN, wird YT_REFRESH_TOKEN (Aix Walker) genutzt – nur für Tests gedacht.
KIDS_TOKEN_VAR = "KIDS_YT_REFRESH_TOKEN" if os.environ.get("KIDS_YT_REFRESH_TOKEN") else "YT_REFRESH_TOKEN"
CHANNEL_NAME = os.environ.get("KIDS_CHANNEL_NAME", "Giggle Meadow")      # Anzeigename, nur für Texte
REPORT_EMAIL = os.environ.get("KIDS_REPORT_EMAIL", "rolf.korr@gmail.com")

# ---- Modelle ----------------------------------------------------------------------------------------------------
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
TEXT_MODEL = os.environ.get("KIDS_TEXT_MODEL", "gemini-3.8-flash")
IMAGE_MODEL = os.environ.get("KIDS_IMAGE_MODEL", "gemini-2.5-flash-image")          # Nano Banana
IMAGE_MODEL_PRO = os.environ.get("KIDS_IMAGE_MODEL_PRO", "gemini-3-pro-image-preview")  # Nano Banana Pro
# Veo: erster Eintrag ist Standardqualität; die weiteren sind Ausweichmodelle, falls eines nicht freigeschaltet ist.
VEO_MODELS = [m for m in os.environ.get(
    "KIDS_VEO_MODELS",
    "veo-3.1-generate-preview,veo-3.1-fast-generate-preview,veo-3.1-lite-generate-preview"
).split(",") if m]
VEO_CLIP_SEC = 8                 # Veo liefert 4/6/8 s; 2 × 8 s → 15 s nach Schnitt
VEO_RESOLUTION = os.environ.get("KIDS_VEO_RESOLUTION", "1080p")
LYRIA_MODEL = os.environ.get("LYRIA_MODEL", "lyria-3.5")

# ---- Video ------------------------------------------------------------------------------------------------------
SHORT_SEC = 15.0
WIDTH, HEIGHT, FPS = 1080, 1920, 30
CROSSFADE_SEC = 0.4
MUSIC_GAIN_DB = -16.0            # Musikbett unter den Veo-Tönen
VEO_AUDIO_GAIN_DB = 0.0
TARGET_LUFS = -14.0

# ---- Kosten / Budget --------------------------------------------------------------------------------------------
PRICES_USD = {
    "veo_sec_standard": 0.40,    # Veo 3.1 Standard, je Sekunde Video (mit Ton)
    "veo_sec_fast": 0.12,        # Veo 3.1 Fast (1080p)
    "veo_sec_lite": 0.08,        # Veo 3.1 Lite (1080p)
    "image_flash": 0.039,
    "image_pro": 0.134,
    "lyria_track": 0.08,
    "text_call": 0.01,           # Pauschale je Gemini-Text-Aufruf (real meist < 0,005 $)
}
USD_EUR_RATE = float(os.environ.get("USD_EUR_RATE", "0.92"))
BUDGET_USD = float(os.environ.get("KIDS_BUDGET_USD", "10.0"))   # harte Obergrenze je Lauf (Abbruch statt Upload)
MAX_CLIP_RETRIES = int(os.environ.get("KIDS_MAX_CLIP_RETRIES", "1"))  # Neuversuche je Clip
BILLING_URL = "https://console.cloud.google.com/billing?project=bodydashboard-fde82"

# ---- Look (Style-Bible) ------------------------------------------------------------------------------------------
STYLE_BIBLE = (
    "Pixar-style 3D animated render, adorable chibi proportions with a big round head, oversized sparkling glossy "
    "eyes, tiny button nose, rosy cheeks, soft subsurface-scattering skin and fluffy fur, warm golden backlight, "
    "glowing bokeh light particles, floating butterflies and fireflies, vivid rich candy colors with rainbow "
    "accents (bright sky blue, sunny yellow, bubblegum pink, lilac, lime green, tangerine), colorful detailed "
    "background full of flowers and toys – never a plain beige, cream or grey background, shallow depth of field, dreamy whimsical storybook mood, flower meadow "
    "setting, vertical 9:16 composition, ultra detailed, high quality, no text, no letters, no watermark, no logo"
)
NEGATIVE_PROMPT = (
    "text, letters, captions, subtitles, watermark, logo, speech, talking, dialogue, lip sync, scary, dark, horror, "
    "blood, weapons, realistic human, deformed, extra limbs, blurry, low quality, glitch, flicker"
)
# Figuren sind immer Eigenkreationen – keine Namen oder Designs bekannter Marken.
FORBIDDEN_WORDS = ["disney", "pixar character", "mickey", "minnie", "donald", "elsa", "frozen", "bluey", "peppa",
                   "paw patrol", "cocomelon", "baby shark", "pikachu", "pokemon", "sonic", "mario", "minion"]

# ---- Themen-Pool (Inspiration für die Tageswahl; Gemini erfindet daraus täglich eine neue Mini-Story) -----------
THEME_POOL = [
    "baby hamster vs. a cupcake twice its size", "caterpillar learning to wave with too many legs",
    "a tiny fallen star that needs help jumping back into the sky", "penguin chick and a melting ice cream",
    "a shy red balloon and a curious puppy", "duckling trying to catch its own reflection in a puddle",
    "kitten discovering a dandelion that floats away", "baby elephant blowing its first soap bubble",
    "bunny who cannot stop sneezing from flower pollen", "owl chick trying to stay awake at sunset",
    "fox cub and a hiccuping frog", "lamb hopping over a tiny stream and landing in a flower",
    "squirrel building a nut tower that keeps toppling", "baby turtle racing a snail (both very slow)",
    "piglet splashing in a rainbow puddle", "chick trying to fly like a butterfly", "bear cub tasting honey for the first time",
    "mouse using a leaf as an umbrella in a sunny drizzle", "koala falling asleep mid-hug", "baby giraffe stuck on a swing",
    "hedgehog with a flower stuck on its spikes", "tiny dragon whose sneeze makes bubbles instead of fire",
    "puppy chasing its tail and getting dizzy", "kitten wearing a sock as a hat", "ducklings forming a conga line",
    "baby otter juggling a pebble", "bee carrying a flower petal as a parachute", "unicorn foal with a rainbow hiccup",
    "little cloud that rains confetti", "snail with a glowing shell at dusk", "baby panda rolling down a grassy hill",
    "robin chick learning to sing (only squeaks)", "goldfish jumping between two bowls", "seal pup clapping for itself",
    "tiny monkey swinging into a pile of leaves", "baby deer meeting a firefly", "kitten and a bouncing ball of yarn",
    "chipmunk with cheeks full of berries trying to whistle", "fluffy chick hiding in a teacup", "baby dolphin playing with a bubble ring",
]

# Suchbegriffe, nach denen Eltern suchen – fließen in Beschreibung und Tags ein (Englisch).
PARENT_KEYWORDS = [
    "cute cartoon for toddlers", "funny baby animals cartoon", "kids shorts", "toddler video no talking",
    "calm video for kids", "cute animation for babies", "bedtime cartoon", "preschool cartoon", "cute animals for kids",
    "3d animation kids", "short cartoon for children", "baby sensory video", "silly animal cartoon", "wholesome kids video",
]
HASHTAGS = ["#shorts", "#kids", "#toddlers", "#cutecartoon", "#babyanimals", "#kidsvideos", "#3danimation"]

# YouTube-Kategorie „Film & Animation“
CATEGORY_ID = "1"
DEFAULT_LANGUAGE = "en"


def require(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        raise RuntimeError(f"Umgebungsvariable {name} fehlt")
    return val
