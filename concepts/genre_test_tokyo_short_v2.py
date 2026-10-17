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
SCENE = ("ONE single continuous vertical photograph, not a collage, not a split screen, no stacked images. A spacious ultra-modern "
         "Tokyo loft apartment at night seen from eye level in portrait format: in the lower middle of the frame a long slim desk with a "
         "large monitor and a slim laptop, " + v.CHAIR + ", behind the desk floor-to-ceiling windows with the Tokyo skyline in deep blue "
         "and amber, in the foreground a low designer sofa and a floor lamp, the dark ceiling with a warm cove light fills the top fifth")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    art = images.generate_art(SCENE, "9:16", pro=True, style=v.STYLE.replace("upper third", "upper fifth"), image_size="2K")
    art.save(OUT / "short-bild.png")
    art.convert("RGB").resize((900, 1600)).save(REPO / "bilder" / "short-bild.jpg", quality=88)
    # Nakameguro als Abendszene neu (Rolf: immer Abend, kein Tageslicht)
    nart = images.generate_art(v.ROOMS["nakameguro-evening-loft"], "16:9", pro=True, style=v.STYLE, image_size="2K")
    nart.save(OUT / "nakameguro-evening-loft.png")
    nart.convert("RGB").resize((1600, 900)).save(REPO / "bilder" / "nakameguro-evening-loft.jpg", quality=88)
    nth = v.make_thumb(nart, REPO / "thumbs" / "thumb-nakameguro-evening-loft.jpg")
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
    links = drive.upload_mix_package("GENRE-TEST Tokyo Work Lounge v2", [], {"video": [vid], "bilder": [OUT / "short-bild.png", OUT / "nakameguro-evening-loft.png"], "thumbs": [nth]})
    for k, val in links.items():
        print(k, val)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
