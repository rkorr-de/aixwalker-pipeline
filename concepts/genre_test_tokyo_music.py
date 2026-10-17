"""Musik-Vergleich für Tokyo Quiet Café (Rolf 17.10.2026): je zwei Klangvarianten pro Raum, A und B, zum Gegenhören.
Aufruf (Cloud mit API-Keys): python concepts/genre_test_tokyo_music.py → Drive „GENRE-TEST Tokyo Quiet Café / musik_vergleich“ + Repo concepts/genre-test-tokyo/musik_vergleich/
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import drive, lyria  # noqa: E402

OUT = Path("build/genre-test-tokyo/musik_vergleich")
BASE = ("quiet Tokyo cafe jazz for focused work and deep concentration, 60 BPM, slow and very steady, no drums, no cymbals, "
        "no vocals, no spoken words, no melodic climax, long stretches of near silence between phrases, intimate close-miked, "
        "warm and unobtrusive, Instrumental.")
VARIANTS = {
    "A": "Warm upright bass and felt piano only. Soft, dark, rounded piano tone with the hammers muted, sparse single notes, "
         "bass plays slow long notes, a very quiet room tone, like a hushed Japanese jazz kissa late at night.",
    "B": "Piano trio feel without drums: felt piano, warm walking upright bass at a very slow pace, a barely audible soft "
         "brushed texture, gentle vintage tape warmth, relaxed and calm, like an old vinyl record in a quiet Tokyo cafe.",
}
ROOMS = {"quiet-counter": "low wooden counter, morning espresso, concrete café", "raked-gravel": "tea house, zen garden, long silence",
         "late-window": "night café, dark mellow, neon far away"}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    files = []
    for room, mood in ROOMS.items():
        for v, desc in VARIANTS.items():
            prompt = f"{BASE} Mood: {mood}. {desc} Duration about 2 minutes. High fidelity stereo."
            try:
                files.append(lyria.generate_track(prompt, OUT / f"{room}-{v}.mp3"))
            except Exception as e:  # noqa: BLE001
                print("fehlgeschlagen:", room, v, e)
    repo = Path("concepts/genre-test-tokyo/musik_vergleich")
    repo.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy(f, repo / f.name)
    links = drive.upload_mix_package("GENRE-TEST Tokyo Quiet Café", [], {"musik_vergleich": files})
    for k, v in links.items():
        print(k, v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
