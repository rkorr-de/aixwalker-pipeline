"""Dünne Hülle um die Gemini-REST-API: Text (JSON-Antworten) und Bilder (Nano Banana), mit Kostenzählung."""
import base64
import io
import json
import re
import time
from pathlib import Path

import requests
from PIL import Image

from . import config, costs


def _headers() -> dict:
    return {"x-goog-api-key": config.require("GOOGLE_API_KEY"), "Content-Type": "application/json"}


def _post(url: str, body: dict, timeout: int = 180, tries: int = 3) -> dict:
    last = None
    for i in range(tries):
        try:
            r = requests.post(url, headers=_headers(), json=body, timeout=timeout)
            if r.status_code == 429 or r.status_code >= 500:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            if r.status_code != 200:
                raise PermissionError(f"HTTP {r.status_code}: {r.text[:400]}")
            return r.json()
        except PermissionError:
            raise
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(4 * (i + 1))
    raise RuntimeError(f"Gemini-Aufruf fehlgeschlagen: {last}")


def _find(obj, key_candidates, mime_prefix):
    if isinstance(obj, dict):
        for key in key_candidates:
            d = obj.get(key)
            if isinstance(d, dict) and d.get("data"):
                mime = d.get("mimeType") or d.get("mime_type") or ""
                if mime.startswith(mime_prefix) or not mime:
                    return d["data"]
        for v in obj.values():
            r = _find(v, key_candidates, mime_prefix)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find(v, key_candidates, mime_prefix)
            if r:
                return r
    return None


def text(prompt: str, system: str = "", json_mode: bool = True,
         model: str | None = None, media: list[tuple[str, bytes]] | None = None, video_fps: float | None = None) -> str:
    """Textaufruf; bei json_mode wird die Antwort als reines JSON angefordert.

    `model` = anderes Modell (z. B. config.CRITIC_MODEL), `media` = [(mime, bytes)] für Bild-/Videoprüfung.
    """
    key = "text_call_pro" if model and model != config.TEXT_MODEL else "text_call"
    costs.ensure_budget(key)
    url = f"{config.GEMINI_BASE}/models/{model or config.TEXT_MODEL}:generateContent"
    parts = []
    for m, b in media or []:
        part = {"inlineData": {"mimeType": m, "data": base64.b64encode(b).decode()}}
        if video_fps and m.startswith("video/"):
            part["videoMetadata"] = {"fps": video_fps}   # Standard ist 1 Bild/s – für genaue Zeiten mehr
        parts.append(part)
    parts.append({"text": prompt})
    # Keine Sampling-Parameter (temperature/top_p/top_k) und kein thinking_budget mehr senden:
    # Google hat sie abgekündigt, künftige Gemini-Modelle antworten darauf mit 400 INVALID_ARGUMENT.
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {}}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"
    data = _post(url, body, timeout=300)
    costs.count(key)
    try:
        return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]
                       if not p.get("thought"))
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Gemini: keine Textantwort: {json.dumps(data)[:400]}") from e


def text_json(prompt: str, system: str = "", model: str | None = None,
              media: list[tuple[str, bytes]] | None = None, video_fps: float | None = None) -> dict:
    raw = text(prompt, system, True, model=model, media=media, video_fps=video_fps)
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    data = json.loads(raw)
    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):   # manchmal als [ {...} ] verpackt
        data = data[0]
    return data


def image(prompt: str, aspect: str = "9:16", pro: bool = False, references: list[Image.Image] | None = None,
          out: Path | None = None) -> Image.Image:
    """Erzeugt ein Bild (Nano Banana). `references` = Bilder, die als Vorlage mitgegeben werden (Figur-Konsistenz)."""
    key = "image_pro" if pro else "image_flash"
    costs.ensure_budget(key)
    model = config.IMAGE_MODEL_PRO if pro else config.IMAGE_MODEL
    url = f"{config.GEMINI_BASE}/models/{model}:generateContent"
    parts = []
    for ref in references or []:
        buf = io.BytesIO()
        ref.save(buf, "PNG")
        parts.append({"inlineData": {"mimeType": "image/png", "data": base64.b64encode(buf.getvalue()).decode()}})
    parts.append({"text": prompt})
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect}}}
    data = _post(url, body, timeout=180)
    b64 = _find(data, ("inlineData", "inline_data"), "image")
    if not b64:
        raise RuntimeError(f"Nano Banana: kein Bild in Antwort: {json.dumps(data)[:400]}")
    costs.count(key)
    img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out, "PNG")
    return img


def lyria(prompt: str, out: Path) -> Path:
    """Kurzes Musikbett über Lyria (Weg wie in pipeline/lyria.py)."""
    costs.ensure_budget("lyria_track")
    url = f"{config.GEMINI_BASE}/models/{config.LYRIA_MODEL}:generateContent"
    data = _post(url, {"contents": [{"parts": [{"text": prompt}]}]}, timeout=300)
    b64 = _find(data, ("inlineData", "inline_data"), "audio")
    if not b64:
        raise RuntimeError(f"Lyria: kein Audio in Antwort: {json.dumps(data)[:400]}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(b64))
    costs.count("lyria_track")
    return out
