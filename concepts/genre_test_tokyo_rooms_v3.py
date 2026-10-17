"""Tokyo Work Lounge v3 (Rolf 17.10.2026 22:21): gemütlicher Raum, 2-3 Pflanzen, Designer-Schreibtischlampe, japanische Teetasse,
Schreibtisch wie gerade verlassen, unscharfe Person am Fenster, Arbeitsplatz NICHT mittig. 3 Bilder + 3 Thumbnails (Text mittig, wie v2).
Aufruf (Cloud mit API-Keys): python concepts/genre_test_tokyo_rooms_v3.py
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import genre_test_tokyo_lounge_v2 as v  # noqa: E402
from pipeline import drive, images  # noqa: E402

OUT = Path("build/tokyo-rooms-v3")
REPO = HERE / "genre-test-tokyo-lounge-v3"

STYLE = (" Photorealistic architectural interior photograph, calm composition with long perspective, warm and cozy atmosphere, "
         "overall warm candle-like amber and golden light around 2700K, warm light pools and hidden warm cove LED strips on dark matte "
         "surfaces, absolutely no cold blue light and no blue tint, ultra-modern contemporary Japanese loft design with concrete, dark "
         "walnut, black stone and sculptural curved plaster, high-end architectural magazine quality, always an evening or night scene "
         "with artificial warm light, never daylight, realistic proportions and materials, the monitors glow softly with abstract "
         "dark-theme code that is not readable, the person in the background is strongly out of focus with shallow depth of field and "
         "not recognizable in detail, no readable text, no logos, no watermark.")

DESK = ("The home-office zone is only a part of the picture and sits in the {side} third of the frame, NOT in the center: a long slim "
        "designer desk with exactly TWO modern widescreen coding monitors side by side, both turned toward the chair so the screens are "
        "visible, a slim monitor light bar, a modern designer desk lamp with a warm glow, a modern handleless Japanese yunomi tea cup "
        "with green tea and a little steam, a small notebook and a pen, the desk looks as if its user has just stepped away: " + v.CHAIR +
        ", pushed back a little and slightly turned away from the desk. ")
COZY = ("The loft is cozy and inviting: two or three lush green indoor plants (for example a leafy plant in a ceramic pot and a small "
        "bonsai), a soft wool throw on a low modular designer sofa, a warm textured rug, a wooden shelf with a few books and a ceramic vase. ")
PERSON = {
    "woman": "In the background by the large window, strongly blurred, stands a modern Asian businesswoman in elegant smart casual clothes, seen from behind at three-quarter angle, holding a tea cup and looking out of the window during her work break. ",
    "man": "In the background by the large window, strongly blurred, stands a modern Western European man in a relaxed dark sweater, seen from behind at three-quarter angle, holding a tea cup and looking out of the window during his work break. ",
}
INTRO = "A wide, spacious ultra-modern Tokyo loft apartment photographed from a wide-angle eye-level view. "

ROOMS = {
    "shinjuku-sky-loft": INTRO + DESK.format(side="left") + COZY + PERSON["woman"] +
        "Floor-to-ceiling windows show the Tokyo night skyline with warm golden-amber city lights, no blue sky.",
    "nakameguro-evening-loft": INTRO + DESK.format(side="right") + COZY + PERSON["man"] +
        "A wide window shows a calm canal with cherry blossom branches lit by soft amber lanterns at night, slatted wood screens lit from behind by warm lamps.",
    "azabu-rain-loft": INTRO + DESK.format(side="left") + COZY + PERSON["woman"] +
        "A very large window with soft rain streaks and blurred warm amber and golden city lights, dark walnut wall panels, curved plaster ceiling.",
}


def main() -> int:
    for sub in ("bilder", "thumbs"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
        (REPO / sub).mkdir(parents=True, exist_ok=True)
    pngs, thumbs = [], []
    for key, scene in ROOMS.items():
        art = images.generate_art(scene, "16:9", pro=True, style=STYLE, image_size="2K")
        art.save(OUT / "bilder" / f"{key}.png")
        pngs.append(OUT / "bilder" / f"{key}.png")
        art.convert("RGB").resize((1600, 900)).save(REPO / "bilder" / f"{key}.jpg", quality=88)
        thumbs.append(v.make_thumb(art, REPO / "thumbs" / f"thumb-{key}.jpg"))
        shutil.copy(thumbs[-1], OUT / "thumbs" / thumbs[-1].name)
    links = drive.upload_mix_package("GENRE-TEST Tokyo Work Lounge v3", [], {"bilder": pngs, "thumbs": thumbs})
    for k, val in links.items():
        print(k, val)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
