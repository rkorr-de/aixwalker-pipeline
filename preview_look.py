#!/usr/bin/env python3
"""Vorschau des Thumbnail-/Cover-Looks mit echten KI-Bildern, ohne Musik und ohne Upload.

    python preview_look.py --out build/look_preview

Erzeugt je Genre (Lounge, Spa, Sleep): Thumbnail, Album-Cover, Track-Cover und Short-Bild sowie eine Übersicht
`overview.jpg`. Kosten: je Genre 1 Pro-Hauptbild (4K) + 1 Flash-Bild.
"""
import argparse
from pathlib import Path

from PIL import Image

from pipeline import config, images, shorts

SAMPLES = [
    {"genre": "Mediterranean Spa Lounge", "album": "Azure Terrace Spa", "track": "Aegean Breeze", "min": 62,
     "hook": "Sunset on repeat",
     "scene": "Infinity pool above the Mediterranean sea with white lounge beds and a few lanterns, golden-hour sunset "
              "over the water, centered composition with calm open sky in the middle"},
    {"genre": "Dark Ambient Spa", "album": "Golden Stone Ritual", "track": "Amber Steam", "min": 90,
     "hook": "Let the day melt",
     "scene": "Candlelit luxury spa with hot stones, white orchids, folded towels and warm wood, a calm water basin, "
              "centered composition with soft open space in the middle"},
    {"genre": "Chillout Sleep", "album": "Harbor Lullaby", "track": "Quiet Mooring", "min": 184,
     "hook": "Sleep in minutes",
     "scene": "Lantern-lit wooden dock on a calm bay at deep blue dusk, warm village lights reflecting on the water, "
              "first stars, centered composition with open sky in the middle"},
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build/look_preview")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for smp in SAMPLES:
        g, slug = smp["genre"], smp["album"].lower().replace(" ", "-")
        style = images.style_for(g)
        kw = config.THUMB_KEYWORD[g]
        art1 = images.master_art(smp["scene"], g)          # ein Hauptbild für Cover und Thumbnail
        art16 = images.crop_aspect(art1, 16, 9)
        track_art = images.generate_art(smp["scene"] + " Variation: closer detail of the same place.", "1:1", style=style)
        for im, tag in ((art16, "raw16"), (art1, "raw1"), (track_art, "rawtrack")):   # Rohbilder für Text-Tests
            im.convert("RGB").save(out / f"{slug}_{tag}.jpg", "JPEG", quality=90)
        t = images.make_thumbnail(art16, kw, smp["album"], out / f"{slug}_thumbnail.jpg",
                                  duration=images.duration_label(smp["min"]))
        a = images.make_album_cover(art1, kw, smp["album"], out / f"{slug}_album.png")
        c = images.make_track_cover(track_art, smp["track"], 1, smp["album"], out / f"{slug}_track01.png")
        s = shorts.make_short_frame(art16, c, smp["hook"], smp["track"], out / f"{slug}_short.png",
                                    total_min=smp["min"], album=smp["album"], keyword=kw)
        rows.append((t, a, c, s))
        print(f"{g}: {t.name}, {a.name}, {c.name}, {s.name}")
    # Übersicht: je Zeile Thumbnail | Album | Track | Short
    H = 360
    W = 640 + H + H + int(H * 9 / 16) + 50
    sheet = Image.new("RGB", (W, len(rows) * (H + 10) + 10), (24, 24, 24))
    for r, (t, a, c, s) in enumerate(rows):
        y, x = 10 + r * (H + 10), 10
        for p, size in ((t, (640, H)), (a, (H, H)), (c, (H, H)), (s, (int(H * 9 / 16), H))):
            sheet.paste(Image.open(p).convert("RGB").resize(size, Image.LANCZOS), (x, y))
            x += size[0] + 10
    sheet.save(out / "overview.jpg", "JPEG", quality=88)
    print(f"Übersicht: {out / 'overview.jpg'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
