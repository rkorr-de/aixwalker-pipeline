"""Ersetzt bei einem Tokyo-Mix den Einleitungstext (alles vor „Chapters“) und den Schlusssatz durch neue Texte.

Aufruf:  python set_tokyo_description.py <video_id> <intro-datei> [<schluss-datei>]
Kapitel, Musik-/KI-Hinweis und Hashtags der bestehenden Beschreibung bleiben unverändert.
"""
import re
import sys
from pathlib import Path

from pipeline import youtube


def main() -> None:
    vid, intro = sys.argv[1], Path(sys.argv[2]).read_text(encoding="utf-8").strip()
    outro = Path(sys.argv[3]).read_text(encoding="utf-8").strip() if len(sys.argv) > 3 else ""
    old = youtube.get_description(vid)
    head, sep, rest = old.partition("\nChapters\n")
    if not sep:
        raise SystemExit("Beschreibung enthält keinen Abschnitt „Chapters“ – nichts geändert.")
    m = re.search(r"\n\nWell done[^\n]*\n\n", rest)
    chapters = rest[:m.start()] if m else rest.split("\n\nMusic by")[0]
    tail = rest[rest.index("Music by"):] if "Music by" in rest else ""
    new = f"{intro}\n\nChapters\n{chapters}\n\n" + (f"{outro}\n\n" if outro else "") + tail
    youtube.set_description(vid, new)
    print("Beschreibung aktualisiert:", len(new), "Zeichen")


if __name__ == "__main__":
    main()
