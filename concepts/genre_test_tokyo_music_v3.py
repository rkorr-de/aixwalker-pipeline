"""Tokyo Quiet Café: 2 Beispielsongs mit Rolfs Lyria-Prompt vom 17.10.2026 20:00 (Prompt unverändert).
Aufruf (Cloud mit API-Keys): python concepts/genre_test_tokyo_music_v3.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import drive, lyria  # noqa: E402

PROMPT = ("Ultra-quiet and intensely intimate modern chillhop and Tokyo cafe jazz fusion. Extremely sparse, minimalist, and low "
          "volume arrangement. The main focus is an exquisitely soft, breathy, and gentle tenor saxophone that borders on a "
          "whisper, completely avoiding any harshness or bright lead qualities. Very minimal accompaniment: only occasional, "
          "highly isolated single notes on a felt piano, a deep warm sub-bass, and a modern, slow lo-fi drum groove with a "
          "muffled kick and soft dry rimshot. The mix is completely dry with almost zero reverb, creating a very close, private, "
          "and late-night aesthetic. Deep focus, soothing background music, strictly instrumental, no vocals.")
OUT = Path("build/genre-test-tokyo/musik_v3")
NAMES = ["Beispielsong 1", "Beispielsong 2"]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    files = []
    for n in NAMES:
        try:
            files.append(lyria.generate_track(PROMPT, OUT / f"{n}.mp3"))
        except Exception as e:  # noqa: BLE001
            print("fehlgeschlagen:", n, e)
    repo = Path("concepts/genre-test-tokyo/musik_v3")
    repo.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy(f, repo / f.name)
    links = drive.upload_mix_package("GENRE-TEST Tokyo Quiet Café", [], {"musik_v3": files})
    for k, v in links.items():
        print(k, v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
