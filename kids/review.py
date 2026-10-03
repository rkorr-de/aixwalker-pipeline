"""Strenge Videoprüfung vor dem Upload: das fertige short.mp4 geht an config.CRITIC_MODEL.

Geprüft werden typische KI-Fehler (falsche Anatomie, Morphing, Figur wechselt Aussehen, Gegenstände tauchen auf/
verschwinden, unmögliche Physik) und ob die Geschichte im Bild verständlich erzählt wird. Unter der Mindestnote
(config.VIDEO_MIN_SCORE) wird nichts veröffentlicht.
"""
import json
import subprocess
from pathlib import Path

from . import config, gemini

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
        "- quality: clean image, no flicker, no text/letters/watermarks, bright and colorful, cute\n\n"
        'Answer as JSON: {"scores": {"anatomy": n, "consistency": n, "physics": n, "story": n, "quality": n}, '
        '"errors": ["concrete visible error with approximate second", ...], "verdict": "publish" or "reject"}'
    )
    r = gemini.text_json(prompt, SYSTEM, temperature=0.1, model=config.CRITIC_MODEL, media=media)
    scores = {k: int(v) for k, v in (r.get("scores") or {}).items()}
    r["scores"] = scores
    r["min_score"] = min(scores.values()) if scores else 0
    r["passed"] = bool(scores) and r["min_score"] >= config.VIDEO_MIN_SCORE and r.get("verdict") != "reject"
    return r


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1])
    st = json.loads((out / "story.json").read_text())
    print(json.dumps(review_video(out / "short.mp4", st, out / "contact_sheet.jpg"), indent=1, ensure_ascii=False))
