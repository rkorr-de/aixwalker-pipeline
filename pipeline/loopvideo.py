"""Kaminfilm aus kurzen KI-Clips (Cozy-Winter-Cabin-Linie, Rolf 09.10.2026): nahtloser Loop („Seamless Loop“).

Ablauf:
1. Veo 3.1 erzeugt aus EINEM Hauptbild mehrere 8-s-Clips in 4K; erstes UND letztes Bild = Hauptbild (`lastFrame`),
   Kamera fest, nur Feuer, Kerzen und Schnee bewegen sich.
2. Veo landet am Clip-Ende nur fast auf dem Startbild (Schneeflocken sitzen anders). Darum bauen wir für jedes
   Clip-Paar X→Y ein Segment = X ab Bild N, dessen letzte N Bilder weich in die ersten N Bilder von Y überblendet
   werden. Auf X→Y folgt immer ein Segment, das mit Y beginnt → die Bewegung läuft ohne Sprung weiter, egal in
   welcher Reihenfolge die Clips kommen.
3. Die Segmente werden EINMAL kodiert (gleiche Einstellungen, Schlüsselbild am Anfang) und danach nur noch ohne
   Neuberechnung aneinandergehängt → ein 2-Stunden-4K-Video entsteht in Minuten. Nur das erste Segment (Einblenden
   aus Schwarz) und das letzte (Ausblenden, auf Länge gekürzt) werden eigens kodiert.
"""
import base64
import io
import json
import random
import subprocess
import time
from pathlib import Path

import numpy as np
import requests
from PIL import Image

from . import config, costs

W, H, FPS = 3840, 2160, 24
BLEND = 12            # Bilder Überblendung an jeder Nahtstelle (0,5 s)
CRF = 26              # H.264-Qualität: ca. 15 Mbit/s bei 4K (Test 09.10.: SSIM 0,98 zur CRF-20-Fassung)
# mbtree=0: sonst ist das erste Bild jedes neu kodierten Segments sichtbar schärfer als die Bilder davor (Mini-Ruck an
# der Naht, gemessen 1,6 statt normal 0,7); ohne mbtree liegt die Naht im normalen Bereich (1,37 ≈ Schlüsselbilder).
VEO_MODEL = "veo-3.1-fast-generate-preview"
VEO_RESOLUTION = "4k"
VEO_SEC = 8

LOOP_PROMPT = (
    "Static locked-off tripod shot of exactly this photograph, absolutely no camera movement: no zoom, no pan, no tilt, "
    "no dolly, no parallax. The room stays exactly as it is. Only three things move: the fire in the stone fireplace "
    "burns and flickers naturally with gently dancing flames and glowing embers, its warm golden light softly pulsing on "
    "the nearby stone; the small candle flames flicker softly; outside the panoramic windows heavy snow falls "
    "continuously and steadily at a constant gentle speed in front of the dark snowy pine forest. Everything else is "
    "completely still: no people, no animals, no objects moving, no blankets moving, no change of light or exposure, no "
    "time-of-day change, nothing appears or disappears. Calm, cozy, cinematic, photorealistic, real footage. The video "
    "starts and ends on exactly the same frame so it loops seamlessly. Sound: only the soft crackling of the fireplace.")
LOOP_NEGATIVE = (
    "camera movement, zoom, pan, tilt, shake, dolly, people, person, hands, animals, text, letters, logo, watermark, "
    "morphing, warping, flicker of the whole image, exposure change, light change, objects moving or appearing, music")


def frame_16x9(img: Image.Image) -> Image.Image:
    """Hauptbild exakt auf 3840×2160 zuschneiden (Nano Banana liefert 4K mit leicht anderem Seitenverhältnis)."""
    img = img.convert("RGB")
    w, h = img.size
    if w / h > 16 / 9:
        cw = round(h * 16 / 9)
        img = img.crop(((w - cw) // 2, 0, (w - cw) // 2 + cw, h))
    else:
        ch = round(w * 9 / 16)
        img = img.crop((0, (h - ch) // 2, w, (h - ch) // 2 + ch))
    return img.resize((W, H), Image.LANCZOS)


# ---------------------------------------------------------------- Veo
def _veo_headers() -> dict:
    return {"x-goog-api-key": config.require("GOOGLE_API_KEY"), "Content-Type": "application/json"}


def generate_clip(frame: Image.Image, out: Path, prompt: str = LOOP_PROMPT, timeout_s: int = 1800) -> Path:
    """Ein 8-s-Clip in 4K; Start- und Endbild = `frame`."""
    buf = io.BytesIO()
    frame.convert("RGB").save(buf, "JPEG", quality=95)
    img = {"bytesBase64Encoded": base64.b64encode(buf.getvalue()).decode(), "mimeType": "image/jpeg"}
    body = {"instances": [{"prompt": prompt, "image": img, "lastFrame": img}],
            "parameters": {"aspectRatio": "16:9", "durationSeconds": VEO_SEC, "resolution": VEO_RESOLUTION,
                           "negativePrompt": LOOP_NEGATIVE, "personGeneration": "allow_adult"}}
    r = requests.post(f"{config.GEMINI_BASE}/models/{VEO_MODEL}:predictLongRunning", headers=_veo_headers(),
                      json=body, timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f"Veo HTTP {r.status_code}: {r.text[:400]}")
    name = r.json()["name"]
    t0 = time.time()
    while True:
        time.sleep(15)
        op = requests.get(f"{config.GEMINI_BASE}/{name}", headers=_veo_headers(), timeout=60).json()
        if op.get("done"):
            break
        if time.time() - t0 > timeout_s:
            raise TimeoutError("Veo: Clip nicht rechtzeitig fertig")
    if op.get("error"):
        raise RuntimeError(f"Veo-Fehler: {json.dumps(op['error'])[:400]}")
    resp = op.get("response", {})
    gen = resp.get("generateVideoResponse") or resp
    samples = gen.get("generatedSamples") or gen.get("videos") or []
    if not samples:
        raise RuntimeError(f"Veo: kein Video (Sicherheitsfilter?): {json.dumps(resp)[:300]}")
    uri = (samples[0].get("video") or {}).get("uri") or samples[0].get("uri")
    v = requests.get(uri, headers={"x-goog-api-key": config.require("GOOGLE_API_KEY")}, timeout=600)
    if v.status_code != 200 or len(v.content) < 1_000_000:
        raise RuntimeError(f"Veo-Download fehlgeschlagen: HTTP {v.status_code}, {len(v.content)} Bytes")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(v.content)
    costs.count("veo_sec_4k_fast", VEO_SEC)
    return out


# ---------------------------------------------------------------- Prüfung
def _read(path: Path, scale: int = 1):
    vf = ["-vf", f"scale={W // scale}:{H // scale}:flags=area"] if scale > 1 else []
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(path), *vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = (W // scale) * (H // scale) * 3
    try:
        while True:
            b = p.stdout.read(n)
            if len(b) < n:
                return
            yield np.frombuffer(b, np.uint8).reshape(H // scale, W // scale, 3)
    finally:
        p.kill()


def check_clip(path: Path) -> dict:
    """Prüft einen Clip: 4K, 8 s, Kamera fest (große ruhige Fläche), keine Belichtungssprünge, kein Stillstand
    am Anfang/Ende (Veo-„Zeitlupe“). Liefert Kennzahlen und ok/Grund."""
    f = np.stack([x.astype(np.float32) for x in _read(path, 4)])
    motion = f.std(axis=0).mean(axis=2)
    static = motion < 2.0
    lum = f.mean(axis=3)[:, static].mean(axis=1)
    step = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2, 3))
    # Sprung-Index im bewegten Bereich (Schnee, Feuer): Änderung zum nächsten Bild im Verhältnis zur Änderung über
    # 6 Bilder. Gleichmäßige Bewegung ≈ 0,55; ein harter Sprung ≈ 1,0. Test 09.10.: Veo-Clips max. 0,62–0,66.
    g = f.mean(axis=3)
    mov = motion > 3
    jump = np.zeros(1)
    if mov.any():
        s = g[:, mov]
        d1 = np.abs(s[1:] - s[:-1]).mean(axis=1)
        d6 = np.array([np.abs(s[min(i + 6, len(s) - 1)] - s[i]).mean() for i in range(len(s) - 1)])
        jump = (d1 / np.maximum(d6, 1e-3))[:-6]
    res = {"frames": len(f), "static_share": round(float(static.mean()), 3),
           "jump_median": round(float(np.median(jump)), 3), "jump_max": round(float(jump.max()), 3),
           "lum_drift": round(float(lum.max() - lum.min()), 2),
           "static_jitter": round(float(np.abs(np.diff(f, axis=0)).mean(axis=3)[:, static].mean()), 3),
           "motion_start": round(float(step[:6].mean()), 2), "motion_mid": round(float(step[len(step) // 2 - 3:
                                                                                        len(step) // 2 + 3].mean()), 2),
           "motion_end": round(float(step[-6:].mean()), 2)}
    reasons = []
    if res["frames"] < VEO_SEC * FPS - 2:
        reasons.append("zu kurz")
    if res["static_share"] < 0.45:
        reasons.append("zu viel Bewegung im Raum (Kamera?)")
    if res["jump_max"] > 0.8 or res["jump_max"] > 1.35 * res["jump_median"]:
        reasons.append("Sprung im Schnee/Feuer")
    if res["lum_drift"] > 3.0:
        reasons.append("Helligkeit pumpt")
    if res["static_jitter"] > 0.8:
        reasons.append("Raum zittert")
    if min(res["motion_start"], res["motion_end"]) < 0.35 * res["motion_mid"]:
        reasons.append("Stillstand am Anfang/Ende")
    res["ok"] = not reasons
    res["reason"] = ", ".join(reasons)
    return res


# ---------------------------------------------------------------- Segmente und Zusammenbau
def _frame_count(path: Path) -> int:
    r = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries",
                        "stream=nb_read_packets", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return int(r.stdout.strip())


def _encoder(out: Path, fade_in: float = 0.0, fade_out_at: float | None = None, size: tuple[int, int] = (W, H),
             crop: str | None = None, out_size: tuple[int, int] | None = None) -> subprocess.Popen:
    vf = []
    if crop:
        vf.append(crop)
    if out_size:
        vf.append(f"scale={out_size[0]}:{out_size[1]}:flags=lanczos")
    if fade_in:
        vf.append(f"fade=t=in:st=0:d={fade_in}")
    if fade_out_at is not None:
        vf.append(f"fade=t=out:st={fade_out_at:.3f}:d=3")
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}",
           "-r", str(FPS), "-i", "-"]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", str(CRF), "-pix_fmt", "yuv420p",
            "-x264-params", f"keyint={FPS * 2}:min-keyint={FPS * 2}:scenecut=0:open-gop=0:mbtree=0",
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", str(out)]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def _segment_frames(x: Path, y: Path):
    """Bilder des Segments X→Y: X ab Bild BLEND, Ende weich in Y[0:BLEND] überblendet."""
    yh = []
    for f in _read(y):
        yh.append(f.astype(np.float32))
        if len(yh) == BLEND:
            break
    n = _frame_count(x)
    for i, f in enumerate(_read(x)):
        if i < BLEND:
            continue
        k = i - (n - BLEND)
        if k >= 0:
            a = (k + 1) / (BLEND + 1)
            a = a * a * (3 - 2 * a)
            f = (f.astype(np.float32) * (1 - a) + yh[k] * a).astype(np.uint8)
        yield f


def build_segment(pairs: list[tuple[Path, Path]], out: Path, fade_in: float = 0.0, max_frames: int | None = None,
                  fade_out: bool = False) -> Path:
    """Kodiert ein oder mehrere Paar-Segmente (X→Y) am Stück; optional Ein-/Ausblenden, auf max_frames gekürzt."""
    total = max_frames or sum(_frame_count(x) - BLEND for x, _ in pairs)
    enc = _encoder(out, fade_in, (total / FPS - 3) if fade_out else None)
    i = 0
    for x, y in pairs:
        for f in _segment_frames(x, y):
            if i >= total:
                break
            enc.stdin.write(f.tobytes())
            i += 1
    enc.stdin.close()
    if enc.wait() != 0 or i < total:
        raise RuntimeError(f"Segment {out.name} fehlgeschlagen ({i}/{total} Bilder)")
    return out


def sequence(clips: list[str], n: int, seed: int | None = None) -> list[str]:
    """Zufällige Reihenfolge der Clips, nie zweimal derselbe direkt hintereinander (bei ≥ 2 Clips)."""
    rnd = random.Random(seed)
    seq = [rnd.choice(clips)]
    while len(seq) < n:
        opts = [c for c in clips if c != seq[-1]] or clips
        seq.append(rnd.choice(opts))
    return seq


def build_video(clips: list[Path], audio: Path, out: Path, work: Path, seed: int | None = None,
                log=print) -> Path:
    """Kaminfilm in Länge der Tonspur: Segmente bauen, aneinanderhängen (ohne Neukodierung), Ton dazu."""
    work.mkdir(parents=True, exist_ok=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(audio)], capture_output=True, text=True).stdout)
    names = [c.stem for c in clips]
    by = {c.stem: c for c in clips}
    seg_sec = (_frame_count(clips[0]) - BLEND) / FPS
    n = max(3, int(np.ceil(dur / seg_sec)))          # Segmente: erstes (Einblenden), Mitte (Kopien), Ende (2 am Stück)
    seq = sequence(names, n + 1, seed)

    def pair(k: int) -> tuple[Path, Path]:           # Segment k = Clip seq[k], am Ende überblendet in seq[k + 1]
        return by[seq[k]], by[seq[k + 1]]

    for k in range(1, n - 2):                        # jedes Clip-Paar nur einmal kodieren
        p = work / f"seg_{seq[k]}_{seq[k + 1]}.mp4"
        if not p.exists():
            log(f"Segment {seq[k]}→{seq[k + 1]} wird kodiert …")
            build_segment([pair(k)], p)
    first = build_segment([pair(0)], work / "seg_first.mp4", fade_in=3.0)
    # Ende: die letzten beiden Segmente am Stück, exakt auf Tonlänge gekürzt, mit Ausblenden
    tail_frames = int(round((dur - (n - 2) * seg_sec) * FPS))
    last = build_segment([pair(n - 2), pair(n - 1)], work / "seg_last.mp4", max_frames=tail_frames, fade_out=True)
    lst = [first] + [work / f"seg_{seq[k]}_{seq[k + 1]}.mp4" for k in range(1, n - 2)] + [last]
    (work / "list.txt").write_text("".join(f"file '{p.resolve()}'\n" for p in lst))
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(work / "list.txt"),
                    "-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
                    "-ar", "48000", "-shortest", "-movflags", "+faststart", str(out)], check=True)
    for p in (first, last):
        p.unlink(missing_ok=True)
    log(f"Kaminfilm fertig: {out.name}, {dur / 60:.1f} Min, {out.stat().st_size / 1e9:.2f} GB, Folge {''.join(seq[:12])}…")
    return out


# ---------------------------------------------------------------- Ton: Musik + durchgehendes Kaminknistern
def mix_with_crackle(music: Path, crackle_loop: Path, out: Path, crackle_db: float = 0.0) -> Path:
    """Legt die Knister-Schleife (gemeinfrei, assets/ambience, auf −30 LUFS normiert) unter den ganzen Mix – bei
    Musik mit −16 LUFS liegt das Knistern ca. 14 dB darunter. `crackle_db` verschiebt es lauter/leiser."""
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(music)], capture_output=True, text=True).stdout)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(music), "-stream_loop", "-1", "-i", str(crackle_loop),
                    "-filter_complex",
                    f"[1:a]atrim=0:{dur:.3f},volume={crackle_db}dB,afade=t=in:d=3,afade=t=out:st={dur - 4:.3f}:d=4[c];"
                    f"[0:a]aresample=48000[m];[m][c]amix=inputs=2:normalize=0,alimiter=limit=0.84:level=false[a]",
                    "-map", "[a]", "-ar", "48000", "-ac", "2", str(out)], check=True)
    return out
