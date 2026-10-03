"""fal.ai: Kling 3.0 Bild-zu-Video (15 s am Stück, ohne Schnitt) und ElevenLabs-Geräusche, mit Kostenzählung.

Zugang: Umgebungsvariable FAL_KEY. REST-Warteschlange: Auftrag abschicken → Status abfragen → Ergebnis laden.
Preise (fal.ai, 03.10.2026): Kling 3.0 Pro 0,112 $/s ohne Ton, Standard 0,084 $/s; Geräusche 0,002 $/s.
"""
import base64
import io
import time
from pathlib import Path

import requests
from PIL import Image

from . import config, costs

QUEUE = "https://queue.fal.run"


def available() -> bool:
    import os
    return bool(os.environ.get("FAL_KEY"))


def _headers() -> dict:
    return {"Authorization": f"Key {config.require('FAL_KEY')}", "Content-Type": "application/json"}


def _data_uri(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def run(app: str, args: dict, timeout_s: int = 1500, poll_s: int = 8) -> dict:
    """Auftrag an die fal-Warteschlange, warten, Ergebnis-JSON zurück."""
    r = requests.post(f"{QUEUE}/{app}", headers=_headers(), json=args, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"fal {app}: HTTP {r.status_code}: {r.text[:400]}")
    sub = r.json()
    status_url = sub.get("status_url") or f"{QUEUE}/{app}/requests/{sub['request_id']}/status"
    result_url = sub.get("response_url") or f"{QUEUE}/{app}/requests/{sub['request_id']}"
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        s = requests.get(status_url, headers=_headers(), timeout=60).json()
        st = s.get("status")
        if st == "COMPLETED":
            res = requests.get(result_url, headers=_headers(), timeout=120)
            if res.status_code >= 400:
                raise RuntimeError(f"fal {app}: Ergebnis HTTP {res.status_code}: {res.text[:400]}")
            return res.json()
        if st not in ("IN_QUEUE", "IN_PROGRESS"):
            raise RuntimeError(f"fal {app}: Status {s}")
        time.sleep(poll_s)
    raise TimeoutError(f"fal {app}: keine Antwort nach {timeout_s} s")


def _download(url: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(out, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    return out


def kling_clip(prompt: str, first_frame: Image.Image, out: Path, seconds: int = 15,
               tier: str | None = None, audio: bool = False) -> Path:
    """Ein durchgehender Kling-3.0-Clip (3–15 s) ab dem Startbild."""
    tier = tier or config.KLING_TIER
    key = f"kling_sec_{tier}" + ("_audio" if audio else "")
    costs.ensure_budget(key, seconds)
    app = f"fal-ai/kling-video/v3/{tier}/image-to-video"
    res = run(app, {"prompt": prompt[:2500], "start_image_url": _data_uri(first_frame), "duration": str(seconds),
                    "generate_audio": audio, "negative_prompt": config.NEGATIVE_PROMPT[:500], "cfg_scale": 0.5})
    costs.count(key, seconds)
    return _download(res["video"]["url"], out)


def sound_effects(text: str, out: Path, seconds: float = 15.0) -> Path:
    """Geräuschkulisse (ElevenLabs Sound Effects V2) passend zur Handlung – ohne Stimmen."""
    costs.ensure_budget("sfx_sec", seconds)
    res = run("fal-ai/elevenlabs/sound-effects/v2",
              {"text": text[:450], "duration_seconds": seconds, "prompt_influence": 0.5}, timeout_s=300, poll_s=3)
    costs.count("sfx_sec", seconds)
    return _download(res["audio"]["url"], out)
