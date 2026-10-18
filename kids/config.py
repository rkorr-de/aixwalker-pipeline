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
# Kling-Ton AN (Rolf 18.10.2026): Kling erzeugt die Geräusche synchron mit dem Video, unsere Musik liegt leise darunter.
# (15.–17.10. war der Ton aus und kam aus der eigenen Bibliothek assets/kids_sfx – laut Rolf „katastrophal“.)
# Gesprochene Wörter verhindert der Kling-Prompt + Negativ-Prompt; die Videoprüfung wertet echte Wörter als schweren
# Fehler. Nur zum Testen abschaltbar mit KIDS_KLING_AUDIO=0.
KLING_AUDIO = os.environ.get("KIDS_KLING_AUDIO", "1") == "1"
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
# Startbild fürs Video (Keyframe): gleicher Look, aber OHNE fliegende Tiere und Spielzeug-Hintergrund – alles, was
# im Startbild steht, muss Kling 15 s lang stabil halten; zusätzliche Kleinteile tauchten auf/verschwanden/verdoppelten
# sich (Videoprüfung 09.–13.10.2026). STYLE_BIBLE bleibt fürs Thumbnail (Standbild) unverändert.
KEYFRAME_STYLE = (
    "Pixar-style 3D animated render, adorable chibi proportions with a big round head, oversized sparkling glossy "
    "eyes, tiny button nose, rosy cheeks, soft subsurface-scattering skin and fluffy fur, warm golden backlight, "
    "vivid rich candy colors (bright sky blue, sunny yellow, bubblegum pink, lilac, lime green, tangerine), "
    "colorful but calm background with soft out-of-focus flowers – no other animals, no extra toys or objects "
    "besides the ones named, never a plain beige, cream or grey background, shallow depth of field, whole "
    "character visible with space around it, vertical 9:16 composition, high quality, no text, no letters, no "
    "watermark, no logo"
)
NEGATIVE_PROMPT = (
    "text, letters, captions, watermark, logo, speech, talking, words, lip sync, scary, horror, realistic human, "
    "human hands, fingers, extra limbs, extra legs, extra arms, extra head, morphing, melting, merging bodies, "
    "character changes appearance, duplicate objects, objects appearing or disappearing, teleporting objects, "
    "scene cut, jump cut, camera cut, zoom, camera pan, blurry, glitch, flicker"
)
# Figuren sind immer Eigenkreationen – keine Namen oder Designs bekannter Marken.
FORBIDDEN_WORDS = ["disney", "pixar character", "mickey", "minnie", "donald duck", "elsa", "bluey", "peppa",
                   "paw patrol", "cocomelon", "baby shark", "pikachu", "pokemon", "sonic", "mario", "minion",
                   "bibi blocksberg", "bibi und tina", "bibi & tina"]

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

# Wiederkehrende „Flaggschiff“-Figur(en) – für Wiedererkennung (Merch/Lizenz-Chancen), zusätzlich zu den täglich
# neuen Tieren. Erscheint alle KIDS_FLAGSHIP_EVERY_N_DAYS Tage mit neuer Geschichte/Lektion, aber gleichem Namen,
# Tier und Aussehen (für visuelle Konsistenz). Leere Liste = Funktion aus.
FLAGSHIP_CHARACTERS = [
    {"name": "Snow", "species": "baby bunny",
     "look": "a small snow-white bunny with pale pink inner ears, round sparkling dark-brown eyes, a fluffy cotton "
             "tail, and one tiny daisy-flower clip behind her left ear"},
]
FLAGSHIP_EVERY_N_DAYS = int(os.environ.get("KIDS_FLAGSHIP_EVERY_N_DAYS", "4"))
STORY_MIN_SCORE = int(os.environ.get("KIDS_STORY_MIN_SCORE", "7"))      # Mindestnote (1–10) je Prüfkriterium
# (07.10.2026 von 8 auf 7 gesenkt, auf Rolfs Wunsch: höhere Wahrscheinlichkeit, dass täglich ein Video entsteht;
# siehe auch den Prompt-Text in kids/story.py, der diesen Wert jetzt direkt übernimmt statt ihn fest zu nennen.)
# Videoprüfung (kids/review.py) – kalibriert am 03.10.2026: Goldfisch-Video 7 schwere Fehler → abgelehnt,
# Kling-Video, das Rolf „sehr gut“ fand: 1 schwerer + 3 deutliche → bestanden
VIDEO_MIN_SCORE = int(os.environ.get("KIDS_VIDEO_MIN_SCORE", "4"))         # Gesamtnote (1–10)
VIDEO_MAX_CRITICAL = int(os.environ.get("KIDS_VIDEO_MAX_CRITICAL", "1"))   # schwere Fehler
VIDEO_MAX_ERRORS = int(os.environ.get("KIDS_VIDEO_MAX_ERRORS", "4"))       # schwere + deutliche Fehler zusammen
# Video-Versuche je Lauf (gleiche Story). Besteht keiner die Videoprüfung, wird das beste trotzdem veröffentlicht
# (Rolf, 07.10.2026: täglich ein Short hat Vorrang). Weitere Versuche nur, solange das Budget reicht.
VIDEO_ATTEMPTS = int(os.environ.get("KIDS_VIDEO_ATTEMPTS", "2"))
# Kosten (Rolf, 13.10.2026): Ein zweites Video (2,52 $) nur, wenn das erste eindeutig kaputt ist. Auswertung 09.–13.10.:
# Neuversuch bei 1–2 schweren Fehlern brachte 3 von 3 Malen kein besseres Video; bei 3 schweren Fehlern (09.10.) schon.
VIDEO_RETRY_MIN_CRITICAL = int(os.environ.get("KIDS_VIDEO_RETRY_MIN_CRITICAL", "3"))

# Suchbegriffe, nach denen Eltern suchen – fließen in Beschreibung und Tags ein (Englisch).
PARENT_KEYWORDS = [
    "cute cartoon for toddlers", "funny baby animals cartoon", "kids shorts", "toddler video no talking",
    "calm video for kids", "cute animation for babies", "bedtime cartoon", "preschool cartoon", "cute animals for kids",
    "3d animation kids", "short cartoon for children", "baby sensory video", "silly animal cartoon", "wholesome kids video",
]
# Affiliate-Links (Amazon-Partnerprogramm): Kuscheltier-Liste und Text in kids/affiliate.py (Stand 14.10.2026).
# `KIDS_AFFILIATE_LINE` leer gesetzt = keine Links; jeder andere Wert wird ignoriert (früherer Einzel-Link).

PLAYLIST_TITLE = '🧸 Cute Baby Animal Cartoons for Toddlers – Giggle Meadow 🌼'
PLAYLIST_DESCRIPTION = (
    '🌼 Cute baby animal cartoons for toddlers – with a little lesson in every story! 🐣 Each 15-second Giggle Meadow short shows a super cute baby animal facing a small everyday problem, like sharing a toy, waiting for a turn, trying again or helping a friend, and solving it in a kind way that little ones can copy. 🐾'
    '\n\n'
    '🧠 Inspired by social-emotional learning: children learn best by watching, so every story shows feelings, cause and effect and friendly behavior in a clear, simple way, without words. Watching together and talking about it afterwards ("How did the bunny feel? What did the puppy do?") makes it even better. 💛'
    '\n\n'
    '🧸 Gentle sounds, bright colors, no talking, nothing scary, always a happy ending. Made for toddlers and preschoolers (ages 1–5). 🌈')
HASHTAGS = ["#shorts", "#kids", "#toddlers", "#cutecartoon", "#babyanimals", "#kidsvideos", "#3danimation"]

# YouTube-Kategorie „Film & Animation“
CATEGORY_ID = "1"
DEFAULT_LANGUAGE = "en"


def require(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        raise RuntimeError(f"Umgebungsvariable {name} fehlt")
    return val
