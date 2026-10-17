"""Gemini hört das SANCTUM-Video (öffentliche YouTube-URL, nichts wird heruntergeladen) und beschreibt Klang und Look.
Daraus entstehen Lyria-Prompts, mit denen 3 neue Test-Stücke erzeugt werden (Rolf 17.10.2026: Musik soll genauso klingen).
Aufruf (Cloud mit API-Keys): python concepts/gemini_analyse_sanctum.py
"""
import json
import re
import shutil
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import config, drive, lyria  # noqa: E402

URL = "https://www.youtube.com/watch?v=4FATPTRiELQ"
OUT = Path("build/genre-test-tokyo/gemini")
REPO = Path("concepts/genre-test-tokyo/gemini")
MODELS = [config.TEXT_MODEL, "gemini-3.1-pro-preview", "gemini-2.5-pro", config.TEXT_MODEL_FALLBACK, "gemini-2.5-flash"]

ASK = """Listen carefully to the AUDIO of this video (and look at the visuals). Answer in English, concretely and technically, as a music producer would.
Part 1 – MUSIC: genre/sub-genre, tempo (BPM estimate), time feel, key/mode if audible, every instrument you hear and its role, tone/timbre of each (e.g. felt piano, close-miked, muted hammers), playing style (note density, silence between phrases, dynamics), harmony (chord types, voicings), whether drums/percussion/brushes exist, room/reverb/tape/vinyl character, stereo image, loudness feel, how tracks start and end, how the music evolves over time (variation vs repetition).
Part 2 – VISUALS: how the video image behaves (static, slow zoom, light changes), room design, light, color palette, camera view.
Part 3 – Write THREE different text prompts for the music generator Lyria that would reproduce this exact sound as closely as possible, each about 2 minutes, instrumental, with no drums if there are none. Label them LYRIA_PROMPT_1, LYRIA_PROMPT_2, LYRIA_PROMPT_3, one paragraph each, starting on a new line with the label."""


def ask_gemini() -> str:
    body = {"contents": [{"parts": [{"file_data": {"file_uri": URL, "mime_type": "video/*"}}, {"text": ASK}]}]}
    last = None
    for m in dict.fromkeys(MODELS):
        try:
            r = requests.post(f"{config.GEMINI_BASE}/models/{m}:generateContent",
                              headers={"x-goog-api-key": config.require("GOOGLE_API_KEY"), "Content-Type": "application/json"},
                              json=body, timeout=600)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            parts = r.json()["candidates"][0]["content"]["parts"]
            txt = "".join(p.get("text", "") for p in parts)
            if len(txt) < 500:
                raise RuntimeError("Antwort zu kurz: " + txt)
            print("Modell:", m)
            return f"[Modell: {m}]\n\n{txt}"
        except Exception as e:  # noqa: BLE001
            last = e
            print("Modell", m, "fehlgeschlagen:", e)
    raise RuntimeError(f"Gemini-Analyse nicht möglich: {last}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    REPO.mkdir(parents=True, exist_ok=True)
    txt = ask_gemini()
    (OUT / "analyse.txt").write_text(txt, encoding="utf-8")
    shutil.copy(OUT / "analyse.txt", REPO / "analyse.txt")
    prompts = re.findall(r"LYRIA_PROMPT_(\d)\W*\n?(.+?)(?=\n\s*\**LYRIA_PROMPT_|\Z)", txt, flags=re.S)
    files = []
    for n, p in prompts[:3]:
        p = p.strip().strip("*").strip()
        if "Duration" not in p:
            p += " Duration about 2 minutes. High fidelity stereo."
        try:
            f = lyria.generate_track(p, OUT / f"gemini-prompt-{n}.mp3")
            files.append(f)
            shutil.copy(f, REPO / f.name)
        except Exception as e:  # noqa: BLE001
            print("Lyria fehlgeschlagen", n, e)
    links = drive.upload_mix_package("GENRE-TEST Tokyo Quiet Café", [], {"gemini_analyse": [OUT / "analyse.txt"] + files})
    for k, v in links.items():
        print(k, v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
