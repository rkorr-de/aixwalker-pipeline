#!/usr/bin/env python3
"""YOIN Rooms Songtest 3 (Rolf 29.10.2026): Track 3 aus Test 2 war am besten, Sax zu hell/vordergründig, Stimmung zu traurig.

Heiter-warm in Dur, ca. 64 BPM, Vibraphon als Hauptmelodie; Bläser (Bassklarinette / Tenorsax weit weg) oder ganz ohne.
Nutzt Erzeugung, Mastering und Prüfung aus yoin_songtest.py und misst zusätzlich Spektralschwerpunkt und Pegel.

  python scripts/yoin_songtest3.py --out build/yoin_test3
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yoin_songtest as t  # noqa: E402

t.BASE_PROMPT = (
    "Relaxed, gently happy and warm Tokyo café jazz for deep work, like a sunny quiet morning in a small café. Smooth, mellow and "
    "cozy, easy and pleasant to listen to, with a simple, friendly, hummable melody that is never boring. Major key, bright and "
    "optimistic harmony, rich jazz chords (major 7th, 6th, 9th), no minor melancholy, no sad or wistful mood. Tempo around 64 BPM, "
    "relaxed light swing, soft and smiling. Soft vibraphone plays the main melody in a clear, warm, rounded tone. Felt piano very "
    "soft and sparse, light touch, never leading. Warm upright bass played gently with a light bouncy walking feel. Clean, warm, "
    "close studio recording, no reverb wash, no lo-fi vinyl crackle. No drums, no percussion, no guitar, no synths, no vocals. "
    "Instrumental only."
)
t.TRACKS = [
    ("01_vibes_bass_clarinet", "A very soft, dark and woody bass clarinet in its low register adds a few warm, long background "
                               "notes between the vibraphone phrases; it is quiet, round and never bright, never in the foreground."),
    ("02_vibes_sax_far", "A mellow tenor saxophone appears only now and then, far away in the background, very quiet and dark, "
                         "with a rounded velvety tone, no bright or sharp overtones, like a distant echo behind the vibraphone."),
    ("03_vibes_no_sax", "No saxophone and no wind instruments at all. Only vibraphone, soft piano and upright bass, with a touch "
                        "of warm Rhodes electric piano chords in the background for extra warmth."),
]

if __name__ == "__main__":
    sys.exit(t.main())
