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
    "Slow Gym Beats": {
        "playlist": "gym", "bpm": (70, 90),
        "purposes": ["heavy lifting", "leg day", "push/pull sessions", "late-night gym", "cardio & stairmaster",
                     "warm-up & mobility", "cooldown after the set", "home workout focus"],
        "motifs": ["athletic woman", "athletic man", "gym object close-up (barbell, chalk, chains)",
                   "empty industrial gym", "rain-soaked street run", "boxing gym"],
        "moods": ["dark, heavy, hypnotic", "cold, industrial, focused", "slow, menacing, powerful",
                  "gritty, determined, minimal"],
    },
    "Dark Ambient Spa": {
        "playlist": "chillout", "bpm": (50, 62),
        "purposes": ["massage & wellness", "hot stone ritual", "sauna & steam", "evening bath", "yin yoga & stretching",
                     "breathwork", "meditation", "floating / sensory calm"],
        "motifs": ["spa scene (stones, candles, water)", "steam & dark tiles", "rain on dark glass",
                   "calm woman in spa robe (advertiser-friendly)", "misty forest pool", "zen garden at night"],
        "moods": ["deep, warm, weightless", "dark, slow, healing", "humid, soft, timeless", "still, glowing, serene"],
    },
    "Night Drive Deep Bass": {
        "playlist": "chillout", "bpm": (85, 105),
        "purposes": ["late night driving", "city lights cruise", "highway at 3 a.m.", "rain drive", "coastal night road",
                     "underground parking / tunnel", "night train", "after-hours focus"],
        "motifs": ["car on wet night road", "tunnel lights", "rain on windshield", "city skyline from the road",
                   "coastal road under moon", "woman at the wheel at night (advertiser-friendly)"],
        "moods": ["dark, deep, nocturnal", "nostalgic, smooth, bass-heavy", "cold, cinematic, driving",
                  "moody, hypnotic, late"],
    },
    "Chillout Sleep": {
        "playlist": "chillout", "bpm": (45, 65),
        "purposes": ["fall asleep fast", "study & deep focus", "night forest rest", "rainy night reading",
                     "insomnia relief", "nap reset", "winter night calm", "ocean night drift"],
        "motifs": ["empty bed", "window with night rain", "dark forest with fireflies", "lantern on a dock",
                   "reading nook by candlelight", "night sky over calm water"],
        "moods": ["warm, soft, weightless", "hazy, slow, tender", "cool, misty, quiet", "deep, dreamy, slow"],
    },
}
LIGHTS = {
    "Slow Gym Beats": ["cold moonlight through high windows", "teal neon haze", "harsh single spotlight", "rain and streetlight",
                       "fog with a single warm lamp", "blue hour", "distant city glow"],
    "Dark Ambient Spa": ["candlelight in darkness", "warm ember glow", "steam with teal backlight", "moonlight on water",
                         "single warm lamp in fog", "blue hour"],
    "Night Drive Deep Bass": ["rain and streetlight", "tunnel sodium lights", "teal neon haze", "distant city glow",
                              "cold moonlight", "dashboard glow"],
    "Chillout Sleep": ["cold moonlight", "candlelight in darkness", "warm ember glow", "fog with a single warm lamp",
                       "blue hour", "starlight"],
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
                  "score": round(0.6 * recency + 0.4 * performance, 3)}
    return out


def choose_brief(mem: dict, analytics_rows: list[dict] | None = None, seed: int | None = None,
                 force_genre: str | None = None) -> dict:
    rnd = random.Random(seed if seed is not None else int(date.today().strftime("%Y%m%d")))
    scores = genre_scores(mem, analytics_rows)
    last_genre = (mem.get("mixes") or [{}])[-1].get("genre")
    if force_genre:
        genre = force_genre
    else:
        ranked = sorted(scores.items(), key=lambda kv: kv[1]["score"] + rnd.uniform(0, 0.15), reverse=True)
        ranked = [kv for kv in ranked if kv[0] != last_genre] or ranked   # nie zweimal hintereinander dasselbe Genre
        genre = ranked[0][0]
    g = GENRES[genre]
    same = [m for m in mem.get("mixes", []) if m["genre"] == genre]
    avoid_purpose = {str(m.get("purpose", "")).lower() for m in same[-3:]}
    avoid_motif = _recent(mem, lambda m: (m.get("visual") or {}).get("motif_family"), 4)
    avoid_light = _recent(mem, lambda m: (m.get("visual") or {}).get("light"), 3)
    avoid_mood = {str(m.get("mood", "")).lower() for m in same[-2:]}
    used_bpm = [m["bpm"] for m in same[-3:]]
    lo, hi = g["bpm"]
    candidates = [b for b in range(lo, hi + 1, 2) if all(abs(b - u) >= 4 for u in used_bpm)] or list(range(lo, hi + 1, 2))
    brief = {
        "date": date.today().isoformat(), "genre": genre, "playlist": g["playlist"], "bpm": rnd.choice(candidates),
        "purpose": _pick(g["purposes"], avoid_purpose, rnd), "mood_hint": _pick(g["moods"], avoid_mood, rnd),
        "motif_family": _pick(g["motifs"], avoid_motif, rnd), "light": _pick(LIGHTS[genre], avoid_light, rnd),
        "scores": scores, "last_genre": last_genre,
    }
    return brief


def brief_text(b: dict) -> str:
    return (f"Date: {b['date']}\nGenre: {b['genre']} (playlist: {b['playlist']})\nBPM: {b['bpm']}\n"
            f"Purpose / listening situation: {b['purpose']}\nMood direction: {b['mood_hint']}\n"
            f"Visual motif family: {b['motif_family']}\nLight: {b['light']}\n"
            f"Why this genre now: last mix was {b['last_genre'] or '-'}; genre scores {json.dumps(b['scores'])}")


# ---------------------------------------------------------------- Textmodell

def _gemini_json(prompt: str, model: str, timeout: int = 240) -> dict:
    url = f"{config.GEMINI_BASE}/models/{model}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 1.0}}
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


def validate(c: dict, mem: dict, brief: dict) -> list[str]:
    """Liefert eine Liste von Beanstandungen (leer = ok). Kleine Dinge werden direkt repariert."""
    errs = []
    req = ["album", "genre", "bpm", "mood", "purpose", "sound_design", "tracks", "extra_tracks", "visual", "art_prompt",
           "thumbnail_prompt", "thumbnail_headline", "yt_title", "hook", "intro", "use_line", "cta_question", "hashtags",
           "tags", "ab_titles", "ab_thumbs", "short_overlays", "short_titles", "shorts", "title_de", "teaser_de",
           "pinned_comment"]
    for k in req:
        if k not in c or c[k] in ("", None, [], {}):
            errs.append(f"Feld fehlt: {k}")
    if errs:
        return errs
    c["genre"], c["playlist"], c["bpm"] = brief["genre"], brief["playlist"], int(brief["bpm"])
    c["minutes_per_track"], c["min_minutes"] = 5, config.MIN_MIX_MINUTES
    if c["album"].strip().lower() in memory.used_albums(mem):
        errs.append(f"Album-Name schon verwendet: {c['album']}")
    used = memory.used_track_titles(mem)
    for key, want in (("tracks", config.PLANNED_TRACKS), ("extra_tracks", config.EXTRA_TRACKS)):
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
    if c["tracks"] and c["extra_tracks"] and c["extra_tracks"][0]["title"].lower() < c["tracks"][-1]["title"].lower():
        errs.append("extra_tracks müssen alphabetisch nach dem letzten regulären Track liegen")
    t_len = len(c["yt_title"].replace("{MIN}", "60").replace("{HOURS}", "1 Hour"))
    if t_len > 75:
        errs.append(f"yt_title zu lang ({t_len})")
    if "{MIN}" not in c["yt_title"] and "{HOURS}" not in c["yt_title"]:
        errs.append("yt_title ohne {MIN}/{HOURS}")
    if re.search(r"\b\d{2,3}\s*min", c["yt_title"], re.I) or re.search(r"\b\d{2,3}\s*min", c["hook"], re.I):
        errs.append("feste Minutenzahl in Titel/Hook – {MIN} verwenden")
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
    c["ab_titles"] = [t for t in c["ab_titles"] if len(t.replace("{MIN}", "60").replace("{HOURS}", "1 Hour")) <= 75][:3]
    if len(c["ab_titles"]) < 2:
        errs.append("ab_titles")
    c["ab_thumbs"] = [t for t in c["ab_thumbs"] if _words(t) <= 3][:2]
    c["short_overlays"] = [t for t in c["short_overlays"] if _words(t) <= 4][:2]
    if len(c["short_overlays"]) < 2 or _words(c["thumbnail_headline"]) > 3:
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
