"""Veo 3.x über die Gemini-API: Bild + Prompt → 8-s-Clip (9:16) mit nativem Ton.

Ablauf (REST): POST models/<veo>:predictLongRunning → operation name → GET operations/... bis done →
response.generateVideoResponse.generatedSamples[0].video.uri → Download mit API-Key.
Die Modell-Liste in config.VEO_MODELS wird der Reihe nach probiert (erstes freigeschaltetes Modell gewinnt
und wird für den Rest des Laufs gemerkt).
"""
import base64
import io
import json
import time
from pathlib import Path

import requests
from PIL import Image

from . import config, costs

_model: str | None = None


def _headers() -> dict:
    return {"x-goog-api-key": config.require("GOOGLE_API_KEY"), "Content-Type": "application/json"}


def _b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _price_key(model: str) -> str:
    if "lite" in model:
        return "veo_sec_lite"
    return "veo_sec_fast" if "fast" in model else "veo_sec_standard"


def _start(model: str, prompt: str, first_frame: Image.Image | None, references: list[Image.Image],
           last_frame: Image.Image | None) -> str:
    inst: dict = {"prompt": prompt}
    if first_frame is not None:
        inst["image"] = {"bytesBase64Encoded": _b64(first_frame), "mimeType": "image/png"}
    if last_frame is not None:
        inst["lastFrame"] = {"bytesBase64Encoded": _b64(last_frame), "mimeType": "image/png"}
    if references:
        inst["referenceImages"] = [{"image": {"bytesBase64Encoded": _b64(r), "mimeType": "image/png"},
                                    "referenceType": "asset"} for r in references[:3]]
    params = {"aspectRatio": "9:16", "durationSeconds": config.VEO_CLIP_SEC, "negativePrompt": config.NEGATIVE_PROMPT,
              "personGeneration": "allow_adult"}   # Veo 3.1 Bild-zu-Video erlaubt nur diesen Wert
    if config.VEO_RESOLUTION and "3.1" in model:
        params["resolution"] = config.VEO_RESOLUTION
    url = f"{config.GEMINI_BASE}/models/{model}:predictLongRunning"
    r = requests.post(url, headers=_headers(), json={"instances": [inst], "parameters": params}, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"{model} HTTP {r.status_code}: {r.text[:500]}")
    name = r.json().get("name")
    if not name:
        raise RuntimeError(f"{model}: keine Operation in Antwort: {r.text[:300]}")
    return name


def _poll(name: str, timeout_s: int = 900) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        r = requests.get(f"{config.GEMINI_BASE}/{name}", headers=_headers(), timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"Operation HTTP {r.status_code}: {r.text[:300]}")
        op = r.json()
        if op.get("done"):
            if op.get("error"):
                raise RuntimeError(f"Veo-Fehler: {json.dumps(op['error'])[:400]}")
            return op
        time.sleep(10)
    raise TimeoutError("Veo: Operation nicht fertig nach Zeitlimit")


def _video_uri(op: dict) -> str:
    resp = op.get("response", {})
    gen = resp.get("generateVideoResponse") or resp
    samples = gen.get("generatedSamples") or gen.get("videos") or []
    if not samples:
        raise RuntimeError(f"Veo: kein Video in Antwort (evtl. Sicherheitsfilter): {json.dumps(resp)[:400]}")
    s = samples[0]
    uri = (s.get("video") or {}).get("uri") or s.get("uri") or s.get("gcsUri")
    if not uri:
        raise RuntimeError(f"Veo: keine Video-URI: {json.dumps(s)[:300]}")
    return uri


def _download(uri: str, out: Path) -> Path:
    r = requests.get(uri, headers={"x-goog-api-key": config.require("GOOGLE_API_KEY")}, timeout=300,
                     allow_redirects=True)
    if r.status_code != 200 or len(r.content) < 100_000:
        raise RuntimeError(f"Veo-Download fehlgeschlagen: HTTP {r.status_code}, {len(r.content)} Bytes")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(r.content)
    return out


def generate_clip(prompt: str, out: Path, first_frame: Image.Image | None = None,
                  references: list[Image.Image] | None = None, last_frame: Image.Image | None = None,
                  retries: int | None = None) -> Path:
    """Erzeugt einen Clip; probiert Modelle der Reihe nach, zählt Kosten, wiederholt bei Fehlern."""
    global _model
    retries = config.MAX_CLIP_RETRIES if retries is None else retries
    models = [_model] if _model else config.VEO_MODELS
    last_err = None
    for attempt in range(retries + 1):
        for model in models:
            key = _price_key(model)
            costs.ensure_budget(key, config.VEO_CLIP_SEC)
            variants = []
            if references:
                variants.append(("mit Referenzbildern", references))
            variants.append(("ohne Referenzbilder", []))
            next_model = False
            for label, refs in variants:
                try:
                    print(f"[veo] {model} {label}, Versuch {attempt + 1}")
                    name = _start(model, prompt, first_frame, refs, last_frame)
                    op = _poll(name)
                    uri = _video_uri(op)
                    _download(uri, out)
                    costs.count(key, config.VEO_CLIP_SEC)
                    _model = model
                    return out
                except Exception as e:  # noqa: BLE001
                    last_err = e
                    msg = str(e)
                    print(f"[veo] {model} {label} fehlgeschlagen: {msg[:300]}")
                    costs.count("veo_failed")
                    unavailable = "404" in msg or "not found" in msg.lower() or "403" in msg
                    bad_request = "400" in msg or "invalid" in msg.lower()
                    if unavailable:
                        next_model = True
                        break
                    if bad_request and refs:
                        continue          # gleiche Anfrage ohne Referenzbilder
                    if bad_request:
                        next_model = True
                        break
                    break                 # vorübergehender Fehler (5xx, Timeout, Filter) → gleiches Modell später erneut
            if not next_model:
                models = [model]          # Modell ist erreichbar: nur dieses erneut versuchen
                break
        time.sleep(15)
    raise RuntimeError(f"Veo: Clip konnte nicht erzeugt werden: {last_err}")


def current_model() -> str | None:
    return _model
