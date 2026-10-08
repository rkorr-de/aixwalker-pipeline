#!/usr/bin/env python3
"""Setzt Kanalbeschreibung und Kanal-Keywords aus channel/description.txt und channel/keywords.txt.

    python set_channel_description.py          # nur anzeigen (Probelauf)
    python set_channel_description.py --apply  # wirklich setzen

Alle anderen brandingSettings (Titel, Land, Trailer …) bleiben erhalten.
"""
import sys
from pathlib import Path

from pipeline import youtube

ROOT = Path(__file__).parent


def main() -> int:
    desc = (ROOT / "channel" / "description.txt").read_text(encoding="utf-8").strip()
    kw = (ROOT / "channel" / "keywords.txt").read_text(encoding="utf-8").strip()
    yt = youtube.service()
    ch = yt.channels().list(part="brandingSettings", mine=True).execute()["items"][0]
    bs = ch["brandingSettings"]
    old = bs.get("channel", {})
    print("VORHER Beschreibung:\n" + old.get("description", "") + "\n")
    print("VORHER Keywords: " + old.get("keywords", "") + "\n")
    if "--apply" not in sys.argv:
        print("Probelauf – nichts geändert. Neu wäre:\n" + desc + "\n\n" + kw)
        return 0
    bs.setdefault("channel", {})["description"] = desc
    bs["channel"]["keywords"] = kw
    bs.pop("image", None)  # veraltetes Feld, wird von der API abgelehnt
    yt.channels().update(part="brandingSettings", body={"id": ch["id"], "brandingSettings": bs}).execute()
    new = yt.channels().list(part="brandingSettings", mine=True).execute()["items"][0]["brandingSettings"]["channel"]
    print("NACHHER Beschreibung:\n" + new.get("description", "") + "\n")
    print("NACHHER Keywords: " + new.get("keywords", ""))
    ok = new.get("description", "").strip() == desc
    print("ERGEBNIS: " + ("OK – Beschreibung gesetzt" if ok else "FEHLER – Beschreibung weicht ab"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
