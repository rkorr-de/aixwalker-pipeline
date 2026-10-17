"""Tokyo Work Lounge v2 (Rolf 17.10.2026 21:00): weite Loft-Ansicht, Eames-Stuhl (cognac) am Schreibtisch, fester Thumbnail-Text oben,
2 neue Testsongs (Rolfs Prompt unverändert), 3 Test-Thumbs, 1 Beispiel-Short (9:16).
Aufruf (Cloud mit API-Keys): python concepts/genre_test_tokyo_lounge_v2.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from PIL import Image, ImageDraw  # noqa: E402

from pipeline import config, drive, images, lyria  # noqa: E402

OUT = Path("build/genre-test-tokyo-lounge-v2")
REPO = Path("concepts/genre-test-tokyo-lounge-v2")
LINE1, LINE2, LINE3 = "TOKYO WORK LOUNGE", "SLOW JAZZ FOR WORK AND CODING", "AIX WALKER"

PROMPT = ("Audiophile high-fidelity recording, crystal clear pristine instrument separation, wide stereo imaging. Ultra-quiet and "
          "intensely intimate modern chillhop and Tokyo cafe jazz fusion. Extremely sparse, minimalist, and low volume arrangement "
          "with high dynamic range. The main focus is an exquisitely soft, breathy, and gentle tenor saxophone that borders on a "
          "whisper, mixed cleanly with no muddy frequencies, completely avoiding any harshness. Very minimal accompaniment: highly "
          "isolated single notes on a felt piano, a distinct deep warm sub-bass, and a modern, slow lo-fi drum groove with a muffled "
          "kick and soft dry rimshot. The mix is completely dry with almost zero reverb, distinct discrete panning for each "
          "instrument, creating a very close, private, and late-night aesthetic. Deep focus, soothing background music, strictly "
          "instrumental, no vocals, master-quality audio.")

CHAIR = ("at the desk stands a sleek Vitra Eames EA 117 aluminum office chair in dark leather with cognac-colored leather "
         "upholstery and polished aluminum frame, clearly visible and realistic")
BASE = ("A wide, spacious ultra-modern Tokyo loft apartment seen from a wide-angle eye-level view: a large open-plan living area "
        "with a low modular designer sofa, a sculptural floor lamp, a dry branch in a ceramic vase and a rug, and further in the room "
        "a stylish realistic home-office zone with a long slim minimal desk, a large monitor and a slim laptop, " + CHAIR + ". "
        "The whole loft is visible, the work area is part of the room and not the only subject. ")
STYLE = (" Photorealistic architectural interior photograph, calm composition with long perspective, completely empty of people, "
         "warm low amber light pools and hidden cove LED strips on dark matte surfaces, ultra-modern contemporary Japanese loft "
         "design with concrete, dark walnut, black stone and sculptural curved plaster, high-end architectural magazine quality, "
         "always an evening or night scene with dark sky and artificial warm light, never daylight, no sunshine, no morning light, "
         "realistic proportions and materials, the upper third of the image is a calm dark ceiling or wall area, screens switched "
         "off or with only a soft abstract glow, no readable text, no logos, no watermark.")
ROOMS = {
    "shinjuku-sky-loft": BASE + "floor-to-ceiling windows showing the Tokyo skyline at blue dusk with distant warm city lights, polished concrete floor",
    "nakameguro-evening-loft": BASE + "tall slatted wood screens lit from behind by warm lamps, a calm canal with cherry blossom branches lit by soft lanterns visible through a wide window in the dark blue evening, deep dusk sky, polished pale concrete floor, warm amber interior light",
    "azabu-rain-loft": BASE + "a very large window with soft rain streaks and blurred city lights, dark walnut wall panels, curved plaster ceiling, moody warm lamp light",
}
SHORT_SCENE = ("Vertical composition: a spacious ultra-modern Tokyo loft apartment at night, the home-office zone in the middle of the "
               "image with a long slim desk, a large monitor, a slim laptop and, " + CHAIR + ", behind it floor-to-ceiling windows with "
               "the Tokyo skyline in deep blue and amber, in the foreground a low designer sofa and a floor lamp, whole loft visible")


def _tracked_fit(d, text, path, size, tr_ratio, max_w):
    f = images._font(path, size, "Regular")
    tr = int(size * tr_ratio)
    while images._tracked_width(d, text, f, tr) > max_w and size > 10:
        size -= 2
        f = images._font(path, size, "Regular")
        tr = int(size * tr_ratio)
    return f, tr


def text_layer(w: int, h: int, top: float, s1: float, s2: float, s3: float) -> Image.Image:
    """Transparente Ebene: dunkler Verlauf oben + drei zentrierte Zeilen (heller als vorher). Größen relativ zur Höhe."""
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    band = h * (top + 0.28)
    for y in range(int(band)):
        d.line([(0, y), (w, y)], fill=(10, 6, 3, int(190 * (1 - y / band) ** 1.2)))
    F = config.ASSETS / "fonts" / "Cinzel.ttf"
    y = int(h * top)
    for text, rel, col, tr_ratio in ((LINE1, s1, (255, 252, 244), 0.30), (LINE2, s2, (255, 232, 185), 0.20),
                                     (LINE3, s3, (255, 244, 225), 0.30)):
        f, tr = _tracked_fit(d, text, F, int(h * rel), tr_ratio, w * 0.90)
        tw = images._tracked_width(d, text, f, tr)
        images._draw_tracked(d, ((w - tw) // 2, y), text, f, col, tr)
        y += int(f.size * 1.75)
    return lay


def make_thumb(art: Image.Image, out: Path, w: int = 1280, h: int = 720) -> Path:
    img = images._cover_crop(art, w, h).convert("RGBA")
    img = Image.alpha_composite(img, text_layer(w, h, 0.05, 0.085, 0.043, 0.032)).convert("RGB")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=92)
    return out


def main() -> int:
    for sub in ("bilder", "thumbs", "musik", "video"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
        (REPO / sub).mkdir(parents=True, exist_ok=True)
    for key, scene in ROOMS.items():
        art = images.generate_art(scene, "16:9", pro=True, style=STYLE, image_size="2K")
        art.save(OUT / "bilder" / f"{key}.png")
        art.convert("RGB").resize((1600, 900)).save(REPO / "bilder" / f"{key}.jpg", quality=88)
        t = make_thumb(art, OUT / "thumbs" / f"thumb-{key}.jpg")
        shutil.copy(t, REPO / "thumbs" / t.name)

    songs = []
    for n in ("Lounge Song 1", "Lounge Song 2"):
        try:
            p = lyria.generate_track(PROMPT, OUT / "musik" / f"{n}.mp3")
            songs.append(p)
            shutil.copy(p, REPO / "musik" / p.name)
        except Exception as e:  # noqa: BLE001
            print("Musik fehlgeschlagen:", n, e)

    # Beispiel-Short 9:16, ca. 25 s: langsamer Zoom, Text oben als feste Ebene, Ausschnitt aus Song 1 mit Ein-/Ausblendung
    try:
        sart = images.generate_art(SHORT_SCENE, "9:16", pro=True, style=STYLE.replace("upper third", "upper fifth"), image_size="2K")
        sart.save(OUT / "bilder" / "short-bild.png")
        sart.convert("RGB").resize((900, 1600)).save(REPO / "bilder" / "short-bild.jpg", quality=88)
        sw, sh = 1080, 1920
        text_layer(sw, sh, 0.07, 0.036, 0.0165, 0.0125).save(OUT / "video" / "short-text.png")
        base = images._cover_crop(sart, sw, sh).convert("RGB")
        base.save(OUT / "video" / "short-basis.png")
        vid = OUT / "video" / "short-beispiel.mp4"
        subprocess.run(["ffmpeg", "-y", "-loop", "1", "-t", "25", "-i", str(OUT / "video" / "short-basis.png"),
                        "-loop", "1", "-t", "25", "-i", str(OUT / "video" / "short-text.png"),
                        "-ss", "15", "-t", "25", "-i", str(songs[0]),
                        "-filter_complex",
                        "[0:v]scale=2160:-2,zoompan=z='1+0.0004*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=25[v];"
                        "[v][1:v]overlay=0:0,format=yuv420p[vo];[2:a]afade=t=in:d=2,afade=t=out:st=22:d=3[ao]",
                        "-map", "[vo]", "-map", "[ao]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-c:a", "aac", "-b:a", "192k", "-t", "25", str(vid)], check=True, capture_output=True)
        shutil.copy(vid, REPO / "video" / vid.name)
    except Exception as e:  # noqa: BLE001
        print("Short fehlgeschlagen:", e)

    files = {sub: sorted(f for f in (OUT / sub).glob("*") if f.name not in ("short-text.png", "short-basis.png"))
             for sub in ("bilder", "thumbs", "musik", "video")}
    links = drive.upload_mix_package("GENRE-TEST Tokyo Work Lounge v2", [], files)
    for k, v in links.items():
        print(k, v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
