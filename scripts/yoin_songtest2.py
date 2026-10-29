#!/usr/bin/env python3
"""YOIN Rooms Songtest 2 (Rolf 29.10.2026): tieferes, leiseres Baritonsaxophon, Klavier dezent, ca. 58 BPM.

Nutzt Erzeugung, Mastering und Prüfung aus yoin_songtest.py, ersetzt nur Prompts, Dateinamen und Tempo und misst zusätzlich
die Tonhöhenlage (Spektralschwerpunkt) und den Pegel des Saxophon-Bereichs (Sax-Hinweis).

  python scripts/yoin_songtest2.py --out build/yoin_test2
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yoin_songtest as t  # noqa: E402

t.BASE_PROMPT = (
    "Extremely slow, soft and deeply relaxing Tokyo café jazz for deep work. Smooth, warm and mellow, easy and pleasant to listen to, "
    "with a gentle simple melody that is never boring. Tempo around 58 BPM, relaxed swing feel, rich jazz chords (major 7th, 9th), "
    "long sustained notes, plenty of space between phrases. Felt piano played very softly and sparsely, light touch, never loud, "
    "never leading. Warm upright bass played gently. A low, deep baritone saxophone in its lowest register, extremely soft, breathy "
    "and quiet, slow long legato notes, mellow and rounded tone, no sharp or bright overtones, sitting gently in the background. "
    "Clean, warm, close studio recording, no reverb wash, no lo-fi vinyl crackle. No drums, no percussion, no guitar, no synths, "
    "no vocals. Instrumental only."
)
t.TRACKS = [
    ("01_low_sax_piano", "The saxophone and the piano share the gentle melody; the saxophone is barely above a whisper, "
                         "the piano plays only a few soft chords."),
    ("02_low_sax_melody", "The low saxophone carries the slow main melody in long, soft phrases; the piano only adds sparse, "
                          "very quiet chords underneath."),
    ("03_rain_vibes", "Late night after the rain. A few very soft vibraphone notes now and then, the low saxophone even quieter "
                      "and deeper, dreamy and calm."),
]

if __name__ == "__main__":
    sys.exit(t.main())
