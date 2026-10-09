"""Planer: entscheidet eigenständig, welcher Mix als Nächstes produziert wird, und erzeugt das Konzept.

1. Richtung (Briefing): Genre-Rotation aus dem Gedächtnis (nie dasselbe Genre wie beim letzten Mix, lange nicht
   bediente Themen zuerst), gewichtet mit den Analytics (Wiedergabeminuten je Genre), dazu Zweck, BPM, Bildmotiv
   und Lichtstimmung, die zuletzt nicht verwendet wurden – alle vier Kanalthemen bleiben erhalten, nur die
   Ausprägung wechselt.
2. Konzept: Textmodell (Gemini) mit prompts/concept_prompt.md + Briefing + Vorgeschichte → JSON; wird geprüft
   (Pflichtfelder, 20 + 8 Tracks, alphabetisch, keine wiederverwendeten Titel/Alben, Titellängen) und bei Fehlern
   bis zu dreimal neu angefordert.
"""
import json
import random
import re
from datetime import date
from pathlib import Path

import requests

from . import config, memory

PROMPT_FILE = config.ROOT / "prompts" / "concept_prompt.md"

GENRES = {
    "Mediterranean Spa Lounge": {
        "playlist": "chillout", "bpm": (92, 92),
        "style": ("Luxury Mediterranean Spa Lounge. Modern Balearic chillout with organic house elements, soft downtempo "
                  "beats, relaxing spa atmosphere, warm analog synths, gentle guitar melodies, smooth bassline, ocean "
                  "ambience, chill beach lounge vibes, luxury wellness resort feeling, sunset over Ibiza, deep relaxation, "
                  "positive emotions, highly professional production, cinematic depth, clean mix, no vocals, 92 BPM."),
        "purposes": ["sunset lounge at the sea", "luxury spa & wellness", "beach club chill", "villa dinner background",
                     "yoga & stretching by the ocean", "rooftop evening", "massage & relaxation", "relaxed focus & reading"],
        # Analyse 08.10.2026: erfolgreiche Thumbnails zeigen einen Sehnsuchtsort, Personen nur selten und klein
        "motifs": ["infinity pool above the sea with white lounge beds", "luxury resort terrace lounge with sofas and lanterns over the sea",
                   "beach club with white daybeds and parasols", "white Mediterranean villa with pool and bougainvillea",
                   "yacht deck lounge on turquoise water", "cliffside bar terrace above the Ibiza coast",
                   "small figure of a woman seen from behind at an infinity pool edge (advertiser-friendly)"],
        "moods": ["warm, sunlit, luxurious, relaxed", "positive, smooth, sunset-golden", "airy, organic, deeply relaxing",
                  "cinematic, balmy, elegant"],
    },
    "Dark Ambient Spa": {
        "playlist": "chillout", "bpm": (50, 62),
        "purposes": ["massage & wellness", "hot stone ritual", "sauna & steam", "evening bath", "yin yoga & stretching",
                     "breathwork", "meditation", "floating / sensory calm"],
        "motifs": ["candlelit spa with hot stones, orchids and warm wood", "luxury spa pool with candles and palm leaves",
                   "massage room with candles, white towels and sea view", "outdoor spa pool with lanterns",
                   "spa bath with rose petals and candlelight", "zen spa courtyard with lanterns and bamboo"],
        "moods": ["deep, warm, weightless", "dark, slow, healing", "humid, soft, timeless", "still, glowing, serene"],
    },
    "Chillout Sleep": {
        "playlist": "chillout", "bpm": (45, 65),
        "purposes": ["fall asleep fast", "study & deep focus", "night forest rest", "rainy night reading",
                     "insomnia relief", "nap reset", "winter night calm", "ocean night drift"],
        "motifs": ["cozy bedroom with warm lamps and a blue dusk window", "lake cabin with warm windows at blue hour",
                   "lantern-lit dock on calm water at dusk", "reading nook by candlelight",
                   "starry sky over a calm bay with village lights", "hammock on a terrace at dusk"],
        "moods": ["warm, soft, weightless", "hazy, slow, tender", "cool, misty, quiet", "deep, dreamy, slow"],
    },
    # Eigene Linie (Rolf, 08.10.2026): „Italian Chillout Music“, Alben-Reihe „Italian Amalfi Coast & Lake Como Ambience“,
    # Mo/Mi/Fr/So mit `run_auto.py --genre "Italian Chillout"`. Nicht Teil der Di/Fr-Rotation (ROTATION_EXCLUDE).
    # Stichwörter aus YouTube-Recherche: Italian lounge/café/instrumental, Amalfi Coast music, candlelight dinner,
    # lounge dinner party, smooth & piano jazz lounge, Italian bossa nova, aperitivo, dolce vita, sunset/coastal music.
    "Italian Chillout": {
        "playlist": "italian", "bpm": (68, 100),
        "style": ("Italian Riviera Chillout Lounge. Calm, romantic Italian dinner music with an elegant 1960s dolce vita "
                  "jet-set feeling. Soft bossa nova groove with brushed drums and light shaker, warm nylon-string guitar and "
                  "gentle mandolin melodies, mellow Rhodes and grand piano, round upright bass, lush string pads like a "
                  "classic Italian film score, a subtle touch of accordion. Distant sea waves and evening cicadas in the "
                  "background. Sunset aperitivo on the Amalfi Coast, candlelit terrace dinner on Lake Como, Mediterranean "
                  "warmth, relaxed, sophisticated, nostalgic and romantic. Intimate high-end lounge production, warm analog "
                  "tape character, clean mix, no vocals, {BPM} BPM."),
        # Unterstil = Zweck: (BPM-Bereich, Zusatz für den Lyria-Stil)
        "substyles": {
            "Sunset Aperitivo (Amalfi bossa lounge)": ((84, 90), "Focus: Amalfi bossa lounge – bossa groove, nylon guitar lead, "
                                                       "flute accents, sunlit and breezy."),
            "Romantic Dinner (Lake Como piano lounge)": ((68, 74), "Focus: Lake Como piano lounge – solo grand piano with soft "
                                                         "strings and upright bass, candlelit and intimate."),
            "Italian Café (Riviera café jazz)": ((88, 96), "Focus: Riviera café jazz – light swing, muted trumpet, vibraphone, "
                                                 "espresso bar on the piazza."),
            "Evening Relax (dolce vita cinematic)": ((70, 78), "Focus: dolce vita cinematic – sweeping vintage film-score "
                                                     "strings, harp, mandolin tremolo, golden-hour nostalgia."),
            "Terrace Lounge (Mediterranean deep chill)": ((96, 100), "Focus: Mediterranean deep chill – soft Italian deep "
                                                          "house pulse, warm pads, guitar plucks, slow build, still calm."),
        },
        "purposes": [],   # wird aus substyles gefüllt
        # Immer: attraktive Frau in passender Abendgarderobe, Sunset- und Dinnerstimmung, Ort groß im Bild (Rolf 08.10.)
        "motifs": [
            "elegant woman in a fitted emerald-green silk evening gown at a candlelit dinner table on a lemon-tree terrace above Positano",
            "elegant woman in a fitted deep red silk evening gown leaning on a white stone balustrade above the sea at Amalfi",
            "elegant woman in a fitted champagne satin evening gown at a candlelit dinner on a villa terrace in Bellagio, Lake Como",
            "elegant woman in a fitted midnight-blue velvet evening gown on a lakeside terrace with string lights in Varenna, Lake Como",
            "elegant woman in a fitted ivory silk evening gown with a glass of prosecco on a garden terrace in Ravello above the coast",
            "elegant woman in a fitted black evening gown at a candlelit table by the water, classic wooden motorboat on Lake Como",
            "elegant woman in a fitted bronze satin evening gown with an Aperol spritz on a cliffside terrace in Praiano",
        ],
        "moods": ["warm, romantic, golden", "elegant, nostalgic, candlelit", "breezy, sunlit, relaxed",
                  "intimate, sophisticated, calm"],
        "visual_rule": ("For THIS line the general rule 'people only small or seen from behind' does NOT apply. Every "
                        "art_prompt and thumbnail_prompt shows ONE attractive, elegant woman with a feminine silhouette in a "
                        "fitted evening gown that matches the scene (use the motif's gown), clearly visible from knee or "
                        "waist up, face visible and beautiful. Position: in the right half but FULLY INSIDE the frame – the "
                        "centre of her body at about 65-70 % of the image width, with clear space between her and the right "
                        "edge (never cut off at the edge). Her face about one third from the top (not near the top edge – the "
                        "square image is also cropped to 16:9 from the middle). The big title is centred across the image and "
                        "MAY overlap her hair, face or dress – that is wanted, it makes the image more interesting. Always sunset light and dinner mood (candles, wine or aperitivo glasses, "
                        "white linen). The famous place (Amalfi Coast / Lake Como as named in the motif) fills the left side "
                        "and the background, with sunset sky over sea or lake. Write it as a "
                        "real professional editorial photo shoot (camera, lens, natural light, skin texture, film grain) – "
                        "never 'illustration', 'render' or 'digital art'. Classy and advertiser-friendly: no lingerie, no "
                        "cleavage focus, no suggestive pose."),
    },
    # Eigene Linie (Rolf, 09.10.2026, nach drei Testrunden freigegeben): „Ibiza Sunset Lounge“ – klassischer Balearic
    # Sunset Chillout (Café-del-Mar-Gefühl, Markenname bewusst NICHT im Prompt), 88–96 BPM, fast instrumental mit seltenem
    # wortlosem Summen (config.VOCAL_STYLE). Bilder: Beach Club mit Gästen bei tiefem, rotem Sonnenuntergang, dunklere
    # Umgebung, Orange-&-Teal-Filter (config.COLOR_GRADE), Titel oben im Himmel (config.THUMB_TITLE_TOP).
    # Start: `run_auto.py --genre "Ibiza Sunset Lounge"`. Nicht Teil der Di/Fr-Rotation (ROTATION_EXCLUDE).
    "Ibiza Sunset Lounge": {
        "playlist": "ibiza", "bpm": (88, 96),
        "style": ("Classic Balearic sunset chillout, the timeless music of an Ibiza sunset bar as the sun sinks into the "
                  "sea: slow, laid-back downtempo groove with a soft, round, low-key kick and gentle brushed percussion "
                  "and light shakers, no driving four-on-the-floor, warm deep mellow bass, lush slowly evolving pads, "
                  "soft Rhodes and felt piano chords, warm nylon-string Spanish guitar melodies, subtle ambient textures "
                  "and distant waves; spacious, dreamy, slightly melancholic yet warm, unhurried and deeply relaxing. "
                  "Mostly instrumental: at most a rare, wordless, breathy hum far in the background, never lyrics. "
                  "Warm high-end lounge production, clean mix, {BPM} BPM."),
        "purposes": ["sunset at the beach club", "sundowner drinks with friends", "relaxed summer evening on the terrace",
                     "unwind after work with sunset vibes", "slow Sunday chill", "dinner and drinks by the sea",
                     "reading and daydreaming at golden hour"],
        "motifs": [
            "upscale Ibiza beach club on the sand with thatched parasols, white canopy daybeds, relaxed guests and an outdoor DJ booth",
            "luxury beach club seen from a raised wooden terrace, rows of white daybeds along the shoreline, guests chatting and swaying barefoot",
            "cliffside sunset bar terrace above a small Ibiza cove with pine trees, lounge cushions and guests holding drinks",
            "bohemian beach club with rattan lounges, pampas grass, candle lanterns and elegant guests with cocktails",
            "white canopy daybed with cocktails and a candle lantern in the foreground, beach club guests further back",
            "rocky sunset point with a chill-out bar, guests on cushions watching the sun sink into the sea",
            "wooden beach club deck with a thatched DJ booth, string lights and guests softly dancing on the sand",
        ],
        "moods": ["warm, dreamy, laid-back", "melancholic, golden, floating", "sensual, hypnotic, unhurried",
                  "warm, nostalgic, glowing"],
        "visual_rule": ("For THIS line the general image rules 'BRIGHT' and 'people only small or seen from behind' do NOT "
                        "apply. Every art_prompt and thumbnail_prompt shows a luxury Ibiza beach club or sunset bar at a "
                        "LATE, DEEP sunset: the sun low on or touching the horizon, a dramatic sky in deep red, crimson, "
                        "burnt orange and dark amber, fiery red reflections on the darkening sea. The surroundings are "
                        "already dim, moody and warm, lit only by the afterglow, string lights, lanterns and candles. "
                        "Natural wood, thatch, white canopy drapes, pampas grass, palm silhouettes. Relaxed, elegant guests "
                        "in light summer outfits are clearly part of the scene (chatting with drinks, lounging, softly "
                        "dancing barefoot) – classy and advertiser-friendly. thumbnail_prompt: the calm sky with the sun "
                        "fills the UPPER 40 % of the square image (the big title sits at the top), the beach-club scene "
                        "fills the lower part. Write it as a real professional editorial photo (camera, lens, film grain), "
                        "dark, warm and cinematic – never 'illustration', 'render' or 'digital art'."),
    },
    # Eigene Linie (Rolf, 09.10.2026): „Cozy Winter Cabin“ – Cozy Lofi Ambient / Smooth Jazz Fireplace Ambience (Rolfs
    # JSON-Prompt), ca. 60 BPM, instrumental. Video: 4K-Kaminfilm aus Veo-Loops (pipeline/loopvideo.py), produziert von
    # run_cabin.py; Format in config.LINE_FORMAT (≥ 120 Min, 42 + 8 Tracks). Freitags, nicht Teil der Di/Fr-Rotation.
    "Cozy Winter Cabin": {
        "playlist": "cabin", "bpm": (58, 64),
        "style": ("Cozy lofi ambient and smooth jazz fireplace ambience: soft muffled upright felt piano with audible "
                  "mechanical key sounds, warm 1980s analog synth pads with slow attack and rich sustain, gentle brushed "
                  "jazz snare and a deep, lazy lofi kick, smooth acoustic stand-up bass, integrated ambient field "
                  "recordings of a continuously crackling fireplace and a muffled blizzard wind outside. Warm, relaxing, "
                  "intimate, melancholic yet deeply comforting, cinematic. Lofi aesthetic, warm analog tape saturation, "
                  "subtle vinyl crackle blended with the fireplace, long lush reverb like a high vaulted log-cabin "
                  "ceiling, high dynamic range, soft and quiet for background listening. Arrangement: intro with only "
                  "the crackling fire and a slow warm synth drone; then soft felt piano with a minimal slow jazz "
                  "progression at very low velocity with deep bass and sparse brushes; then wide lush pads, laid-back, "
                  "hypnotic; a bridge without percussion, just pads, fire and a nostalgic melodic piano; outro fading "
                  "to a warm synth tail and the fire. Instrumental, {BPM} BPM."),
        "purposes": ["cozy winter night by the fireplace", "reading with a blanket on a snowy evening",
                     "studying and working on a cold winter day", "falling asleep while it snows outside",
                     "slow Sunday morning coffee in the cabin", "unwinding after a long winter day"],
        "motifs": [
            "modern luxury log cabin living room in Montana with a cognac leather sofa and a stone fireplace, "
            "floor-to-ceiling windows onto a snowy pine forest",
            "A-frame cabin with a huge triangular glass front onto snow-covered mountains, a stone fireplace and "
            "a deep sofa with wool blankets",
            "lakeside log cabin with panoramic windows onto a frozen lake and snowy pines, a corner stone fireplace "
            "and a reading nook",
            "mountain chalet living room with exposed timber beams, a black steel wood stove next to tall windows and "
            "a plush sheepskin-covered sofa",
            "Scandinavian modern cabin with warm oak walls, a round hanging fireplace and big windows onto a snowy "
            "birch forest",
            "rustic log cabin with a large fieldstone hearth, a leather armchair with a knitted blanket and a big "
            "window onto a blizzard in the pines",
        ],
        "moods": ["warm, intimate, comforting", "melancholic, nostalgic, cozy", "calm, hypnotic, dreamy",
                  "soft, safe, slow"],
        "visual_rule": ("For THIS line the general image rules 'BRIGHT' and 'people small' do NOT apply. Every "
                        "art_prompt and thumbnail_prompt is an INTERIOR of an ultra-cozy luxury log cabin at NIGHT: a "
                        "glowing fireplace with clearly visible flames on one side, large windows showing heavy falling "
                        "snow over a dark snowy forest under a deep night sky, warm amber light inside vs. freezing blue "
                        "outside, a sofa or armchair with knitted wool blankets, a low wooden table with candles and a "
                        "mug. NO people, NO animals. The upper part of the frame (beams, night sky behind glass) is calm. "
                        "Static camera, no motion blur. Write it as a real photograph, never 'illustration' or 'render'."),
        "title_rule": ("Title pattern for THIS line: '[Album] · Cozy Winter Cabin · {HOURS} Relaxing Fireplace Chillout 4K' "
                       "or with a short variant of the last segment (e.g. '{HOURS} Fireplace & Lofi Jazz 4K'). Always use "
                       "{HOURS}, never {MIN}. Mention '4K', 'fireplace' and 'snow' in hook or tags. No BPM in the title."),
    },
}
ROTATION_EXCLUDE = {"Italian Chillout", "Ibiza Sunset Lounge", "Cozy Winter Cabin"}   # eigene Linien mit eigenem Zeitplan → nicht in der Genre-Wahl
for _g in GENRES.values():
    if _g.get("substyles"):
        _g["purposes"] = list(_g["substyles"])
# Strategie 05.10.2026: Sleep/Spa haben den höchsten RPM (ca. 4–8 $) und die längsten Sitzungen → häufiger;
# Gym- und Night-Drive-Mixe eingestellt (Rolf, 08.10.2026).
GENRE_WEIGHT = {"Mediterranean Spa Lounge": 1.6, "Chillout Sleep": 1.35, "Dark Ambient Spa": 1.25}
LIGHTS = {
    "Mediterranean Spa Lounge": ["golden hour sunset over the sea", "bright sunny Mediterranean afternoon", "pink-orange Ibiza sunset sky",
                                 "warm amber dusk with lanterns", "low sun glittering on turquoise water",
                                 "clear blue sky with white architecture"],
    "Dark Ambient Spa": ["warm golden candlelight", "golden hour through large windows", "lanterns at dusk",
                         "warm amber glow with green plants", "soft morning sun and steam"],
    "Chillout Sleep": ["deep blue dusk with warm window lights", "candlelight", "moonlight with warm lamps",
                       "starry sky with a warm glow", "warm reading lamp at blue hour"],
    # dunkler und wärmer (Rolf 09.10. abends): tiefer Sonnenuntergang statt heller Goldstunde, Kerzenlicht
    "Italian Chillout": ["deep red-orange sunset with the sun touching the water", "crimson and amber sunset sky with the candles lit",
                         "last afterglow of the sunset with candlelight and village lights", "warm amber sunset glow reflected on the darkening water",
                         "last red sunset light on the old Italian buildings"],   # ortsneutral: passt zu Küste UND See
    "Ibiza Sunset Lounge": ["deep red sun touching the horizon", "sun half below the horizon under a crimson sky",
                            "last minutes of sunset with a burnt-orange afterglow", "fiery red sky reflected on the darkening sea",
                            "dark amber afterglow just after sunset with the first lanterns glowing"],
    "Cozy Winter Cabin": ["deep blue snowy night with a warm amber fireplace glow", "starry winter night with heavy snowfall",
                          "blue hour turning to night with candlelight inside", "moonlit snow outside, firelight inside",
                          "dark blizzard night with a glowing hearth"],
}


def _recent(mem: dict, key, n: int) -> set:
    vals = []
    for m in mem.get("mixes", [])[-n:]:
        v = key(m)
        if v:
            vals.append(str(v).lower())
    return set(vals)


def _pick(options: list[str], avoid: set[str], rnd: random.Random) -> str:
    free = [o for o in options if o.lower() not in avoid]
    return rnd.choice(free or options)


def genre_scores(mem: dict, analytics_rows: list[dict] | None) -> dict[str, dict]:
    """Punkte je Genre: Abstand zum letzten Einsatz (0..1) + Leistung laut Analytics (0..1)."""
    mixes = mem.get("mixes", [])
    by_video = {m.get("video_id"): m["genre"] for m in mixes if m.get("video_id")}
    perf: dict[str, list[float]] = {g: [] for g in GENRES}
    for r in analytics_rows or []:
        g = by_video.get(r.get("videoId"))
        if g in perf:
            perf[g].append(float(r.get("minutesWatched", 0)))
    avg = {g: (sum(v) / len(v) if v else None) for g, v in perf.items()}
    top = max([a for a in avg.values() if a], default=None)
    out = {}
    for g in GENRES:
        last_idx = max((i for i, m in enumerate(mixes) if m["genre"] == g), default=None)
        gap = len(mixes) - last_idx if last_idx is not None else 99
        recency = min(gap, 4) / 4
        performance = 0.5 if avg[g] is None or not top else avg[g] / top
        out[g] = {"recency": round(recency, 2), "performance": round(performance, 2), "gap": gap,
                  "score": round((0.6 * recency + 0.4 * performance) * GENRE_WEIGHT.get(g, 1.0), 3)}
    return out


# Pflicht-Kernbegriff am Titelanfang je Genre (siehe prompts/concept_prompt.md). Ohne diese Prüfung konnte das
# Textmodell trotz Vorgabe einen fremden Begriff wählen – genau das ist beim Sleep-Mix „Starlight Slumber“
# (06.10.2026) passiert: Titel begann mit „Slow Beat“ statt „Sleep Music“, was Klicks mit falscher Erwartung
# (energiegeladener Beat statt ruhiger Ambient-Sound) und dadurch frühe Abbrüche begünstigt.
GENRE_TITLE_PREFIX = {g: (k.lower(),) for g, k in config.THUMB_KEYWORD.items()}   # = Begriff auf dem Thumbnail

# Suchbegriffe aus den Analytics stammen auch von alten Videos (Drohne, Walks). Nur Begriffe, die zum Genre passen, dürfen
# in Titel/Tags einfließen – sonst entstehen Titel wie „Slow Beat“ für einen Sleep-Mix (Fehler vom 06.10.2026).
GENRE_KEYWORDS = {
    "Chillout Sleep": ("sleep", "nap", "insomnia", "rain", "calm", "relax", "dream", "lullaby", "bed"),
    "Dark Ambient Spa": ("spa", "massage", "sauna", "wellness", "yoga", "stone", "ambient", "relax", "meditat"),
    "Mediterranean Spa Lounge": ("lounge", "chill", "sunset", "ibiza", "beach", "balearic", "spa", "mediterr", "cafe"),
    "Italian Chillout": ("ital", "amalfi", "como", "positano", "dinner", "lounge", "jazz", "bossa", "cafe", "sunset", "mediterr"),
    "Ibiza Sunset Lounge": ("ibiza", "balearic", "sunset", "lounge", "chill", "beach", "cafe del mar", "sundowner", "summer"),
    "Cozy Winter Cabin": ("cabin", "fireplace", "winter", "snow", "cozy", "fire", "jazz", "lofi", "cold"),
}


def relevant_terms(mem: dict, genre: str, n: int = 8) -> list[str]:
    keys = GENRE_KEYWORDS.get(genre, ())
    terms = [t["term"] for t in (mem.get("search_terms") or []) if any(k in t["term"].lower() for k in keys)]
    return terms[:n]


# Fokus-Genre (Rolf, 06.10.2026: „davon im Verhältnis noch mehr“): etwa jeder zweite Mix, nie mehr als zwei in Folge.
FOCUS_GENRE = "Mediterranean Spa Lounge"
FOCUS_SHARE = 0.55
FOCUS_WINDOW = 6


def focus_due(mem: dict) -> bool:
    recent = [m.get("genre") for m in (mem.get("mixes") or [])][-FOCUS_WINDOW:]
    if len(recent) >= 2 and recent[-1] == recent[-2] == FOCUS_GENRE:
        return False
    return sum(1 for g in recent if g == FOCUS_GENRE) / max(len(recent), 1) < FOCUS_SHARE


LONG_GENRES = ("Chillout Sleep", "Dark Ambient Spa", "Mediterranean Spa Lounge")   # Lang-Format nur dort, wo lange Sitzungen üblich sind


def choose_brief(mem: dict, analytics_rows: list[dict] | None = None, seed: int | None = None,
                 force_genre: str | None = None, long: bool = False) -> dict:
    rnd = random.Random(seed if seed is not None else int(date.today().strftime("%Y%m%d")))
    # Eigene Linien (Italien) laufen getrennt: ihre Mixe zählen nicht für Rotation, Fokus-Quote und „letztes Genre“
    # der Di/Fr/So-Mixe – und umgekehrt sieht die Italien-Linie bei Motiv/Licht nur ihre eigenen Mixe.
    own_line = force_genre in ROTATION_EXCLUDE
    all_mixes = mem.get("mixes") or []
    view = dict(mem, mixes=[m for m in all_mixes if (m.get("genre") in ROTATION_EXCLUDE) == own_line])
    mem = view
    scores = {g: s for g, s in genre_scores(mem, analytics_rows).items() if own_line or g not in ROTATION_EXCLUDE}
    last_genre = (mem.get("mixes") or [{}])[-1].get("genre")
    if force_genre:
        genre = force_genre
    else:
        ranked = sorted(scores.items(), key=lambda kv: kv[1]["score"] + rnd.uniform(0, 0.15), reverse=True)
        if long:
            ranked = [kv for kv in ranked if kv[0] in LONG_GENRES] or ranked
        ranked = [kv for kv in ranked if kv[0] != last_genre] or ranked   # sonst nie zweimal hintereinander dasselbe Genre
        genre = ranked[0][0]
        if focus_due(mem):
            genre = FOCUS_GENRE
    g = GENRES[genre]
    same = [m for m in mem.get("mixes", []) if m["genre"] == genre]
    avoid_purpose = {str(m.get("purpose", "")).lower() for m in same[-3:]}
    avoid_motif = _recent(mem, lambda m: (m.get("visual") or {}).get("motif_family"), 4)
    avoid_light = _recent(mem, lambda m: (m.get("visual") or {}).get("light"), 3)
    avoid_mood = {str(m.get("mood", "")).lower() for m in same[-2:]}
    used_bpm = [m["bpm"] for m in same[-3:]]
    purpose = _pick(g["purposes"], avoid_purpose, rnd)
    style = g.get("style", "")
    lo, hi = g["bpm"]
    sub = (g.get("substyles") or {}).get(purpose)
    if sub:                                    # Unterstil bestimmt Tempo und den Zusatz zum Lyria-Stil
        (lo, hi), extra = sub
        style = f"{style} {extra}"
    candidates = [b for b in range(lo, hi + 1, 2) if all(abs(b - u) >= 4 for u in used_bpm)] or list(range(lo, hi + 1, 2))
    bpm = rnd.choice(candidates)
    brief = {
        "date": date.today().isoformat(), "genre": genre, "playlist": g["playlist"], "bpm": bpm,
        "purpose": purpose, "mood_hint": _pick(g["moods"], avoid_mood, rnd),
        "motif_family": _pick(g["motifs"], avoid_motif, rnd), "light": _pick(LIGHTS[genre], avoid_light, rnd),
        "scores": scores, "last_genre": last_genre,
        "long": long, "style": style.replace("{BPM}", str(bpm)), "visual_rule": g.get("visual_rule", ""),
        "title_rule": g.get("title_rule", ""),
        "search_terms": relevant_terms(mem, genre),
    }
    return brief


def brief_text(b: dict) -> str:
    session = "evening lounge" if b.get("genre") in ROTATION_EXCLUDE else "sleep/relax"
    fmt = (f"Format: LONG {session} session of {config.LONG_MIN_MINUTES // 60} hours or more "
           f"({config.LONG_PLANNED_TRACKS}+{config.LONG_EXTRA_TRACKS} track titles). Use {{HOURS}} in the title, never {{MIN}}. "
           f"Even more continuous, seamless and calm than a normal mix; tracks flow into each other.\n" if b.get("long") else "")
    if b.get("style"):
        fmt += (f"MANDATORY SOUND STYLE for all tracks (stay faithful to it, vary only melody, instruments and "
                f"arrangement per track): {b['style']}\n")
    if b.get("visual_rule"):
        fmt += f"MANDATORY VISUAL RULE (overrides the general image rules): {b['visual_rule']}\n"
    lf = config.LINE_FORMAT.get(b.get("genre", ""))
    if lf:
        fmt += (f"Format: {lf['min_minutes'] // 60}-hour 4K fireplace film with music ({lf['tracks']}+{lf['extra']} track "
                f"titles; tracks flow seamlessly into each other).\n")
    if b.get("title_rule"):
        fmt += f"MANDATORY TITLE RULE: {b['title_rule']}\n"
    return (fmt + f"Date: {b['date']}\nGenre: {b['genre']} (playlist: {b['playlist']})\nBPM: {b['bpm']}\n"
            f"Purpose / listening situation: {b['purpose']}\nMood direction: {b['mood_hint']}\n"
            f"Visual motif family: {b['motif_family']}\nLight: {b['light']}\n"
            f"Why this genre now: last mix was {b['last_genre'] or '-'}; genre scores {json.dumps(b['scores'])}"
            + (f"\nReal viewer search terms that fit this genre (inspiration for 1–2 keywords in hook and tags; right after the album "
               f"name the title must continue with exactly '{config.THUMB_KEYWORD.get(b['genre'], b['genre'])}'): "
               f"{', '.join(b['search_terms'])}"
               if b.get("search_terms") else
               "\nKeyword angle: pick ONE specific search phrase for this mix (e.g. use case + duration) that differs "
               "from the titles in the history, and use it in title, hook and tags. Right after the album name the title must continue with "
               f"exactly '{config.THUMB_KEYWORD.get(b['genre'], b['genre'])}' (this word is also the big thumbnail text)."))


# ---------------------------------------------------------------- Textmodell

def _gemini_json(prompt: str, model: str, timeout: int = 240) -> dict:
    url = f"{config.GEMINI_BASE}/models/{model}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}}  # ohne temperature (von Google abgekündigt)
    r = requests.post(url, headers={"x-goog-api-key": config.require("GOOGLE_API_KEY"),
                                    "Content-Type": "application/json"}, json=body, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"{model} HTTP {r.status_code}: {r.text[:300]}")
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(text)


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _words(s: str) -> int:
    return len(re.findall(r"[A-Za-z0-9'’]+", s))


TITLE_SEP = " · "


def unify_title(title: str, album: str, keyword: str | None = None, max_len: int = 90) -> str:
    """Wiedererkennung (Rolf, 07./08.10.2026): Video-, Album-, Cover- und Thumbnail-Titel gehören zusammen.
    Der YouTube-Titel beginnt immer exakt mit dem Albumnamen, direkt dahinter steht der Genre-Begriff vom Thumbnail
    (config.THUMB_KEYWORD), dann die übrigen Suchbegriffe. Steht der Albumname schon vorne/hinten, wird er nicht gedoppelt."""
    a = re.escape(album.strip())
    rest = title.strip()
    rest = re.sub(r"^" + a + r"\s*[–\-·|:]*\s*", "", rest, flags=re.I)      # schon vorne → nicht doppeln
    rest = re.sub(r"\s*[–\-·|:]+\s*" + a + r"$", "", rest, flags=re.I)      # „… – Album" am Ende → nach vorne
    rest = re.sub(r"\s{2,}", " ", rest).strip(" –-·|:")
    if keyword and not rest.lower().startswith(keyword.lower()):
        parts = [p for p in rest.split(TITLE_SEP) if p.strip()]
        # erstes Segment ist meist ein anderer Genre-Begriff („Spa Music") → durch den Thumbnail-Begriff ersetzen
        if parts and not re.search(r"\{MIN\}|\{HOURS\}|\d", parts[0]):
            parts = parts[1:]
        rest = TITLE_SEP.join([keyword, *parts])
    def ln(t):
        return len(t.replace("{MIN}", "60").replace("{HOURS}", "2.5 Hours"))
    full = f"{album.strip()}{TITLE_SEP}{rest}" if rest else album.strip()
    while ln(full) > max_len and TITLE_SEP in rest and rest.count(TITLE_SEP) >= 2:
        segs = rest.split(TITLE_SEP)
        cand = [i for i in range(1, len(segs)) if not re.search(r"\{MIN\}|\{HOURS\}|BPM", segs[i])]
        drop = max(cand, key=lambda i: len(segs[i])) if cand else None
        if drop is None:
            break
        segs.pop(drop)
        rest = TITLE_SEP.join(segs)
        full = f"{album.strip()}{TITLE_SEP}{rest}"
    return full


def track_counts(brief: dict) -> tuple[int, int, int]:
    """(Haupt-Tracks, Reserve-Tracks, Mindestminuten) – Linien mit eigenem Format (config.LINE_FORMAT) zuerst."""
    fmt = config.LINE_FORMAT.get(brief.get("genre", ""))
    if fmt:
        return fmt["tracks"], fmt["extra"], fmt["min_minutes"]
    if brief.get("long"):
        return config.LONG_PLANNED_TRACKS, config.LONG_EXTRA_TRACKS, config.LONG_MIN_MINUTES
    return config.PLANNED_TRACKS, config.EXTRA_TRACKS, config.MIN_MIX_MINUTES


def validate(c: dict, mem: dict, brief: dict) -> list[str]:
    """Liefert eine Liste von Beanstandungen (leer = ok). Kleine Dinge werden direkt repariert."""
    errs = []
    req = ["album", "genre", "bpm", "mood", "purpose", "sound_design", "tracks", "extra_tracks", "visual", "art_prompt",
           "thumbnail_prompt", "yt_title", "hook", "intro", "use_line", "cta_question", "hashtags",
           "tags", "ab_titles", "short_overlays", "short_titles", "shorts", "title_de", "teaser_de",
           "pinned_comment"]
    for k in req:
        if k not in c or c[k] in ("", None, [], {}):
            errs.append(f"Feld fehlt: {k}")
    if errs:
        return errs
    c["genre"], c["playlist"], c["bpm"] = brief["genre"], brief["playlist"], int(brief["bpm"])
    if isinstance(c.get("mood"), list):
        c["mood"] = ", ".join(str(m) for m in c["mood"])
    if brief.get("style") and brief["style"] not in str(c.get("sound_design", "")):
        c["sound_design"] = f"{brief['style']} {c.get('sound_design', '')}".strip()   # Stil-Vorgabe geht 1:1 in jeden Lyria-Prompt
    is_long = bool(brief.get("long"))
    c["minutes_per_track"] = 5
    n_main, n_extra, c["min_minutes"] = track_counts(brief)
    c["format"] = "long" if is_long else ("line" if brief.get("genre") in config.LINE_FORMAT else "standard")
    if c["album"].strip().lower() in memory.used_albums(mem):
        errs.append(f"Album-Name schon verwendet: {c['album']}")
    used = memory.used_track_titles(mem)
    for key, want in (("tracks", n_main), ("extra_tracks", n_extra)):
        lst = [t for t in c[key] if isinstance(t, dict) and t.get("title") and t.get("variation")]
        if len(lst) < want - 2:
            errs.append(f"{key}: {len(lst)} statt {want}")
        lst.sort(key=lambda t: t["title"].lower())
        c[key] = lst[:want]
    titles = [t["title"].strip() for t in c["tracks"] + c["extra_tracks"]]
    low = [t.lower() for t in titles]
    if len(set(low)) != len(low):
        errs.append("doppelte Track-Titel")
    reused = [t for t in titles if t.lower() in used]
    if reused:
        errs.append(f"Track-Titel schon verwendet: {reused}")
    if any(re.search(r"reprise|track \d|study \d", t, re.I) for t in titles):
        errs.append("generische Titel (Reprise/Track n/Study n)")
    if (not is_long and c["tracks"] and c["extra_tracks"]
            and c["extra_tracks"][0]["title"].lower() < c["tracks"][-1]["title"].lower()):
        errs.append("extra_tracks müssen alphabetisch nach dem letzten regulären Track liegen")
    if _words(c["album"]) > 3:
        errs.append("Album-Name zu lang (max. 3 Wörter, er steht groß auf dem Thumbnail)")
    c["album"] = c["album"].strip()
    kw = config.THUMB_KEYWORD.get(brief["genre"])
    c["yt_title"] = unify_title(c["yt_title"], c["album"], kw)
    c["ab_titles"] = [unify_title(t, c["album"], kw) for t in c.get("ab_titles") or []]
    c["thumbnail_headline"] = c["album"]          # Thumbnail zeigt exakt den Albumnamen
    t_len = len(c["yt_title"].replace("{MIN}", "60").replace("{HOURS}", "2.5 Hours"))
    if t_len > 90:
        errs.append(f"yt_title zu lang ({t_len})")
    if "{MIN}" not in c["yt_title"] and "{HOURS}" not in c["yt_title"]:
        errs.append("yt_title ohne {MIN}/{HOURS}")
    if re.search(r"\b\d{2,3}\s*min", c["yt_title"], re.I) or re.search(r"\b\d{2,3}\s*min", c["hook"], re.I):
        errs.append("feste Minutenzahl in Titel/Hook – {MIN} verwenden")
    title_kw = GENRE_TITLE_PREFIX.get(brief["genre"])
    after_album = c["yt_title"][len(c["album"]):].strip(" –-·|:").lower()
    if title_kw and not after_album.startswith(title_kw):
        errs.append(f"yt_title: nach dem Albumnamen fehlt der Genre-Kernbegriff ({'/'.join(title_kw)}) – "
                     f"sonst Erwartungs-Mismatch wie bei „Slow Beat“ für einen Sleep-Mix")
    c["hashtags"] = [h if h.startswith("#") else "#" + h for h in c["hashtags"]][:5]
    if "#AixWalker" not in c["hashtags"]:
        c["hashtags"] = c["hashtags"][:4] + ["#AixWalker"]
    tags = [t.strip().lower() for t in c["tags"] if t.strip()]
    for must in ("aixwalker", "aix walker"):
        if must not in tags:
            tags.append(must)
    c["tags"] = tags[:15]
    if len(c["tags"]) < 10:
        errs.append("zu wenige Tags")
    c["ab_titles"] = [t for t in c["ab_titles"] if len(t.replace("{MIN}", "60").replace("{HOURS}", "1 Hour")) <= 90][:3]
    # ab_titles sind nur Vorschläge für die Mail – zu wenige blockieren das Konzept nicht
    c["ab_thumbs"] = []   # kein Thumbnail mit abweichendem Text – Wiedererkennung über den Albumnamen
    c["short_overlays"] = [t for t in c["short_overlays"] if _words(t) <= 4][:2]
    if len(c["short_overlays"]) < 2:
        errs.append("Overlays/Headline zu lang")
    c["short_titles"] = [t[:70] for t in c["short_titles"]][:2]
    for k in ("art_prompt", "thumbnail_prompt"):
        if "no text" not in c[k].lower():
            c[k] = c[k].rstrip(". ") + ". No text, no letters, no logos."
    v = c["visual"]
    v.setdefault("motif_family", brief["motif_family"])
    v.setdefault("light", brief["light"])
    c["slug"] = f"{date.today().isoformat()}-{_slugify(c['album'])}"
    return errs


def generate_concept(mem: dict, brief: dict, attempts: int = 3, log=print) -> dict:
    tmpl = PROMPT_FILE.read_text(encoding="utf-8").split("---", 1)[1]
    used = sorted(memory.used_track_titles(mem))
    prompt = (tmpl.replace("{{BRIEF}}", brief_text(brief))
              .replace("{{HISTORY}}", memory.summary_for_prompt(mem))
              .replace("{{USED_TITLES}}", ", ".join(used) or "(none)")
              .replace("{{LEARNINGS}}", "\n".join("- " + s for s in mem.get("learnings", [])) or "-")
              .replace("{{GENRE}}", brief["genre"]).replace("{{BPM}}", str(brief["bpm"]))
              .replace("{{N_TRACKS}}", str(track_counts(brief)[0]))
              .replace("{{N_EXTRA}}", str(track_counts(brief)[1]))
              .replace("{{PLAYLIST}}", brief["playlist"]).replace("{{MOTIF_FAMILY}}", brief["motif_family"])
              .replace("{{LIGHT}}", brief["light"]))
    feedback = ""
    last_errs: list[str] = []
    for attempt in range(attempts):
        for model in (config.TEXT_MODEL, config.TEXT_MODEL_FALLBACK):
            try:
                c = _gemini_json(prompt + feedback, model)
                break
            except Exception as e:  # noqa: BLE001
                log(f"[planner] {model}: {e}")
                c = None
        if not c:
            continue
        last_errs = validate(c, mem, brief)
        if not last_errs:
            log(f"[planner] Konzept „{c['album']}“ ({c['genre']}, {c['bpm']} BPM) nach {attempt + 1} Versuch(en)")
            return c
        log(f"[planner] Versuch {attempt + 1}: {last_errs}")
        feedback = "\n\n## Your previous answer was rejected – fix exactly these points and answer again with full JSON:\n" + \
                   "\n".join("- " + e for e in last_errs)
    raise RuntimeError(f"Planer: kein gültiges Konzept nach {attempts} Versuchen: {last_errs}")


def write_concept(c: dict, folder: Path = config.ROOT / "concepts") -> Path:
    folder.mkdir(exist_ok=True)
    p = folder / f"{c['slug']}.json"
    p.write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


if __name__ == "__main__":
    import sys
    mem = memory.load(use_drive="--local" not in sys.argv)
    b = choose_brief(mem)
    print(brief_text(b))
    if "--concept" in sys.argv:
        c = generate_concept(mem, b)
        print(write_concept(c))
