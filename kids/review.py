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
        "Watch AND listen to the attached video carefully. List every problem you notice and classify it:\n"
        "- critical: an object or character suddenly appears, disappears or turns into something else; wrong "
        "number of limbs or body parts that do not belong (e.g. legs on a fish); a creature in an impossible "
        "situation (fish out of water, floating in the air without reason); bodies melting into each other for "
        "more than a moment; real recognizable words or sentences in any language; scary, rude or unsafe content; "
        "the story makes no sense at all\n"
        "- major: clearly visible glitch for more than half a second (limb clipping through an object, face "
        "distorted), a hard jump cut that breaks continuity, story only partly understandable, sound clearly not "
        "matching the picture, harsh or shrill sound\n"
        "- minor: brief small artifacts, slight morphing of paws during fast motion, small inconsistencies – "
        "normal for animation and acceptable\n"
        "Cute nonsense babble, giggles and animal squeaks are NOT problems.\n"
        "Also give an overall score 1–10 for how good this is as a toddler cartoon.\n"
        'Answer as JSON: {"problems": [{"second": n, "severity": "critical|major|minor", "text": "..."}], '
        '"overall": n}'
    )
    r = gemini.text_json(prompt, SYSTEM, model=config.CRITIC_MODEL, media=media)
    probs = r.get("problems") or []
    crit = [p for p in probs if p.get("severity") == "critical"]
    major = [p for p in probs if p.get("severity") == "major"]
    r["errors"] = [f"{p.get('second', '?')} s [{p.get('severity')}] {p.get('text', '')}" for p in crit + major]
    r["scores"] = {"overall": int(r.get("overall", 0)), "critical": len(crit), "major": len(major),
                   "minor": len(probs) - len(crit) - len(major)}
    # Kalibriert an Rolfs Urteil (03.10.2026): Goldfisch-Video (Fisch in der Luft, Feder taucht auf/verschwindet)
    # muss scheitern, das Kling-Video (kleine Pfoten-Artefakte) bestehen.
    r["passed"] = (len(crit) <= config.VIDEO_MAX_CRITICAL and len(crit) + len(major) <= config.VIDEO_MAX_ERRORS
                   and r["scores"]["overall"] >= config.VIDEO_MIN_SCORE)
    r["min_score"] = r["scores"]["overall"]
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
    r = gemini.text_json(prompt, "Answer ONLY with valid JSON.", model=config.CRITIC_MODEL,
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
    r = gemini.text_json(prompt, "Answer ONLY with valid JSON.", model=config.CRITIC_MODEL,
                         media=[("video/mp4", small.read_bytes())], video_fps=8)
    return r[0] if isinstance(r, list) and r else r


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1])
    st = json.loads((out / "story.json").read_text())
    print(json.dumps(review_video(out / "short.mp4", st, out / "contact_sheet.jpg"), indent=1, ensure_ascii=False))
