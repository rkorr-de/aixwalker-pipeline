"""Strenge Videoprüfung vor dem Upload: das fertige short.mp4 geht an config.CRITIC_MODEL.

Geprüft werden typische KI-Fehler (falsche Anatomie, Morphing, Figur wechselt Aussehen, Gegenstände tauchen auf/
verschwinden, unmögliche Physik) und ob die Geschichte im Bild verständlich erzählt wird. Unter der Mindestnote
(config.VIDEO_MIN_SCORE) wird nichts veröffentlicht.
"""
import json
import subprocess
from pathlib import Path

from . import config, gemini, sfx_library

SYSTEM = (
    "You are the strict quality controller of a YouTube channel for toddlers. You watch AI-generated 15-second "
    "videos before publication and reject anything with visible AI errors or a story that does not make sense. "
    "Parents must never see glitches. Answer ONLY with valid JSON."
)


def review_video(video: Path, story: dict, contact_sheet: Path | None = None) -> dict:
    media: list[tuple[str, bytes]] = []
    small = video.with_name("qc_preview.mp4")   # 720p-Kopie, damit die Anfrage sicher unter 20 MB bleibt
    try:
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video), "-vf", "scale=720:-2",
                        "-c:v", "libx264", "-crf", "26", "-preset", "veryfast", "-c:a", "aac", "-b:a", "96k",
                        str(small)], check=True)
        video = small
    except Exception:  # noqa: BLE001
        pass
    if video.stat().st_size < 14 * 1024 * 1024:
        media.append(("video/mp4", video.read_bytes()))
    elif contact_sheet and contact_sheet.exists():
        media.append(("image/jpeg", contact_sheet.read_bytes()))
    plan = {k: story.get(k) for k in ("summary", "lesson", "character", "friend", "setting", "beats")}
    prompt = (
        f"This is the planned story:\n{json.dumps(plan, indent=1, ensure_ascii=False)}\n\n"
        "Watch the attached video very carefully, frame by frame. Score from 1 (terrible) to 10 (flawless):\n"
        "- anatomy: characters have correct, stable anatomy for their animal (no extra/missing legs, no legs on "
        "fish, no melting faces, no merged bodies)\n"
        "- consistency: the character keeps the same look, colors and size in every frame and across the cut\n"
        "- physics: objects stay solid, nothing appears/disappears/morphs, no impossible motion, no weird liquids\n"
        "- story: the planned story is clearly understandable from the pictures alone – want, problem, solution, "
        "happy end – and it makes sense\n"
        "- quality: clean image, no flicker, no text/letters/watermarks, bright and colorful, cute\n"
        "- sound: LISTEN to the audio: cheerful music clearly audible, sounds are soft, cute and child-friendly and "
        "fit the action; NO shrill squeaking, chipmunk babble, voices, grunts, harsh or loud noises\n\n"
        'Answer as JSON: {"scores": {"anatomy": n, "consistency": n, "physics": n, "story": n, "quality": n, '
        '"sound": n}, '
        '"errors": ["concrete visible error with approximate second", ...], "verdict": "publish" or "reject"}'
    )
    r = gemini.text_json(prompt, SYSTEM, temperature=0.1, model=config.CRITIC_MODEL, media=media)
    scores = {k: int(v) for k, v in (r.get("scores") or {}).items()}
    r["scores"] = scores
    r["min_score"] = min(scores.values()) if scores else 0
    r["passed"] = bool(scores) and r["min_score"] >= config.VIDEO_MIN_SCORE and r.get("verdict") != "reject"
    return r


def _length(f: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 1.0)


def place_sounds(clip: Path, story: dict, total: float = config.SHORT_SEC) -> list[dict]:
    """Die KI schaut den (stummen) Clip mit 8 Bildern/s an und legt Geräusche aus der Bibliothek auf die
    Zehntelsekunde genau auf sichtbare Aktionen. Jedes Geräusch klingt vor dem Ende vollständig aus."""
    lib = sfx_library.available()
    lens = {k: _length(sfx_library.path(k)) for k in lib}
    small = clip.with_name("sfx_preview.mp4")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(clip), "-vf", "scale=540:-2",
                    "-an", "-c:v", "libx264", "-crf", "28", "-preset", "veryfast", str(small)], check=True)
    latest = total - 0.6
    lib_txt = {k: f"{v} ({lens[k]:.1f} s long)" for k, v in lib.items()}
    prompt = (
        f"You are the sound designer of a gentle toddler cartoon. Story: {story.get('summary', '')}\n"
        "Watch the attached silent video frame by frame (8 frames per second) and place 4–6 sound effects from this "
        "LIBRARY so that each one starts EXACTLY on the frame where the matching action happens. Give times with "
        "0.1 s precision (e.g. 3.4), never just round seconds.\n"
        "- footsteps only while a character is visibly walking; thud exactly when something touches down; idea "
        "exactly when a character visibly gets the idea (eyes widen, points)\n"
        "- animal sounds (squeak_happy, chirp_happy, coo, purr) ONLY on a frame where that character's mouth "
        "visibly opens or it clearly reacts – otherwise do not use animal sounds\n"
        f"- exactly one success sound (tada or sparkle) when the goal is reached; every sound must END before "
        f"{latest:.1f} s, i.e. start + length ≤ {latest:.1f}\n"
        "- at least 1 s between cues; calm is better than busy\n"
        f"LIBRARY: {json.dumps(lib_txt)}\n"
        'Answer as JSON: {"cues": [{"second": 3.4, "sound": "footsteps", "why": "visible action at that frame"}]}'
    )
    r = gemini.text_json(prompt, "Answer ONLY with valid JSON.", temperature=0.1, model=config.CRITIC_MODEL,
                         media=[("video/mp4", small.read_bytes())], video_fps=8)
    cues = []
    for c in r.get("cues", []):
        k = c.get("sound")
        try:
            t = float(c.get("second", -1))
        except (TypeError, ValueError):
            continue
        if k not in lib or t < 0:
            continue
        t = min(t, latest - lens[k])          # sonst wird das Geräusch am Ende abgeschnitten (fehlendes Ta-da)
        if t >= 0:
            cues.append({"second": round(t, 2), "sound": k, "why": c.get("why", "")})
    return sorted(cues, key=lambda c: c["second"])[:7]


def check_sync(video: Path, cues: list[dict]) -> dict:
    """Prüft im fertigen Video (mit Ton, 8 Bilder/s), ob jedes Geräusch zur sichtbaren Aktion passt."""
    small = video.with_name("sync_preview.mp4")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video), "-vf", "scale=540:-2",
                    "-c:v", "libx264", "-crf", "28", "-preset", "veryfast", "-c:a", "aac", "-b:a", "96k", str(small)],
                   check=True)
    prompt = (
        f"Planned sound cues: {json.dumps(cues)}\nWatch and LISTEN to the attached video (8 frames per second). "
        "For each cue: is it audible, and does it start within 0.2 s of the matching visible action? Is the final "
        "success sound fully audible before the end? "
        'Answer as JSON: {"cues": [{"second": n, "sound": "...", "audible": true/false, "in_sync": true/false, '
        '"better_second": n}], "all_good": true/false}'
    )
    r = gemini.text_json(prompt, "Answer ONLY with valid JSON.", temperature=0.1, model=config.CRITIC_MODEL,
                         media=[("video/mp4", small.read_bytes())], video_fps=8)
    return r[0] if isinstance(r, list) and r else r


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1])
    st = json.loads((out / "story.json").read_text())
    print(json.dumps(review_video(out / "short.mp4", st, out / "contact_sheet.jpg"), indent=1, ensure_ascii=False))
