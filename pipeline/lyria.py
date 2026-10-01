"""Musikerzeugung über die Gemini-API (Lyria 3.5).

Zwei Aufrufwege, weil Google die API 2026 umgestellt hat:
1. models/<model>:generateContent  (hat im Test am 28.09.2026 funktioniert)
2. /interactions                   (neuer Interactions-API-Weg laut Doku)
Der erste erfolgreiche Weg wird gemerkt.
"""
import base64
import json
import time
from pathlib import Path

import requests

from . import config

_working_mode = None


def _find_inline_audio(obj):
    """Sucht rekursiv nach inlineData/inline_data mit Audio-MIME und liefert (mime, b64)."""
    if isinstance(obj, dict):
        for key in ("inlineData", "inline_data"):
            d = obj.get(key)
            if isinstance(d, dict):
                mime = d.get("mimeType") or d.get("mime_type") or ""
                data = d.get("data")
                if data and (mime.startswith("audio") or not mime):
                    return mime or "audio/mpeg", data
        for v in obj.values():
            r = _find_inline_audio(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_inline_audio(v)
            if r:
                return r
    return None


def _call_generate_content(prompt: str, timeout: int) -> bytes:
    url = f"{config.GEMINI_BASE}/models/{config.LYRIA_MODEL}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    r = requests.post(url, headers={"x-goog-api-key": config.require("GOOGLE_API_KEY"),
                                    "Content-Type": "application/json"},
                      json=body, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"generateContent HTTP {r.status_code}: {r.text[:400]}")
    found = _find_inline_audio(r.json())
    if not found:
        raise RuntimeError(f"generateContent: kein Audio in Antwort: {r.text[:400]}")
    return base64.b64decode(found[1])


def _call_interactions(prompt: str, timeout: int) -> bytes:
    url = f"{config.GEMINI_BASE}/interactions"
    body = {"model": config.LYRIA_MODEL, "input": prompt,
            "response_format": "mp3"}
    r = requests.post(url, headers={"x-goog-api-key": config.require("GOOGLE_API_KEY"),
                                    "Content-Type": "application/json"},
                      json=body, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"interactions HTTP {r.status_code}: {r.text[:400]}")
    found = _find_inline_audio(r.json())
    if not found:
        raise RuntimeError(f"interactions: kein Audio in Antwort: {r.text[:400]}")
    return base64.b64decode(found[1])


def generate_track(prompt: str, out_path: Path, retries: int = 3, timeout: int = 300) -> Path:
    """Erzeugt einen Track als MP3 und schreibt ihn nach out_path."""
    global _working_mode
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    modes = [_working_mode] if _working_mode else ["generateContent", "interactions"]
    last_err = None
    for attempt in range(retries):
        for mode in modes:
            try:
                fn = _call_generate_content if mode == "generateContent" else _call_interactions
                audio = fn(prompt, timeout)
                if len(audio) < 50_000:
                    raise RuntimeError(f"{mode}: Audio verdächtig klein ({len(audio)} Bytes)")
                out_path.write_bytes(audio)
                _working_mode = mode
                return out_path
            except Exception as e:  # noqa: BLE001
                last_err = e
                print(f"[lyria] {mode} Versuch {attempt + 1} fehlgeschlagen: {e}")
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Lyria: Track konnte nicht erzeugt werden: {last_err}")


def build_prompt(genre: str, bpm: int, mood: str, variation: str, minutes: float = 3.0) -> str:
    """Baut einen Lyria-Prompt. `variation` beschreibt, was diesen Track von den anderen abhebt."""
    return (
        f"{genre}, {bpm} BPM, {mood}. {variation}. "
        f"Instrumental, no vocals, no lyrics, no spoken words. "
        f"Clean intro without long silence, steady groove, natural ending suitable for a DJ mix. "
        f"Duration about {minutes:g} minutes. High fidelity stereo."
    )


if __name__ == "__main__":
    import sys
    p = build_prompt("slow gym beat, dark trap", 80, "dark, heavy, focused", "deep 808 sub bass, sparse hi-hats", 2)
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "lyria_test.mp3")
    print(generate_track(p, out), out.stat().st_size, "bytes", "mode:", _working_mode)
