"""Zentrale Konfiguration: Umgebungsvariablen, Pfade, Kanal-Konstanten."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONT_DISPLAY = ASSETS / "fonts" / "BebasNeue-Regular.ttf"
FONT_BODY = ASSETS / "fonts" / "Manrope.ttf"
# Neuer Look (Thumbnail-Analyse 08.10.2026): kräftige, breite Groteske für den Genre-Begriff + Schreibschrift für den Albumnamen
FONT_TITLE = ASSETS / "fonts" / "Montserrat.ttf"          # Variable Font, für kleine Beschriftungen (Dauer, AIX WALKER)
FONT_HEAD = ASSETS / "fonts" / "Cinzel.ttf"               # elegante Antiqua-Versalien für den Haupttitel (Rolf 08.10.)
FONT_SCRIPT = ASSETS / "fonts" / "GreatVibes-Regular.ttf"  # Schreibschrift (OFL)

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
LOGO_PNG = ASSETS / "brand" / "aixwalker_logo.png"   # rundes Kanal-Logo, unten links im Mix-Video (Rolf 08.10.2026)

PLAYLISTS = {
    "gym": "PLVJixyQyNYDc",       # nur noch für alte Videos – Gym-Mixe eingestellt (08.10.2026)
    "chillout": "PLQyvcKUee6e8",
    "songs": "PLZUHXQMXYvmo",
    "aachen": "PLAPYXyJDsfd4",
    "mallorca": "PLCl2AgQDWKzk",
    # Italien-Linie (Rolf, 08.10.2026): leer = Playlist wird beim ersten Upload über den Titel gesucht bzw. angelegt
    "italian": os.environ.get("YT_PLAYLIST_ITALIAN", ""),
    # Ibiza-Linie (Rolf, 09.10.2026): leer = Playlist wird beim ersten Upload über den Titel gesucht bzw. angelegt
    "ibiza": os.environ.get("YT_PLAYLIST_IBIZA", ""),
    # Winter-Cabin-Linie (Rolf, 09.10.2026): leer = Playlist wird beim ersten Upload über den Titel gesucht bzw. angelegt
    "cabin": os.environ.get("YT_PLAYLIST_CABIN", ""),
}
PLAYLIST_TITLES = {   # für Playlists, die die Pipeline selbst findet/anlegt (youtube.ensure_playlist)
    "italian": ("Italian Chillout Music",
                "Calm Italian chillout and lounge music for sunset dinners on the Amalfi Coast and Lake Como – "
                "Italian Amalfi Coast & Lake Como Ambience by Aix Walker. A new mix every few days."),
    "ibiza": ("Ibiza Sunset Lounge",
              "Ibiza Sunset Lounge – Balearic chillout mixes with dreamy, breathy vocal hums for golden-hour beach "
              "club vibes, relaxing summer evenings and sunset lounging. By Aix Walker."),
    "cabin": ("Cozy Winter Cabin · Relaxing Fireplace Chillout 4K",
              "Cozy winter cabin ambience in 4K: a crackling fireplace, candlelight and heavy snowfall outside the window, "
              "with warm lofi jazz and ambient chillout music by Aix Walker. Long fireplace films for relaxing, reading, "
              "studying and sleeping on cold winter nights."),
}

# Kanalfarben
BG = (11, 20, 22)
BG2 = (15, 34, 38)
TEAL = (95, 201, 187)
TEAL_DIM = (77, 122, 128)
WHITE = (242, 247, 246)
GREY = (185, 207, 208)
CREAM = (255, 238, 214)
GLOW = (255, 206, 140)    # atmendes Licht im Video: warmes Gold passend zum hellen Look   # Albumname in Schreibschrift (warm, auf hellen wie dunklen Motiven lesbar)

# Groß auf Thumbnail und Album-Cover: der Suchbegriff des Genres (76 % der erfolgreichen Nischen-Thumbnails zeigen so einen
# Begriff). Derselbe Begriff steht im YouTube-Titel direkt hinter dem Albumnamen → Video und Album sehen gleich aus.
THUMB_KEYWORD = {   # immer mit „Music", damit sofort klar ist: das ist Musik, kein Spa- oder Reisevideo (Rolf 08.10.)
    "Mediterranean Spa Lounge": "Chillout Lounge Music",
    "Dark Ambient Spa": "Luxury Spa Music",
    "Chillout Sleep": "Sleep Music",
    "Italian Chillout": "Italian Chillout Music",
    "Ibiza Sunset Lounge": "Ibiza Sunset Lounge",
    "Cozy Winter Cabin": "Cozy Winter Cabin",
}
# Unterzeile unter dem Genre-Begriff (gleiche Antiqua, kleiner) und Genres mit einzeiligem Genre-Begriff (Rolf 09.10.)
THUMB_SUBLINE = {"Ibiza Sunset Lounge": "Balearic Chillout"}   # Rolf 09.10.: passt zur langsameren Musik
THUMB_ONE_LINE = {"Ibiza Sunset Lounge"}
# Thumbnail-Anordnung „Titel oben im Himmel“ (Rolf 09.10.): Titelblock oben, Dauer unten rechts auf Höhe von AIX WALKER
THUMB_TITLE_TOP = {"Ibiza Sunset Lounge"}
# Kinematografischer Orange-&-Teal-Filter auf alle Bilder des Genres (Rolf 09.10.: warme Lichter/Sonne kräftig
# orange-gold, Himmel, Meer und Schatten in Türkis/Teal) – images.color_grade; Wert = Einstellungen für orange_teal().
# Italien (Rolf 09.10. abends: „auch in die Italian-Linie“): sanftere Variante, weil dort eine Frau groß im Bild ist –
# Hauttöne natürlich, kräftige Kleiderfarben bleiben warm, weiße Tischdecken kippen nicht ins Türkise.
COLOR_GRADE = {
    "Ibiza Sunset Lounge": {},
    "Italian Chillout": {"warm_lum": (0.03, 0.22), "teal_mix": 0.6, "bright_keep": 0.7, "skin": True, "strength": 0.9},
}
# Genres mit Stimme (alle anderen: instrumental, „no vocals“ in Texten). Ibiza (Rolf 09.10. nach 3 Testrunden): KEIN
# Liedtext, nur selten ein gehauchtes, wortloses Summen weit im Hintergrund – geht als `vocals` in jeden Lyria-Prompt
VOCAL_STYLE = {
    "Ibiza Sunset Lounge": ("almost none, the track is mostly instrumental. Only now and then a soft, breathy, wordless "
                            "female humming (gentle 'mmm' and airy 'ooh'), placed far in the background, very low in the "
                            "mix, drenched in reverb and delay like a distant whisper, never in the foreground and never "
                            "carrying the melody. No lyrics, no words, no singing of text, no vocal chops, no spoken words."),
}
VOCAL_GENRES = set(VOCAL_STYLE)
# Genre-Angabe am Anfang des Lyria-Prompts (Standard: der Genre-Name). Ibiza: so in Testrunde 3 freigegeben (Rolf 09.10.)
LYRIA_GENRE_TAGS = {"Ibiza Sunset Lounge": "Balearic Chillout, Ibiza Sunset Chillout, Downtempo Lounge",
                    "Cozy Winter Cabin": "Cozy Lofi Ambient, Smooth Jazz, Fireplace Ambience"}

# Linien mit eigenem Format (Rolf 09.10.2026, „Cozy Winter Cabin“): bewegter 4K-Kaminfilm aus Veo-Loops statt Standbild,
# keine Track-/Album-Cover, kein DistroKid, leiseres Mastering, eigene Kostengrenze. Produktion: run_cabin.py.
LINE_FORMAT = {
    "Cozy Winter Cabin": {"tracks": 42, "extra": 8, "min_minutes": 120, "lufs": -16.0, "budget_usd": 15.0,
                          "veo_clips": 3, "max_tracks": 52},
}


def vocal_note(genre: str | None) -> str:
    """Kurzangabe für Beschreibungen/Shorts: „no vocals“ bzw. bei wortlosem Summen „no lyrics“."""
    return "no lyrics" if genre in VOCAL_GENRES else "no vocals"
# Schriftgröße von Genre-Begriff und Albumname auf Thumbnail/Cover je Genre (1.0 = Standard). Italien: größer (Rolf 08.10.)
THUMB_TEXT_SCALE = {"Italian Chillout": 1.2, "Ibiza Sunset Lounge": 1.2}

# Bildstil je Genre (wird an jeden Bild-Prompt angehängt). Analyse 08.10.2026: erfolgreiche Thumbnails sind doppelt so hell
# und mehr als doppelt so farbig wie unsere alten dunkel-teal Bilder – daher hell, warm, farbig für Lounge/Spa/Sleep.
_NO_TEXT = " Photorealistic, high detail, no text, no letters, no watermark, no logos."
IMAGE_STYLE = {
    "Mediterranean Spa Lounge": (" Bright, warm, vivid luxury resort photography: golden-hour sunset or sunny Mediterranean "
                                 "daylight, rich saturated colors (turquoise water, white architecture, warm orange and pink "
                                 "sky), inviting and aspirational, clean high-end travel-magazine look, wide composition." + _NO_TEXT),
    "Dark Ambient Spa": (" Warm, inviting luxury spa photography: glowing candlelight and golden tones, rich warm colors with fresh "
                         "green leaves or blossom accents, soft steam, polished stone and wood, bright enough to read well on a "
                         "phone screen, high-end wellness-magazine look." + _NO_TEXT),
    "Chillout Sleep": (" Calm, dreamy evening photography: soft warm lights against a deep blue dusk sky, gentle but colorful, "
                       "cozy and safe, clear and not murky, high-end interior or nature photography." + _NO_TEXT),
    # Italien-Linie: super-realistisch wie ein echtes Magazin-Shooting, ausdrücklich nicht künstlich (Rolf 08.10.2026)
    "Italian Chillout": (" Professional editorial travel photograph, real photo taken on a full-frame camera (Canon EOS R5 or "
                         "Sony A7R V, 35–85 mm prime lens), not CGI, not a render, not an illustration, not airbrushed. "
                         "Natural golden-hour or sunset light mixed with warm candlelight, natural skin texture, real fabric "
                         "folds and sheen, subtle film grain, true-to-life colors, realistic shallow depth of field with natural "
                         "bokeh, classy luxury travel-magazine look (Condé Nast Traveller style), tasteful and "
                         "advertiser-friendly. Darker, warmer cinematic mood (Rolf 09.10.): a late, deep sunset with a "
                         "red-orange sky, the surroundings dimmer and moodier, lit by the afterglow and candlelight, her "
                         "face softly lit by warm candlelight; moody cinematic orange and teal colour grading – sunset glow, "
                         "candles and skin in warm orange and gold, sky, water and shadows in contrasting teal tones."
                         + _NO_TEXT),
    # Ibiza-Linie (Rolf 09.10.2026): Beach Club mit Gästen bei Sonnenuntergang, gleicher Foto-Realismus wie Italien.
    # Stimmung dunkler und wärmer (Rolf 09.10. abends): tieferer Sonnenuntergang, mehr Rot am Himmel, dunklere Umgebung
    "Ibiza Sunset Lounge": (" Professional editorial travel photograph, real photo taken on a full-frame camera (Sony "
                            "A7R V, 24–50 mm), not CGI, not a render, not an illustration. Late, deep Ibiza sunset: the "
                            "sun low on or just touching the horizon, a dramatic glowing sky in deep red, crimson, "
                            "burnt orange and dark amber, fiery red reflections on the darkening sea. The surroundings "
                            "are already dim and moody, in warm low-key shadows, lit only by the red afterglow, warm "
                            "string lights, lanterns and candles; natural wood, thatch and white canopy drapes catching "
                            "the red light, relaxed elegant guests as warm silhouettes, natural skin texture, subtle "
                            "film grain, slight background blur, dark, warm, rich and cinematic, luxury beach-club "
                            "magazine look, advertiser-friendly. Moody cinematic orange and teal colour grading: the "
                            "sun, sunset glow and warm lights in strong orange and gold, while the upper sky, the sea "
                            "and the shadows fall into contrasting teal and turquoise tones." + _NO_TEXT),
    # Winter-Cabin-Linie (Rolf 09.10.2026): Rolfs Bildprompt – Luxus-Blockhütte bei Nacht, Kamin, Panoramafenster, Schneefall
    "Cozy Winter Cabin": (" Cinematic wide-angle interior photograph, professional architectural interior photography, "
                          "shot on a 35mm lens at f/2.8, hyper-realistic, photorealistic textures, clean static "
                          "composition, balanced 16:9 framing, cinematic color grading. Night: perfect contrast between the "
                          "freezing blue night outside the large windows with heavy falling snow and the warm amber glow "
                          "inside. The burning fireplace with clearly visible flames and the windows with falling snow are "
                          "both prominent; the upper part of the frame is calm. No people, no animals, no hands; any "
                          "magazines or books show no readable text. Real photograph, not CGI, not a render, not an "
                          "illustration." + _NO_TEXT),
}
DEFAULT_GENRE = "Mediterranean Spa Lounge"

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
    "image_pro_4k": 0.24,    # Nano Banana Pro in 4K (Hauptbild je Mix für Cover + Thumbnail), Stand 08.10.2026
    "veo_sec_4k_fast": 0.30,  # Veo 3.1 Fast in 4K, je Sekunde Video (Kaminfilm-Loops der Winter-Cabin-Linie), Stand 09.10.2026
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
# Bewegte Visuals (sanft atmendes Licht um das Cover) statt Standbild; MIX_ANIMATED_VISUALS=0 schaltet auf das alte Standbild zurück
ANIMATED_VISUALS = os.environ.get("MIX_ANIMATED_VISUALS", "1") == "1"
BILLING_URL = "https://console.cloud.google.com/billing?project=bodydashboard-fde82"
MP3_BITRATE = "192k"


def require(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        raise RuntimeError(f"Umgebungsvariable {name} fehlt")
    return val
