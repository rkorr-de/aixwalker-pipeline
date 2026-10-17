"""Tokyo Work Lounge (Rolf 17.10.2026): supermoderne Tokyo-Wohnung als Arbeitsraum zu Hause (Schreibtisch, Laptop, Monitor).
Erzeugt 4 Testbilder + 4 Thumbnails + eine 20-s-Videoprobe (mit Beispielsong 1) und lädt alles nach Drive.
Aufruf (Cloud mit API-Keys): python concepts/genre_test_tokyo_lounge.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from PIL import Image  # noqa: E402

import genre_test_tokyo as g  # noqa: E402
from pipeline import drive, images  # noqa: E402

OUT = Path("build/genre-test-tokyo-lounge")
REPO = Path("concepts/genre-test-tokyo-lounge")
STYLE = (" Photorealistic architectural interior photograph, 16:9, eye level, calm composition with long perspective into the depth, "
         "completely empty of people, warm low amber light pools and hidden cove LED light strips on dark matte surfaces, soft shadows, "
         "ultra-modern contemporary Japanese interior design, sleek designer minimalism with concrete, dark walnut, black stone and "
         "sculptural curved plaster, clean lines, high-end architectural magazine quality, screens are switched off or show only a soft "
         "abstract glow, no readable text, no logos, no watermark.")
BASE = ("A super-modern Tokyo high-rise apartment lounge that is used as a quiet home office: a long minimal desk with a slim "
        "laptop, a large monitor and a sculptural designer lounge chair, a low modular sofa, a floor lamp, one dry branch in a "
        "ceramic vase, ")
ROOMS = {
    "shinjuku-sky-lounge": ("SHINJUKU SKY LOUNGE", "JAZZ FOR WORK & CODING",
        BASE + "floor-to-ceiling windows showing the Tokyo skyline at blue dusk with distant warm city lights, polished concrete floor"),
    "nakameguro-morning-loft": ("NAKAMEGURO MORNING LOFT", "MORNING START JAZZ",
        BASE + "tall slatted wood screens throwing soft morning stripes of light across pale concrete and a tatami-textured rug, a calm "
        "canal with cherry tree branches visible through a wide window, golden light"),
    "azabu-rain-lounge": ("AZABU RAIN LOUNGE", "DEEP FOCUS JAZZ",
        BASE + "a large window with soft rain streaks and blurred city lights, dark walnut wall panels, curved plaster ceiling, "
        "moody warm lamp light, very calm and cozy"),
    "midnight-code-lounge": ("MIDNIGHT CODE LOUNGE", "CODING AFTER DARK",
        BASE + "night view of Tokyo far below with soft neon glow, a dark minimal desk setup with two monitors showing a faint dark "
        "glow, deep blue and amber colors, sculptural arch in the wall, very quiet late-night mood"),
}


def main() -> int:
    for sub in ("bilder", "thumbs", "video"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
        (REPO / sub).mkdir(parents=True, exist_ok=True)
    for key, (title, sub, scene) in ROOMS.items():
        art = images.generate_art(scene, "16:9", pro=True, style=STYLE, image_size="2K")
        art.save(OUT / "bilder" / f"{key}.png")
        art.convert("RGB").resize((1600, 900)).save(REPO / "bilder" / f"{key}.jpg", quality=88)
        g.thumb(art, title, OUT / "thumbs" / f"thumb-{key}.jpg", sub)
        shutil.copy(OUT / "thumbs" / f"thumb-{key}.jpg", REPO / "thumbs" / f"thumb-{key}.jpg")
    try:
        song = HERE / "genre-test-tokyo" / "musik_v3" / "Beispielsong 1.mp3"
        vid = OUT / "video" / "video-probe-lounge.mp4"
        subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(OUT / "bilder" / "shinjuku-sky-lounge.png"), "-i", str(song), "-t", "20",
                        "-vf", "scale=3840:-2,zoompan=z='1+0.0006*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=25,format=yuv420p",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-shortest", str(vid)],
                       check=True, capture_output=True)
        shutil.copy(vid, REPO / "video" / vid.name)
    except Exception as e:  # noqa: BLE001
        print("Video-Probe fehlgeschlagen:", e)
    files = {sub: sorted((OUT / sub).glob("*")) for sub in ("bilder", "thumbs", "video")}
    links = drive.upload_mix_package("GENRE-TEST Tokyo Work Lounge", [], files)
    for k, v in links.items():
        print(k, v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
