"""Tokyo Quiet Café: Musik mit Rolfs eigenem Lyria-Prompt (17.10.2026, unverändert), 4 Stücke.
Aufruf (Cloud mit API-Keys): python concepts/genre_test_tokyo_music_rolf.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import drive, lyria  # noqa: E402

PROMPT = ("Instrumental smooth Tokyo cafe jazz. Very slow tempo, late-night atmospheric chillout vibe. The lead instrument is a "
          "soft, breathy tenor saxophone playing very slow, soothing, and relaxing melodies. The accompaniment is minimal: sparse "
          "warm felt piano chords, a deep upright bass, and gentle brushed snare drums. Intimate, quiet room acoustics, deep focus "
          "aesthetic, highly relaxing background music. No vocals, strictly instrumental.")
OUT = Path("build/genre-test-tokyo/musik_rolf")
NAMES = ["Quiet Counter", "Raked Gravel", "Seven Oclock", "Late Window"]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    files = []
    for i, n in enumerate(NAMES, 1):
        try:
            files.append(lyria.generate_track(PROMPT + " Duration about 2 minutes.", OUT / f"{i}-{n}.mp3"))
        except Exception as e:  # noqa: BLE001
            print("fehlgeschlagen:", n, e)
    repo = Path("concepts/genre-test-tokyo/musik_rolf")
    repo.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy(f, repo / f.name)
    links = drive.upload_mix_package("GENRE-TEST Tokyo Quiet Café", [], {"musik_rolf_prompt": files})
    for k, v in links.items():
        print(k, v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
