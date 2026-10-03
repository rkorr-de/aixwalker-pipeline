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
# Strenger Prüfer für Story (vor dem Dreh) und fertiges Video (vor dem Upload) – stärkeres Modell als der Autor
CRITIC_MODEL = os.environ.get("KIDS_CRITIC_MODEL", "gemini-3.1-pro-preview")
IMAGE_MODEL = os.environ.get("KIDS_IMAGE_MODEL", "gemini-2.5-flash-image")          # Nano Banana
IMAGE_MODEL_PRO = os.environ.get("KIDS_IMAGE_MODEL_PRO", "gemini-3-pro-image-preview")  # Nano Banana Pro
# Veo: erster Eintrag wird benutzt, die weiteren sind Ausweichmodelle. Standard ist seit 03.10.2026 Veo 3.1 Fast
# (0,12 $/s statt 0,40 $/s – ca. 1,90 $ statt 6,40 $ je Short). Bessere Qualität: KIDS_VEO_MODELS=veo-3.1-generate-preview
VEO_MODELS = [m for m in os.environ.get(
    "KIDS_VEO_MODELS",
    "veo-3.1-fast-generate-preview,veo-3.1-lite-generate-preview"
).split(",") if m]
# Videoquelle: "kling" (fal.ai, Kling 3.0, 15 s am Stück) oder "veo" (Gemini API, 2 × 8 s)
VIDEO_PROVIDER = os.environ.get("KIDS_VIDEO_PROVIDER", "kling")
KLING_TIER = os.environ.get("KIDS_KLING_TIER", "pro")          # "pro" oder "standard"
VEO_CLIP_SEC = 8                 # Veo liefert 4/6/8 s; 2 × 8 s → 15 s nach Schnitt
VEO_RESOLUTION = os.environ.get("KIDS_VEO_RESOLUTION", "1080p")
LYRIA_MODEL = os.environ.get("LYRIA_MODEL", "lyria-3.5")

# ---- Video ------------------------------------------------------------------------------------------------------
SHORT_SEC = 15.0
WIDTH, HEIGHT, FPS = 1080, 1920, 30
CROSSFADE_SEC = 0.4
MUSIC_GAIN_DB = -16.0            # Musikbett unter den Veo-Tönen
MUSIC_BED_GAIN_DB = -12.0        # Kling: Musikbett (wird bei jedem Geräusch zusätzlich kurz abgesenkt)
SFX_GAIN_DB = 0.0                # Kling: Geräusche aus assets/kids_sfx (Spitze −1 dB, verdichtet) über der Musik
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
    "text_call_pro": 0.05,
    "kling_sec_pro": 0.112,      # fal.ai Kling 3.0 Pro, ohne Ton, je Sekunde
    "kling_sec_pro_audio": 0.168,
    "kling_sec_standard": 0.084,
    "kling_sec_standard_audio": 0.126,
    "sfx_sec": 0.002,            # fal.ai ElevenLabs Sound Effects V2, je Sekunde       # Pauschale je Prüf-Aufruf mit CRITIC_MODEL (Story-/Videoprüfung)
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
FORBIDDEN_WORDS = ["disney", "pixar character", "mickey", "minnie", "donald duck", "elsa", "bluey", "peppa",
                   "paw patrol", "cocomelon", "baby shark", "pikachu", "pokemon", "sonic", "mario", "minion"]

# ---- Abwechslung: Tiere × Lehrinhalte ------------------------------------------------------------------------
# Jeden Tag wird ein Tier gewählt, das in den letzten AVOID_SPECIES_DAYS Shorts nicht vorkam, und ein Lehrinhalt,
# der in den letzten AVOID_LESSON_DAYS nicht dran war. Gemini schreibt daraus jedes Mal eine komplett neue Story.
# Nur Tiere mit klar erkennbaren Beinen/Pfoten auf festem Boden – damit kommen Videomodelle zuverlässig zurecht
# (keine Fische, Schlangen, Schnecken, Quallen; keine Flugszenen).
SPECIES_POOL = [
    "baby bunny", "fox cub", "bear cub", "piglet", "duckling", "penguin chick", "kitten", "puppy", "hedgehog",
    "raccoon kit", "lamb", "baby goat", "calf", "pony foal", "baby elephant", "koala joey", "panda cub", "sloth baby",
    "squirrel", "chipmunk", "field mouse", "hamster", "owl chick", "baby hippo", "baby giraffe", "zebra foal",
    "red panda cub", "beaver kit", "mole", "badger cub", "capybara pup", "baby llama", "fluffy yellow chick",
    "frog (sitting on the ground)", "baby turtle (on land)", "otter pup (on a riverbank)", "lion cub", "tiger cub",
    "baby monkey", "baby gorilla", "kangaroo joey", "baby rhino", "wombat", "meerkat pup", "baby deer (fawn)",
    "polar bear cub", "seal pup (on the beach)", "baby walrus (on the ice)", "dinosaur hatchling (cute, round)",
    "baby dragon (tiny, friendly, wingless walker)", "baby alpaca", "guinea pig", "ferret kit", "baby armadillo",
    "baby porcupine", "baby camel", "baby flamingo (standing)", "baby ostrich chick", "puffin chick", "little bulldog puppy",
]
LESSON_POOL = [   # nur Lektionen, die man mit großen, langsamen Bewegungen zeigen kann (keine Fingerarbeit)
    "sharing a toy with a friend", "waiting for your turn", "trying again after a mistake", "asking for help",
    "helping a smaller friend", "tidying up toys after playing", "being gentle with a flower", "saying sorry and hugging",
    "eating a vegetable and liking it", "learning colors: red, yellow, blue", "big and small", "up and down",
    "being brave in the dark with a night light", "saying thank you with a hug", "sharing food with a friend",
    "teamwork: two friends push something heavy together", "being patient while waiting", "comforting a sad friend",
    "making a new friend", "building a block tower together", "taking only one cookie", "giving a present to a friend",
    "letting a friend go first", "inviting someone who is alone to play", "being careful near a sleeping baby animal",
    "sharing an umbrella-sized leaf in the rain", "cheering for a friend", "taking a rest when tired",
    "fast and slow", "near and far", "heavy and light", "happy and sad feelings", "being kind to a tiny bug",
]
AVOID_SPECIES_DAYS = int(os.environ.get("KIDS_AVOID_SPECIES_DAYS", "45"))
AVOID_LESSON_DAYS = int(os.environ.get("KIDS_AVOID_LESSON_DAYS", "25"))
STORY_MIN_SCORE = int(os.environ.get("KIDS_STORY_MIN_SCORE", "8"))      # Mindestnote (1–10) je Prüfkriterium
VIDEO_MIN_SCORE = int(os.environ.get("KIDS_VIDEO_MIN_SCORE", "7"))

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
