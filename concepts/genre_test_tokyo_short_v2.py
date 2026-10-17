"""Tokyo Work Lounge: Beispiel-Short neu (das erste Bild war eine Collage aus zwei Ansichten).
Aufruf (Cloud mit API-Keys): python concepts/genre_test_tokyo_short_v2.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from PIL import Image  # noqa: E402

import genre_test_tokyo_lounge_v2 as v  # noqa: E402
from pipeline import drive, images  # noqa: E402

REPO = HERE / "genre-test-tokyo-lounge-v2"
OUT = Path("build/short-v2")
SCENE = ("ONE single continuous vertical photograph, not a collage, not a split screen, no stacked images. Portrait view from behind "
         "an office chair in a spacious ultra-modern Tokyo loft at night: in the lower middle of the frame a long slim desk with exactly TWO "
         "modern widescreen coding monitors side by side, both facing the chair and the camera with their screens fully visible, the left "
         "screen a dark-theme code editor with colorful abstract syntax lines, the right a dark dashboard, a slim monitor light bar above; "
         + v.CHAIR + ", seen from behind; behind the desk floor-to-ceiling windows with a warm golden-amber glow of the Tokyo night skyline, no cold blue light, in the "
         "foreground a low designer sofa and a floor lamp, the dark ceiling with a warm cove light fills the top fifth")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    art = images.generate_art(SCENE, "9:16", pro=True, style=v.STYLE.replace("upper third", "upper fifth"), image_size="2K")
    art.save(OUT / "short-bild.png")
    art.convert("RGB").resize((900, 1600)).save(REPO / "bilder" / "short-bild.jpg", quality=88)
    # alle drei Räume neu (Rolf: zwei Coding-Monitore zum Arbeitsplatz gedreht, immer Abend), dann Thumbnails mit Text mittig
    thumbs, bilder = [], [OUT / "short-bild.png"]
    for key, scene in v.ROOMS.items():
        rart = images.generate_art(scene, "16:9", pro=True, style=v.STYLE, image_size="2K")
        rart.save(OUT / f"{key}.png")
        bilder.append(OUT / f"{key}.png")
        rart.convert("RGB").resize((1600, 900)).save(REPO / "bilder" / f"{key}.jpg", quality=88)
        thumbs.append(v.make_thumb(rart, REPO / "thumbs" / f"thumb-{key}.jpg"))
    sw, sh = 1080, 1920
    v.text_layer(sw, sh, 0.07, 0.036, 0.0165, 0.0125).save(OUT / "text.png")
    images._cover_crop(art, sw, sh).convert("RGB").save(OUT / "basis.png")
    vid = OUT / "short-beispiel.mp4"
    song = REPO / "musik" / "Lounge Song 1.mp3"
    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-t", "25", "-i", str(OUT / "basis.png"),
                    "-loop", "1", "-t", "25", "-i", str(OUT / "text.png"), "-ss", "15", "-t", "25", "-i", str(song),
                    "-filter_complex",
                    "[0:v]scale=2160:-2,zoompan=z='1+0.0004*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=25[v];"
                    "[v][1:v]overlay=0:0,format=yuv420p[vo];[2:a]afade=t=in:d=2,afade=t=out:st=22:d=3[ao]",
                    "-map", "[vo]", "-map", "[ao]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-c:a", "aac", "-b:a", "192k", "-t", "25", str(vid)], check=True, capture_output=True)
    shutil.copy(vid, REPO / "video" / vid.name)
    links = drive.upload_mix_package("GENRE-TEST Tokyo Work Lounge v2", [], {"video": [vid], "bilder": bilder, "thumbs": thumbs})
    for k, val in links.items():
        print(k, val)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
