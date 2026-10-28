#!/usr/bin/env python3
"""Songtest für den geplanten Kanal „YOIN Rooms“ (Rolf 28.10.2026): ruhiger Tokyo-Café-Jazz, Vorbild SANCTUM.

Erzeugt mit Lyria (dieselbe Funktion wie die Tokyo-Mixe: pipeline.lyria.generate_track) drei Test-Tracks, masteriert sie auf
−18 LUFS, hängt 2 s Stille an und exportiert MP3 mit 320 kbit/s. Danach prüft das Skript jede Datei (Dauer, Bitrate,
Lautheit, Stille am Ende, Schlagzeug-Hinweise aus Spektrum/Onsets) und schreibt report.json. Fällt ein Track durch,
wird er genau einmal neu erzeugt. Kein Upload; Drive und Mail macht die Sitzung.

  python scripts/yoin_songtest.py                      # Ausgabe: build/yoin_test/
  python scripts/yoin_songtest.py --out build/yoin_test --limit-eur 1.0
"""
import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from pipeline import audio, costs, lyria  # noqa: E402

LUFS = -18.0
TAIL_SEC = 2.0
BITRATE = "320k"
MIN_SEC, MAX_SEC = 150, 300          # „ca. 3–4 Minuten“ mit Toleranz

BASE_PROMPT = (
    "Quiet Tokyo café jazz for deep work. Felt piano with soft, intimate touch, warm upright bass played gently. "
    "Slow tempo around 66 BPM, relaxed swing feel, rich jazz chords (major 7th, 9th), long sustained notes, lots of space "
    "and silence between phrases. Minimal, unhurried, contemplative, late evening in a small Tokyo kissaten. "
    "Clean studio recording, warm and close, no reverb wash, no lo-fi vinyl crackle. "
    "No drums, no percussion, no guitar, no synths. Instrumental only, no vocals."
)
TRACKS = [
    ("01_piano_bass", "Piano and bass only, no saxophone."),
    ("02_soft_sax", "Plus a very soft, breathy tenor saxophone far in the background, barely above a whisper, "
                    "playing slow long notes, never a solo."),
    ("03_morning_sax", "Early morning light, after the rain. Plus a very soft, breathy tenor saxophone far in the "
                       "background, barely above a whisper, slow long notes, never a solo, and a few soft vibraphone notes."),
]


def prompt_for(extra: str) -> str:
    return f"{BASE_PROMPT} {extra}"


# ---------------------------------------------------------------- Messungen
def loudness(path: Path) -> dict:
    """Integrierte Lautheit (EBU R128, Pausen am Ende werden vom Gate ausgenommen) und True Peak."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    summary = r.stderr[r.stderr.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    tp = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary)
    return {"lufs": float(i.group(1)) if i else None, "true_peak_db": float(tp.group(1)) if tp else None}


def probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                          "stream=bit_rate,sample_rate,channels:format=duration,bit_rate", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    st = j["streams"][0]
    return {"duration": float(j["format"]["duration"]), "bitrate": int(st.get("bit_rate") or j["format"]["bit_rate"]),
            "sample_rate": int(st["sample_rate"]), "channels": int(st["channels"])}


def tail_level_db(path: Path, sec: float = TAIL_SEC - 0.1) -> float:
    """Pegel der letzten `sec` Sekunden (dBFS, RMS) – muss praktisch Stille sein."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-sseof", f"-{sec}", "-i", str(path), "-af", "volumedetect",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"mean_volume:\s+(-?[\d.]+|-inf) dB", r.stderr)
    return -120.0 if not m or m.group(1) == "-inf" else float(m.group(1))


def percussion_check(path: Path) -> dict:
    """Hinweise auf Schlagzeug/Percussion aus Spektrum und Onsets (kein Beweis, aber ein brauchbarer Alarm):

    * hi_hat_ratio: Energieanteil 6–14 kHz an der Gesamtenergie (Becken/Besen/Hi-Hat); Klavier/Bass/Sax liegen weit darunter
    * hi_onset_peak: wie „spitz“ die Hochton-Onsets sind (Maximum / Median der Onset-Stärke 6–14 kHz) – Hi-Hat = viele gleich starke Spitzen
    * kick_onset_peak: dasselbe für das 35–110-Hz-Band der Bassdrum (Kontrabass-Töne liegen auch dort, daher nur im Vergleich lesen)
    * perc_ratio: Anteil der perkussiven Komponente (HPSS) an der Gesamtenergie
    * beat_regularity: Stärke der Periodizität der Hochton-Onsets bei 1/4–1/2 Taktschlag (hohe Werte = Beckenmuster)
    """
    import librosa
    y, sr = librosa.load(str(path), sr=32000, mono=True)
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    total = S.sum() + 1e-12
    hi = (freqs >= 6000) & (freqs <= 14000)
    lo = (freqs >= 35) & (freqs <= 110)
    hi_ratio = float(S[hi].sum() / total)

    def onset_band(mask):
        env = librosa.onset.onset_strength(S=librosa.power_to_db(S[mask] + 1e-12), sr=sr, hop_length=512)
        return env

    env_hi, env_lo = onset_band(hi), onset_band(lo)
    peak = lambda e: float(np.percentile(e, 99) / (np.median(e) + 1e-6))      # noqa: E731
    H, P = librosa.decompose.hpss(S ** 0.5)
    perc_ratio = float((P ** 2).sum() / ((H ** 2).sum() + (P ** 2).sum() + 1e-12))
    # Periodizität der Hochton-Onsets (Autokorrelation), gemessen bei 1/2 und 1/4 Schlag von 66 BPM (0,91 s)
    e = env_hi - env_hi.mean()
    ac = np.correlate(e, e, mode="full")[len(e) - 1:]
    ac = ac / (ac[0] + 1e-9)
    fps = sr / 512
    beat = 60 / 66
    reg = max(float(ac[int(round(beat * k * fps))]) for k in (0.25, 0.5, 1.0) if int(round(beat * k * fps)) < len(ac))
    return {"hi_hat_ratio": round(hi_ratio, 5), "hi_onset_peak": round(peak(env_hi), 2), "kick_onset_peak": round(peak(env_lo), 2),
            "perc_ratio": round(perc_ratio, 3), "beat_regularity": round(reg, 3)}


def tempo_estimate(path: Path) -> float:
    import librosa
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    fn = getattr(librosa.feature, "tempo", None) or librosa.feature.rhythm.tempo   # librosa ≥ 1.0 / ältere Versionen
    return float(np.atleast_1d(fn(y=y, sr=sr))[0])


# ---------------------------------------------------------------- Erzeugung
def export(raw: Path, final: Path, title: str) -> None:
    """Rohspur → −18 LUFS (WAV) → MP3 320 kbit/s mit 2 s Stille am Ende."""
    wav = raw.parent.parent / "wav" / f"{final.stem}.wav"
    audio.master(raw, wav, lufs=LUFS)
    subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", str(wav), "-af", f"apad=pad_dur={TAIL_SEC}",
                    "-c:a", "libmp3lame", "-b:a", BITRATE, "-metadata", f"title={title}", "-metadata", "artist=YOIN Rooms (Test)",
                    "-id3v2_version", "3", str(final)], check=True, capture_output=True)


def verdict(final: Path) -> dict:
    """Harte Prüfungen (problems → Neuerzeugung) und Schlagzeug-Hinweise (warnings → Sitzung beurteilt die Messwerte)."""
    info = probe(final)
    loud = loudness(final)
    perc = percussion_check(final)
    tail = tail_level_db(final)
    problems, warnings = [], []
    if not MIN_SEC <= info["duration"] - TAIL_SEC <= MAX_SEC:
        problems.append(f"Dauer {info['duration']:.0f}s außerhalb {MIN_SEC}–{MAX_SEC}s")
    if abs(info["bitrate"] - 320_000) > 8_000:
        problems.append(f"Bitrate {info['bitrate']}")
    if loud["lufs"] is None or abs(loud["lufs"] - LUFS) > 1.5:
        problems.append(f"Lautheit {loud['lufs']} LUFS")
    if tail > -60:
        problems.append(f"Ende nicht still ({tail:.0f} dB)")
    # Schwellen kalibriert am 28.10.2026 mit künstlichen Hi-Hat-/Bassdrum-Schlägen bei 66 BPM unter Track 1: Hi-Hat 30 dB unter der
    # Musik → hi_onset_peak 8,9, beat_regularity 0,92; Bassdrum 12 dB unter der Musik → perc_ratio 0,066 (ohne: 0,032). Echte Tracks ohne
    # Schlagzeug lagen bei hi_hat_ratio ≤ 0,0002, hi_onset_peak ≤ 3,1, beat_regularity ≤ 0,18, perc_ratio ≤ 0,042.
    if perc["hi_hat_ratio"] > 0.001 or perc["hi_onset_peak"] > 5 or perc["beat_regularity"] > 0.5:
        warnings.append("Schlagzeug-Verdacht: Becken/Hi-Hat-Muster (Hochton-Anteil, Onset-Spitzen oder regelmäßige Hochton-Onsets)")
    if perc["perc_ratio"] > 0.055:
        warnings.append("Schlagzeug-Verdacht: auffallend viel perkussive Energie (Bassdrum/Snare?)")
    return {"file": final.name, **info, **loud, "tail_db": round(tail, 1), "tempo_est": round(tempo_estimate(final), 1),
            "percussion": perc, "problems": problems, "warnings": warnings, "ok": not problems}


def make_track(stem: str, extra: str, out: Path, attempt: int) -> Path:
    raw = out / "raw" / f"{stem}_v{attempt}.mp3"
    if not (raw.exists() and raw.stat().st_size > 50_000):
        lyria.generate_track(prompt_for(extra), raw)
    final = out / f"{stem}.mp3"
    export(raw, final, stem)
    return final


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="nur diese Tracks (z. B. 02_soft_sax)")
    ap.add_argument("--attempt", type=int, default=1, help="Versuchsnummer der Rohdatei; 2 erzwingt eine Neuerzeugung")
    ap.add_argument("--out", default=str(HERE / "build" / "yoin_test"))
    ap.add_argument("--limit-eur", type=float, default=1.0, help="harte Kostengrenze (Standard 1 €; 3 Tracks ≈ 0,22 €)")
    a = ap.parse_args()
    out = Path(a.out)
    (out / "raw").mkdir(parents=True, exist_ok=True)
    costs.start(out / "costs.json", limit_eur=a.limit_eur)

    def job(item):
        stem, extra = item
        final = make_track(stem, extra, out, a.attempt)
        res = verdict(final)
        if not res["ok"] and a.attempt == 1:
            print(f"[{stem}] durchgefallen: {res['problems']} → einmal neu erzeugen", flush=True)
            costs.count("lyria_retries")
            final = make_track(stem, extra, out, 2)
            res = verdict(final)
            res["regenerated"] = True
        print(f"[{stem}] {'OK' if res['ok'] else 'DURCHGEFALLEN'}: {json.dumps(res, ensure_ascii=False)}", flush=True)
        return res

    todo = [t for t in TRACKS if not a.only or t[0] in a.only]
    with ThreadPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(job, todo))
    led = json.loads((out / "costs.json").read_text())
    rp = out / "report.json"
    old = {r["file"]: r for r in json.loads(rp.read_text())["tracks"]} if rp.exists() else {}
    old.update({r["file"]: r for r in results})
    results = [old[k] for k in sorted(old)]
    report = {"tracks": results, "kosten": {"lyria_tracks": led["lyria_tracks"], "usd": led["usd"], "eur": led["eur"]}}
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report["kosten"], ensure_ascii=False))
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
