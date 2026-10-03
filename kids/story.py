"""Tägliche Story: Thema wählen (keine Wiederholung), Mini-Drehbuch mit 2 Shots à 8 s, Figur, Sounds, Metadaten.

Ergebnis ist ein dict (siehe SCHEMA), das als story.json im Build-Ordner liegt.
"""
import json
import random
from datetime import date

from . import config, gemini

SCHEMA = {
    "slug": "kebab-case-id-ohne-datum",
    "theme": "ein Satz, worum es geht",
    "character": {
        "name": "Eigenname (erfunden)",
        "species": "z. B. baby hamster",
        "look": "sehr genaue Beschreibung von Körper, Fell/Haut, Farben, Augen, Kleidung/Accessoire – für Bildkonsistenz",
    },
    "setting": "Ort/Tageszeit in dieser Welt – farbenfroh (Blumenwiese, Spielzimmer, Licht, Requisiten), nie ein schlichter heller Hintergrund",
    "goal": "was die Figur will und warum (1 Satz, für ein Kleinkind sofort verständlich)",
    "logic": "warum die Lösung funktioniert: Ursache → Wirkung, nur mit Dingen, die in Shot 1 schon zu sehen sind",
    "shots": [
        {"seconds": 8, "action": "Ziel + Problem: Figur will etwas, ein Hindernis ist sichtbar, 1–2 klare Aktionen, Kamera, Mimik, Bewegung in einfachen Worten",
         "sounds": "welche Töne/Geräusche hörbar sind (keine Stimmen, keine Worte)", "ends_with": "Endbild dieses Shots"},
        {"seconds": 8, "action": "Lösung + Pointe: Figur löst das Problem auf logische Weise und erreicht das Ziel, endet auf dem Startbild von Shot 1 (Loop)",
         "sounds": "...", "ends_with": "..."},
    ],
    "music": "Lyria-Prompt: fröhlich, kindgerecht, instrumental, 15 Sekunden, Instrumente",
    "title": "YouTube-Titel (EN, < 70 Zeichen, emotional + Suchwort, 1 Emoji, endet mit #shorts)",
    "description": "YouTube-Beschreibung (EN, 3–5 Zeilen, erst die Story in 1 Satz, dann Keywords für Eltern, dann Hashtags)",
    "tags": ["10–20 englische Tags"],
    "thumbnail_moment": "welcher Moment als Vorschaubild taugt (Shot 1 oder 2, Sekunde)",
}

SYSTEM = (
    "You are a children's animation director and YouTube Shorts strategist. You write 15-second wordless stories "
    "for toddlers (age 1–5) in a Pixar-style 3D look: ultra cute original animal characters, bright pastel colors, "
    "gentle slapstick and a story that MAKES SENSE: the character clearly wants something, a visible obstacle "
    "blocks it, the character tries something, and the solution follows logically (cause and effect) from objects "
    "already shown – then a happy ending where the goal is reached. Nothing random, every prop has a purpose. A "
    "3-year-old must be able to retell it in one sentence ('the fish wanted X, so it did Y'). No speech, no dialogue, no text on "
    "screen, no scary moments, no real-world brands or known characters. Every shot must be simple enough for a "
    "video model: ONE character, ONE clear action per 4 seconds, camera at child eye level, character centered. "
    "Answer ONLY with valid JSON that matches the given schema."
)


def pick_theme(used_titles: list[str], rnd: random.Random) -> str:
    """Thema aus dem Pool, das in den bisherigen Titeln noch nicht vorkommt (Wortüberlappung)."""
    used = " ".join(used_titles).lower()
    pool = list(config.THEME_POOL)
    rnd.shuffle(pool)
    for t in pool:
        key = [w for w in t.split() if len(w) > 4][:2]
        if not all(w.lower() in used for w in key):
            return t
    return pool[0]


def _sanitize(story: dict) -> dict:
    blob = json.dumps(story).lower()
    for w in config.FORBIDDEN_WORDS:
        if w in blob:
            raise ValueError(f"Story enthält geschützten Begriff „{w}“ – neu erzeugen")
    story["title"] = story["title"][:100]
    if "#shorts" not in story["title"].lower():
        story["title"] = (story["title"][:92] + " #shorts").strip()
    story["tags"] = [t[:30] for t in story.get("tags", [])][:20]
    for kw in config.PARENT_KEYWORDS:
        if len(story["tags"]) >= 30:
            break
        if kw not in story["tags"]:
            story["tags"].append(kw)
    desc = story.get("description", "").strip()
    if "#shorts" not in desc.lower():
        desc += "\n\n" + " ".join(config.HASHTAGS)
    story["description"] = desc[:4800]
    assert len(story["shots"]) == 2, "genau 2 Shots erwartet"
    return story


def create(used_titles: list[str], theme: str | None = None, seed: int | None = None, tries: int = 3) -> dict:
    rnd = random.Random(seed if seed is not None else int(date.today().strftime("%Y%m%d")))
    theme = theme or pick_theme(used_titles, rnd)
    prompt = (
        f"Today's theme idea: {theme}\n"
        f"Date: {date.today().isoformat()}\n"
        f"Already published titles (do NOT repeat these stories or characters): {json.dumps(used_titles[-60:])}\n\n"
        f"Write the story as JSON with exactly this schema (same keys, English values):\n{json.dumps(SCHEMA, indent=1)}\n\n"
        "Rules: 2 shots × 8 seconds. Shot 1 = goal + obstacle, Shot 2 = logical solution + payoff (goal reached), and the final frame of shot 2 "
        "must look like the first frame of shot 1 so the video loops seamlessly. Include a half-second pause before "
        "the payoff. Sounds are cartoon SFX and little animal noises only (squeaks, boings, plops, giggles) – never "
        "words. The title must make a parent click: emotion + the animal + what happens, one emoji, ends with #shorts. "
        "Description: first line = the story in one sentence, second line = who it is for (toddlers, calm, no talking), "
        "then 6–10 search phrases parents use, then hashtags. Before answering, check: does the plot make sense "
        "step by step? Is the goal reached at the end? Is the setting bright and colorful? If not, rewrite it."
    )
    last = None
    for _ in range(tries):
        try:
            story = gemini.text_json(prompt, SYSTEM, temperature=1.1)
            story["theme_seed"] = theme
            return _sanitize(story)
        except Exception as e:  # noqa: BLE001
            last = e
            prompt += f"\n\nPrevious attempt failed: {e}. Fix it and answer again with valid JSON only."
    raise RuntimeError(f"Story konnte nicht erzeugt werden: {last}")


def character_sheet_prompt(story: dict) -> str:
    c = story["character"]
    return (f"Character design sheet of {c['name']}, a {c['species']}: {c['look']}. Three views side by side "
            f"(front, three-quarter, side), neutral soft cream background, full body, cheerful expression. "
            f"{config.STYLE_BIBLE}")


def keyframe_prompt(story: dict, shot_idx: int) -> str:
    c = story["character"]
    shot = story["shots"][shot_idx]
    moment = shot["action"] if shot_idx == 0 else shot["ends_with"]
    return (f"{c['name']} the {c['species']} ({c['look']}) in {story['setting']}. Scene: {moment}. "
            f"Single character, centered, full body visible, camera at child eye level. {config.STYLE_BIBLE}")


def veo_prompt(story: dict, shot_idx: int) -> str:
    c = story["character"]
    shot = story["shots"][shot_idx]
    why = f"Story logic: {story['goal']} {story['logic']} " if story.get("goal") else ""
    return (f"Pixar-style 3D animation, {c['name']} the {c['species']} ({c['look']}) in {story['setting']}. "
            f"{why}This shot: {shot['action']} Ends with: {shot['ends_with']}. Audio: {shot['sounds']} – cute cartoon sound effects "
            f"and soft animal noises only, absolutely no speech, no words, no singing. Smooth, gentle motion, "
            f"expressive face, clear readable action, vivid rich candy colors, colorful detailed background, warm backlight, bokeh particles, shallow depth of field, "
            f"vertical 9:16, no text on screen.")


def thumbnail_prompt(story: dict) -> str:
    c = story["character"]
    return (f"YouTube thumbnail: extreme close-up of {c['name']} the {c['species']} ({c['look']}) with a huge "
            f"surprised, delighted expression, {story['thumbnail_moment']}, {story['setting']}, big sparkling eyes "
            f"looking at the camera, bright and colorful, {config.STYLE_BIBLE}")
