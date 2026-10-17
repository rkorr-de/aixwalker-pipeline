"""Test-Material für das neue Genre «Tokyo Quiet Café» (Rolf 17.10.2026): Testbilder, Test-Thumbnails, Test-Musik, Video-Probe.

Aufruf (Cloud-Umgebung mit API-Keys):  python concepts/genre_test_quiet_rooms.py
Ergebnis: Drive → AIX WALKER Mixe / GENRE-TEST Tokyo Quiet Café (bilder, thumbs, musik, video)
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from pipeline import config, drive, images, lyria  # noqa: E402

OUT = Path("build/genre-test-tokyo")
STYLE = (" Photorealistic architectural interior photograph, 16:9, shot at eye level, calm composition with long perspective "
         "into the depth, completely empty of people, warm low amber light pools and recessed light strips on dark matte surfaces, "
         "soft shadows, ultra-modern contemporary Japanese architecture, sleek designer minimalism with sculptural curved plaster, concrete, stone and dark wood, clean lines, high-end architectural magazine quality, no text, no logos, no watermark, "
         "no signage.")

ROOMS = {
    "tokyo-quiet-cafe": ("TOKYO QUIET CAFÉ",
        "A silent ultra-modern Tokyo specialty café interior designed by a top architect: raw concrete and warm plaster walls, a low long wooden counter with a "
        "small espresso machine behind glass, two low round stools, one old coat hanging on a black hook, a single dried "
        "branch in a clay vase on a stone ledge, large floor-to-ceiling window with soft blue dusk light from the street, "
        "polished concrete floor reflecting warm spot lights"),
    "kyoto-tea-room": ("KYOTO TEA ROOM",
        "A silent Kyoto tea house corridor: dark wood slat walls, paper shoji screens glowing warmly, a raked gravel zen "
        "garden with a moss stone seen through a wide opening, a long low bench, tall pampas grass in a ceramic vase, "
        "recessed warm light strips along the floor, tatami edge, very calm symmetrical perspective"),
    "shibuya-morning-cafe": ("SHIBUYA MORNING CAFÉ",
        "A quiet Tokyo café at 7 in the morning: tall slatted wooden screens throwing dappled sunlight stripes across a "
        "pale concrete floor, a minimalist wooden counter with a pour-over kettle, dark vertical wood panels, a few "
        "low stools, soft haze, one small plant, warm golden light entering from the right, empty and peaceful"),
}
VARIANT = ("night-coding-cafe", "NIGHT CODING CAFÉ",
           "A silent Tokyo café at night for late work: curved plaster arches, dark walnut counter with warm amber pendant "
           "lights, a long low shelf with a single book, a large window showing blurred neon lights of Tokyo far away in "
           "deep blue, polished concrete floor, a dry branch in a vase, very calm moody warm light")

SUBS = {"tokyo-quiet-cafe": "JAZZ FOR WORK & CODING", "kyoto-tea-room": "DEEP FOCUS TEA HOUSE JAZZ",
        "shibuya-morning-cafe": "MORNING START JAZZ", "night-coding-cafe": "CODING AFTER DARK"}

TRACKS = {
    "tokyo-quiet-cafe": ("Quiet Counter", "warm upright bass, felt piano, soft muted brushed texture barely audible, vintage Tokyo jazz kissa warmth"),
    "kyoto-tea-room": ("Raked Gravel", "felt piano and warm upright bass, sparse single notes, long gaps of silence, soft room air"),
    "shibuya-morning-cafe": ("Seven Oclock", "gentle upright bass walking very softly, felt piano, hint of soft vibraphone, light morning warmth"),
    "night-coding-cafe": ("Late Window", "slow felt piano, deep warm upright bass, dark mellow late-night jazz cafe feel, very steady"),
}


def thumb(art: Image.Image, title: str, out: Path, sub: str, w: int = 1280, h: int = 720) -> Path:
    img = art.convert("RGB").resize((w, h), Image.LANCZOS)
    over = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    cy = h * 0.40
    for y in range(h):
        a = int(150 * max(0.0, 1 - abs(y - cy) / (h * 0.26)))
        d.line([(0, y), (w, y)], fill=(14, 9, 5, a))
    img = Image.alpha_composite(img.convert("RGBA"), over).convert("RGB")
    d = ImageDraw.Draw(img)
    F = config.ASSETS / "fonts" / "Cinzel.ttf"
    size = int(h * 0.085)
    f = images._font(F, size, "Regular")
    tr = int(h * 0.028)
    while images._tracked_width(d, title, f, tr) > w * 0.86:
        size -= 2
        f = images._font(F, size, "Regular")
        tr = int(size * 0.33)
    tw = images._tracked_width(d, title, f, tr)
    y0 = int(h * 0.32)
    images._draw_tracked(d, ((w - tw) // 2, y0), title, f, (248, 240, 225), tr)
    sf = images._font(F, int(h * 0.036), "Regular")
    st = int(h * 0.014)
    sw = images._tracked_width(d, sub, sf, st)
    images._draw_tracked(d, ((w - sw) // 2, y0 + int(h * 0.14)), sub, sf, (236, 205, 150), st)
    mf = images._font(F, int(h * 0.026), "Regular")
    m, ms = "AIX WALKER", int(h * 0.012)
    mw = images._tracked_width(d, m, mf, ms)
    images._draw_tracked(d, ((w - mw) // 2, y0 + int(h * 0.22)), m, mf, (214, 196, 170), ms)
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
        thumb(art, title, OUT / "thumbs" / f"thumb-{key}.jpg", SUBS.get(key, "JAZZ FOR WORK & CODING"))

    mp3s = []
    for key, (name, instr) in TRACKS.items():
        prompt = lyria.build_prompt("quiet Tokyo cafe jazz for focused work and deep concentration", 60,
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
        vid = OUT / "video" / "video-probe-tokyo.mp4"
        subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-i", str(mp3), "-t", "20",
                        "-vf", "scale=3840:-2,zoompan=z='1+0.0006*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=25,format=yuv420p",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-shortest", str(vid)],
                       check=True, capture_output=True)
    except Exception as e:  # noqa: BLE001
        print("Video-Probe fehlgeschlagen:", e)

    # Kopien ins Repo (kleine JPEGs), damit die Präsentation sie von dort holen kann
    import shutil
    repo_dir = Path("concepts/genre-test-tokyo")
    for sub in ("bilder", "thumbs", "musik", "video"):
        (repo_dir / sub).mkdir(parents=True, exist_ok=True)
    for f in (OUT / "bilder").glob("*.png"):
        Image.open(f).convert("RGB").resize((1600, 900)).save(repo_dir / "bilder" / (f.stem + ".jpg"), quality=88)
    for sub in ("thumbs", "musik", "video"):
        for f in (OUT / sub).glob("*"):
            shutil.copy(f, repo_dir / sub / f.name)
    files_by_sub = {sub: sorted((OUT / sub).glob("*")) for sub in ("bilder", "thumbs", "musik", "video")}
    links = drive.upload_mix_package("GENRE-TEST Tokyo Quiet Café", [], files_by_sub)
    for k, v in links.items():
        print(k, v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
