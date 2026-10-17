"""Test-Material für das neue Genre «Quiet Rooms» (Rolf 17.10.2026): Testbilder, Test-Thumbnails, Test-Musik, Video-Probe.

Aufruf (Cloud-Umgebung mit API-Keys):  python concepts/genre_test_quiet_rooms.py
Ergebnis: Drive → AIX WALKER Mixe / GENRE-TEST Quiet Rooms (bilder, thumbs, musik, video)
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from pipeline import config, drive, images, lyria  # noqa: E402

OUT = Path("build/genre-test-quiet-rooms")
STYLE = (" Photorealistic architectural interior photograph, 16:9, shot at eye level, calm symmetrical composition with "
         "deep perspective, completely empty of people, warm low amber light pools, soft shadows, matte natural materials, "
         "quiet luxury, premium editorial quality, no text, no logos, no watermark, no signage.")

ROOMS = {
    "provence-atelier": ("PROVENCE ATELIER",
        "Interior of a quiet artist's atelier in Aix-en-Provence at golden hour: hand-troweled lime plaster walls, wide "
        "stone floor, one long oak work table with a single ceramic cup, dried olive branches in a terracotta vase, tall "
        "arched window glowing with soft evening light over lavender fields, a linen jacket on a wooden peg, one small "
        "warm spot light above the table"),
    "milan-reading-room": ("MILAN READING ROOM",
        "Interior of a hushed private reading room in Milan: travertine floor and walls, a very long dark oak table with "
        "one brass reading lamp lit, floor-to-ceiling shelves of books in warm shadow, a tall window with sheer linen "
        "curtain and blue-hour light, a low stool and a pair of leather armchairs, one dry branch in a stone vase"),
    "lisbon-tile-cafe": ("LISBON TILE CAFÉ",
        "Interior of a tiny quiet café in Lisbon before opening: pale blue and white hand-painted azulejo tiles on the "
        "lower wall, matte cream plaster above, a short marble counter with a vintage espresso machine, two low wooden "
        "stools, an arched doorway with soft morning light, one small ceramic vase with a dry branch, warm pendant light"),
}
VARIANT = ("provence-atelier-dusk", "PROVENCE ATELIER",
           "Same style of quiet Provençal artist's atelier at blue hour: lime plaster walls, stone floor, long oak table "
           "with one lit candle and a ceramic cup, arched window with deep blue twilight, dried olive branch in a "
           "terracotta vase, warm single spot light, very calm")

TRACKS = {
    "provence-atelier": ("Quiet Atelier", "felt piano, warm upright bass, soft nylon guitar, brushed shaker barely audible"),
    "milan-reading-room": ("Reading Room", "felt piano and warm upright bass, soft vibraphone, long gaps of silence"),
    "lisbon-tile-cafe": ("Tile Café", "soft nylon guitar, warm upright bass, felt piano, gentle brushed texture, subtle bossa feel"),
}


def thumb(art: Image.Image, title: str, out: Path, sub: str = "@AIXWALKER", w: int = 1280, h: int = 720) -> Path:
    img = images._cover_crop(art, w, h).convert("RGB")
    # sanfter Verlauf in der Mitte, damit die dünne Schrift lesbar bleibt
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    for y in range(h):
        a = int(105 * max(0.0, 1 - abs(y - h * 0.5) / (h * 0.30)))
        d.line([(0, y), (w, y)], fill=(12, 8, 4, a))
    img = Image.alpha_composite(img.convert("RGBA"), over).convert("RGB")
    d = ImageDraw.Draw(img)
    font = images._font(config.ASSETS / "fonts" / "Cinzel.ttf", int(h * 0.088), "Regular")
    track = int(h * 0.030)
    tw = images._tracked_width(d, title, font, track)
    images._draw_tracked(d, ((w - tw) // 2, int(h * 0.44)), title, font, (244, 235, 218), track)
    sfont = images._font(config.ASSETS / "fonts" / "Cinzel.ttf", int(h * 0.030), "Regular")
    stw = images._tracked_width(d, sub, sfont, int(h * 0.012))
    images._draw_tracked(d, ((w - stw) // 2, int(h * 0.44) + int(h * 0.13)), sub, sfont, (214, 196, 170), int(h * 0.012))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=92)
    return out


def main() -> int:
    for sub in ("bilder", "thumbs", "musik", "video"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    arts = {}
    for key, (title, scene) in ROOMS.items():
        art = images.generate_art(scene, "16:9", pro=True, style=STYLE, image_size="2K")
        art.save(OUT / "bilder" / f"{key}.png")
        arts[key] = (title, art)
    vkey, vtitle, vscene = VARIANT
    vart = images.generate_art(vscene, "16:9", pro=True, style=STYLE, image_size="2K")
    vart.save(OUT / "bilder" / f"{vkey}.png")
    arts[vkey] = (vtitle, vart)

    for key, (title, art) in arts.items():
        thumb(art, title, OUT / "thumbs" / f"thumb-{key}.jpg")

    mp3s = []
    for key, (name, instr) in TRACKS.items():
        prompt = lyria.build_prompt("quiet focus cafe jazz for deep work", 60,
                                    "calm, warm, unobtrusive, spacious, intimate",
                                    f"{instr}; no drums, no cymbals, no vocals, no melodic climax, very steady and gentle, "
                                    "long stretches of near silence between phrases",
                                    minutes=2)
        try:
            p = lyria.generate_track(prompt, OUT / "musik" / f"{name}.mp3")
            mp3s.append((key, p))
        except Exception as e:  # noqa: BLE001
            print("Musik fehlgeschlagen:", name, e)

    # Video-Probe: 20 s langsamer Zoom (Ken Burns) auf das Provence-Bild mit dem ersten Track
    try:
        key, mp3 = mp3s[0]
        img = OUT / "bilder" / f"{key}.png"
        vid = OUT / "video" / "video-probe-provence.mp4"
        subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-i", str(mp3), "-t", "20",
                        "-vf", "scale=3840:-2,zoompan=z='1+0.0006*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=25,format=yuv420p",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-shortest", str(vid)],
                       check=True, capture_output=True)
    except Exception as e:  # noqa: BLE001
        print("Video-Probe fehlgeschlagen:", e)

    files_by_sub = {sub: sorted((OUT / sub).glob("*")) for sub in ("bilder", "thumbs", "musik", "video")}
    links = drive.upload_mix_package("GENRE-TEST Quiet Rooms", [], files_by_sub)
    for k, v in links.items():
        print(k, v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
