"""Tägliche Story: neues Tier × neuer Lehrinhalt, Mini-Geschichte mit Sinn, strenge Prüfung vor dem Dreh.

Ablauf:
1. `pick()` wählt Tier und Lehrinhalt, die im Verlauf (kids/history.py) lange nicht dran waren – echter Zufall,
   nicht an das Datum gebunden (zwei Läufe am selben Tag bekommen verschiedene Themen).
2. Gemini schreibt die Geschichte (4 Takte: Wunsch → Problem → Idee/Lösung → glückliches Ende mit Lerneffekt).
3. Ein stärkeres Modell (config.CRITIC_MODEL) prüft streng: Logik, Verständlichkeit für Kleinkinder, Lerninhalt,
   Drehbarkeit für eine Video-KI, Neuheit gegenüber dem Verlauf. Unter der Mindestnote wird mit der Kritik neu
   geschrieben (max. 4 Runden). Erst eine bestandene Story geht an Veo.
Ergebnis ist ein dict (siehe SCHEMA), das als story.json im Build-Ordner liegt.
"""
import json
import random
import re

from . import config, gemini, sfx_library

SCHEMA = {
    "slug": "kebab-case-id",
    "lesson": "the lesson/learning goal in a few words (given below)",
    "summary": "the whole story in ONE simple sentence a 3-year-old could retell: '<Name> wants X, but Y, so <Name> does Z, and now W.'",
    "theme": "same as summary, shorter",
    "character": {
        "name": "invented first name",
        "species": "the given animal",
        "look": "very precise description of body, fur/skin, colors, eyes, ONE accessory – for visual consistency",
    },
    "friend": "optional second character (species + very precise look) or empty string – at most ONE friend",
    "setting": "one bright, colorful, everyday place (playroom, garden, kitchen, park, beach, bedroom ...) with the 2–3 props the story needs, all visible from the start",
    "beats": [
        "1 WANT (0–4 s): what the character wants and why – shown by looking/pointing at it",
        "2 PROBLEM (4–8 s): a simple, visible obstacle; the first try does not work",
        "3 IDEA (8–12 s): the character (or friend) does something sensible that a child could copy",
        "4 HAPPY END (12–15 s): goal reached, the lesson is visible, big smile",
    ],
    "shots": [
        {"seconds": 8, "action": "beats 1+2 in plain words: who does what, where, with which prop; camera, facial expression",
         "sounds": "audible sounds (no voices, no words)", "ends_with": "exact final image of this shot"},
        {"seconds": 8, "action": "beats 3+4 in plain words, continuing exactly from the end of shot 1",
         "sounds": "...", "ends_with": "final happy image"},
    ],
    "sfx_cues": [{"second": "0–14.5, when the sound happens", "sound": "one key from the SOUND LIBRARY below"}],
    "music": "Lyria prompt: cheerful, gentle, child-friendly instrumental (glockenspiel, xylophone, ukulele, soft piano), 15 seconds",
    "title": "YouTube title (EN, < 70 characters, emotion + animal + what happens, 1 emoji, ends with #shorts)",
    "description": "YouTube description (EN, 3–5 lines: story in 1 sentence, what children learn, keywords for parents, hashtags)",
    "tags": ["10–20 English tags"],
    "thumbnail_moment": "which moment works as thumbnail",
}

SYSTEM = (
    "You are an award-winning preschool TV writer (think of the clarity of the best toddler shows) and a director "
    "who knows exactly what AI video models can and cannot animate. You write 15-second wordless mini stories for "
    "children aged 1–5 in a Pixar-style 3D look with an ultra-cute original animal character.\n\n"
    "A GOOD story: everyday situation a toddler knows from their own life; the character clearly WANTS something; "
    "a simple obstacle; the character solves it in a sensible, copyable way (cause → effect); happy ending where "
    "the lesson is visible. Every step follows logically from the one before. Animals behave plausibly for their "
    "kind and stay in their natural element (fish stay in water, nobody breathes underwater who can't, etc.). "
    "Nothing magical, random or unexplained. A 3-year-old must be able to retell it: 'Bunny wanted the ball, but "
    "it was too high, so Bunny got a stool, and now they play.'\n\n"
    "FILMABLE for an AI video model (very important – otherwise the video shows typical AI errors): "
    "one main character (+ at most one friend), large simple props (ball, block, apple, cup, blanket, umbrella, "
    "watering can), slow simple motions on solid ground (walk, look, point, reach, push, pull, carry, give, hug, "
    "sit, nod, clap). AVOID: water/liquid physics, splashing, swimming, pouring large amounts; jumping across gaps, "
    "flying, launching, springs, bouncing high; falling; objects that transform, appear or disappear; tiny objects "
    "handled with fingers; more than 3 props; crowds; text, letters or numbers written anywhere; fast action; "
    "anything scary, sad for long, dangerous or rude. The final image does NOT need to match the first one.\n\n"
    "No speech, no dialogue, no text on screen, no real-world brands or known characters. "
    "Answer ONLY with valid JSON that matches the given schema."
)

CRITIC_SYSTEM = (
    "You are the strict head of a preschool TV channel and an expert for AI video generation. You review a "
    "15-second wordless story for toddlers BEFORE it is produced. Be harsh: only clearly good, logical, original "
    "stories pass. Answer ONLY with valid JSON."
)


def _recent(history: list[dict], key: str, n: int) -> list[str]:
    return [str(e.get(key, "")).lower() for e in history[-n:] if e.get(key)]


def pick(history: list[dict], used_titles: list[str], rnd: random.Random | None = None) -> tuple[str, str]:
    """Tier und Lehrinhalt, die zuletzt nicht vorkamen (auch nicht in YouTube-Titeln)."""
    rnd = rnd or random.SystemRandom()
    recent_species = _recent(history, "species", config.AVOID_SPECIES_DAYS)
    blob = " ".join(recent_species + [t.lower() for t in used_titles[:config.AVOID_SPECIES_DAYS]])

    def species_used(s: str) -> bool:
        main = s.split("(")[0]
        for w in ("baby", "cub", "chick", "pup", "kit", "little", "fluffy", "yellow"):
            main = main.replace(w, " ")
        words = [w for w in main.split() if len(w) > 2]
        return any(w in blob for w in words) if words else s.lower() in blob

    species = [s for s in config.SPECIES_POOL if not species_used(s)] or list(config.SPECIES_POOL)
    recent_lessons = _recent(history, "lesson", config.AVOID_LESSON_DAYS)
    lessons = [l for l in config.LESSON_POOL if l.lower() not in recent_lessons] or list(config.LESSON_POOL)
    return rnd.choice(species), rnd.choice(lessons)


def _sanitize(story: dict) -> dict:
    blob = json.dumps(story).lower()
    for w in config.FORBIDDEN_WORDS:
        if re.search(rf"\b{re.escape(w)}\b", blob):
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
    lib = sfx_library.available()
    cues = []
    for c in story.get("sfx_cues") or []:
        try:
            t = float(str(c.get("second")).replace(",", "."))
        except (TypeError, ValueError):
            continue
        if c.get("sound") in lib and 0 <= t <= 14.5:
            cues.append({"second": round(t, 2), "sound": c["sound"]})
    story["sfx_cues"] = sorted(cues, key=lambda c: c["second"])[:8]
    assert story.get("summary") and story.get("character", {}).get("species"), "summary/species fehlen"
    return story


def _history_text(history: list[dict]) -> str:
    rows = [f"- {e.get('species', '')}: {e.get('summary') or e.get('theme', '')}" for e in history[-60:]]
    return "\n".join(rows) or "- (none yet)"


def review(story: dict, history: list[dict]) -> dict:
    """Strenge Prüfung vor dem Dreh. Liefert {scores{...}, passed, min_score, problems[], fix}."""
    draft = {k: v for k, v in story.items() if k not in ("review", "tags", "description")}
    prompt = (
        f"Story to review:\n{json.dumps(draft, indent=1, ensure_ascii=False)}\n\n"
        f"Stories already published on the channel (must not repeat – same animal, same plot or same idea):\n"
        f"{_history_text(history)}\n\n"
        "Score each criterion from 1 (terrible) to 10 (excellent):\n"
        "- logic: every step follows from the previous one; the solution makes sense in the real world; animals "
        "behave plausibly (e.g. a fish never leaves the water); nothing random or unexplained\n"
        "- clarity: a 2–3-year-old understands what the character wants, what the problem is and how it is solved, "
        "WITHOUT words\n"
        "- lesson: there is a clear, positive, everyday lesson or learning moment that is visible at the end\n"
        "- filmable: an AI video model can animate it without typical errors (no water physics, no jumping/flying/"
        "launching, no transformations, no tiny objects, max 2 characters, max 3 large props, slow simple motions); "
        "the two 8-second shots connect seamlessly\n"
        "- originality: clearly different from every story listed above (different animal AND different idea)\n"
        "- charm: cute, warm, a small funny moment, parents would happily show it\n\n"
        'Answer as JSON: {"scores": {"logic": n, "clarity": n, "lesson": n, "filmable": n, "originality": n, '
        '"charm": n}, "problems": ["concrete problem 1", ...], "fix": "concrete instructions how to rewrite it"}'
    )
    r = gemini.text_json(prompt, CRITIC_SYSTEM, temperature=0.2, model=config.CRITIC_MODEL)
    scores = {k: int(v) for k, v in (r.get("scores") or {}).items()}
    r["scores"] = scores
    r["min_score"] = min(scores.values()) if scores else 0
    r["passed"] = bool(scores) and r["min_score"] >= config.STORY_MIN_SCORE
    return r


def create(history: list[dict], used_titles: list[str], theme: str | None = None, combos: int = 3,
           rounds: int = 3, log=print) -> dict:
    """Bis zu `combos` Tier×Lektion-Kombinationen mit je `rounds` Überarbeitungen; die erste bestandene Story gewinnt,
    sonst die beste mit Mindestnote ≥ Grenze−1."""
    best, best_score, last_err = None, -1, None
    tried: set[str] = set()
    for _ in range(combos):
        for _ in range(10):
            species, lesson = pick(history, used_titles)
            if species not in tried:
                break
        tried.add(species)
        if theme:
            lesson = theme
        log(f"Heute: {species} × „{lesson}“")
        st, score, err = _write(species, lesson, history, rounds, log)
        if st is not None and st.get("review", {}).get("passed"):
            return st
        last_err = err or last_err
        if st is not None and score > best_score:
            best, best_score = st, score
    if best is not None and best_score >= config.STORY_MIN_SCORE - 1:
        best["review"]["note"] = f"beste Fassung (Mindestnote {best_score})"
        return best
    raise RuntimeError(f"Keine Story hat die Prüfung bestanden (beste Mindestnote {best_score}). {last_err or ''}")


def _write(species: str, lesson: str, history: list[dict], rounds: int, log) -> tuple[dict | None, int, Exception | None]:
    base = (
        f"Main character: a {species}.\n"
        f"Lesson / learning goal: {lesson}.\n\n"
        f"Stories already published (do NOT reuse their animal, plot or idea):\n{_history_text(history)}\n\n"
        f"Write a completely NEW story as JSON with exactly this schema (same keys, English values):\n"
        f"{json.dumps(SCHEMA, indent=1)}\n\n"
        f"SOUND LIBRARY (only these keys are allowed in sfx_cues; choose 4–7 cues that match the action exactly, "
        f"e.g. footsteps while walking, 'idea' when the solution comes, 'tada' or 'sparkle' at the happy end; at "
        f"least one cute animal sound; at least 1 s between cues):\n"
        f"{json.dumps(sfx_library.available(), indent=1)}\n\n"
        "Rules: 2 shots × 8 seconds that together tell the 4 beats. Shot 2 starts exactly where shot 1 ends (same "
        "place, same props, same character position). Sounds are cartoon SFX and little animal noises only (squeaks, "
        "giggles, soft taps, a happy 'ta-da' chime) – never words, never grunts or babbling. The setting is bright and colorful. "
        "Title: emotion + animal + what happens, one emoji, ends with #shorts. Description: line 1 = the story in "
        "one sentence, line 2 = what children learn, then 6–10 search phrases parents use, then hashtags.\n\n"
        "A strict reviewer will score your story 1–10 on: logic, clarity (understandable without words for a "
        "2-year-old), lesson (clearly visible at the end), filmable (only slow, simple, large motions; nothing rolls "
        "far, falls, flies, splashes or changes shape; max 3 big props; the same props in both shots), originality "
        "and charm. Everything below 8 is rejected – check your draft against this list before answering."
    )
    best, best_score, feedback, last_err = None, -1, "", None
    for i in range(rounds):
        prompt = base + (f"\n\nYour previous draft was rejected by the reviewer:\n{feedback}\n"
                         "Write a NEW, better story that fixes every problem." if feedback else "")
        try:
            st = _sanitize(gemini.text_json(prompt, SYSTEM, temperature=0.9))
            st["lesson"] = st.get("lesson") or lesson
            rv = review(st, history)
        except Exception as e:  # noqa: BLE001
            last_err = e
            feedback = f"Technical problem: {e}. Answer with valid JSON matching the schema."
            continue
        st["review"] = {"round": i + 1, "scores": rv["scores"], "problems": rv.get("problems", []),
                        "passed": rv["passed"]}
        log(f"Story-Prüfung Runde {i + 1}: {st['summary'][:110]} | Noten {rv['scores']} → "
            f"{'bestanden' if rv['passed'] else 'abgelehnt'}")
        if rv["passed"]:
            return st, rv["min_score"], None
        if rv["min_score"] > best_score:
            best, best_score = st, rv["min_score"]
        feedback = "Problems: " + "; ".join(rv.get("problems", [])) + "\nHow to fix: " + str(rv.get("fix", ""))
    return best, best_score, last_err


def _cast(story: dict) -> str:
    c = story["character"]
    friend = f" Together with a friend: {story['friend']}." if story.get("friend") else ""
    return f"{c['name']} the {c['species']} ({c['look']}).{friend}"


def character_sheet_prompt(story: dict) -> str:
    c = story["character"]
    return (f"Character design sheet of {c['name']}, a {c['species']}: {c['look']}. Three views side by side "
            f"(front, three-quarter, side), soft pastel gradient background, full body, cheerful expression. "
            f"{config.STYLE_BIBLE}")


def keyframe_prompt(story: dict, shot_idx: int) -> str:
    shot = story["shots"][shot_idx]
    moment = shot["action"] if shot_idx == 0 else shot["ends_with"]
    return (f"{_cast(story)} Place: {story['setting']}. First moment of this scene: {moment}. "
            f"All characters fully visible, centered, camera at child eye level, props clearly visible. "
            f"{config.STYLE_BIBLE}")


def veo_prompt(story: dict, shot_idx: int) -> str:
    shot = story["shots"][shot_idx]
    return (f"Pixar-style 3D animation for toddlers. {_cast(story)} Place: {story['setting']}. "
            f"Story: {story['summary']} This shot: {shot['action']} Ends with: {shot['ends_with']}. "
            f"Audio: {shot['sounds']} – cute cartoon sound effects and soft animal noises only, absolutely no speech, "
            f"no words, no singing. Slow, simple, clearly readable motion, stable camera, characters keep exactly "
            f"the same look, correct anatomy for the animal, objects stay solid and do not morph, vivid rich candy "
            f"colors, colorful detailed background, warm light, vertical 9:16, no text on screen.")


def kling_prompt(story: dict) -> str:
    """Ein durchgehender 15-s-Clip: beide Shots als Zeitablauf, ruhige Kamera, keine Schnitte."""
    s1, s2 = story["shots"]
    return (f"Pixar-style 3D animation for toddlers, one continuous shot, no cuts. {_cast(story)} "
            f"Place: {story['setting']}. Story: {story['summary']} "
            f"0–8 s: {s1['action']} 8–15 s: {s2['action']} Ends with: {s2['ends_with']}. "
            f"Slow, simple, clearly readable motion, stable camera at child eye level, characters keep exactly the "
            f"same look, correct anatomy for the animal, objects stay solid and stay in place unless pushed, "
            f"nothing appears or disappears, vivid rich candy colors, colorful detailed background, warm light, "
            f"no text on screen.")


def sfx_prompt(story: dict) -> str:
    s1, s2 = story["shots"]
    return (f"Cute cartoon sound effects for a 15-second toddler animation, no voices, no words, no music. "
            f"First half: {s1['sounds']}. Second half: {s2['sounds']}. Soft, gentle, playful foley.")


def thumbnail_prompt(story: dict) -> str:
    c = story["character"]
    return (f"YouTube thumbnail: close-up of {c['name']} the {c['species']} ({c['look']}) with a huge happy, "
            f"delighted expression, {story['thumbnail_moment']}, {story['setting']}, big sparkling eyes looking at "
            f"the camera, bright and colorful, {config.STYLE_BIBLE}")
