#!/usr/bin/env python3
"""YOIN Rooms Songtest 4 (Rolf 29.10.2026): drei Prompts WORTGETREU als kompletter Lyria-Prompt.

Anders als Test 1–3 gibt es hier KEINEN Basis-Prompt und keine Zusätze: `yoin_songtest.prompt_for` wird auf die Identität gesetzt, und
`pipeline.lyria.generate_track` reicht den Text unverändert an die API weiter (kein „no drums“, kein „instrumental only“, kein festes Tempo;
die BPM-Angabe steht im Prompt). Zur Kontrolle protokolliert das Skript den tatsächlich gesendeten Text je Track in prompts_sent.json und
vergleicht ihn mit der Vorgabe. Mastering (−18 LUFS), 2 s Stille am Ende, MP3 320 kbit/s und die technische Prüfung kommen aus
yoin_songtest.py; zusätzlich wird auf Clipping geprüft. Schlagzeug-Warnungen entfallen (hier ausdrücklich erwünscht).

  python scripts/yoin_songtest4.py --out build/yoin_test4
"""
import json
import re
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yoin_songtest as t  # noqa: E402
from pipeline import lyria  # noqa: E402

TRACKS = [
    ("01_quiet_tokyo_74bpm",
     "Low-cortisol quiet Tokyo cafe jazz with subtle lo-fi chillhop undertones for deep concentration, 74 BPM. Warm Fender Rhodes electric "
     "piano and soft acoustic upright piano playing lush, jazzy minor 9th and major 7th chord progressions. Deep, round, warm sub-bass and "
     "plucked upright bass locking into a gentle, laid-back head-nodding groove. Soft brushed snare drum, muted rimshots, and whisper-quiet "
     "vinyl crackle texture. Breathy, airy muted trumpet and mellow tenor saxophone playing relaxed, nocturnal melodic phrases. Subtle, airy "
     "vocal breath textures in the background mix, warm analog tape saturation, wide architectural reverb, warm low-pass filtered top end, "
     "zero harshness, soothing deep focus atmosphere."),
    ("02_airy_brushes_68bpm",
     "Low-cortisol intimate nocturnal Japanese lounge jazz, minimalist acoustic quartet, 68 BPM. Extremely airy, breathy tenor saxophone and "
     "velvety flugelhorn playing slow, soothing melodies with audible warm breath texture. Accompanied by soft felt piano chords, a deep "
     "resonant double bass, and continuous, hypnotic jazz brushes swishing softly on a snare drum and dry ride cymbal. Wide architectural "
     "reverb, warm low-pass filtered top end, rolled-off high frequencies, ultra-smooth low-mid warmth, zero sudden dynamics, meditative "
     "late-night Tokyo sanctuary vibe, instrumental."),
    ("03_rhodes_minimal_72bpm",
     "Low-cortisol minimalist Tokyo ambient jazz-hop, deep focus flow-state instrumental, 72 BPM. Warm vintage Rhodes piano and clean "
     "hollow-body jazz guitar playing sparse, soulful jazz chords with long decay. Soft, dusty lo-fi jazz drums with gentle brush sweeps, "
     "deep muffled kick drum, and a warm, steady acoustic bassline. Subtle ambient pad humming softly in the background, wide architectural "
     "reverb, warm low-pass filtered top end, analog warmth, calm, grounding, and stress-reducing gallery atmosphere, no sharp transients."),
]
PROMPT_OF = {stem: prompt for stem, prompt in TRACKS}
BPM_OF = {"01_quiet_tokyo_74bpm": 74, "02_airy_brushes_68bpm": 68, "03_rhodes_minimal_72bpm": 72}

_sent: list[dict] = []
_lock = threading.Lock()
_out_dir: list[Path] = []


def _logging_generate(orig):
    def gen(prompt, out_path, *a, **kw):
        stem = re.sub(r"_v\d+$", "", Path(out_path).stem)
        with _lock:
            _sent.append({"track": stem, "file": Path(out_path).name, "prompt_sent": prompt,
                          "identical_to_spec": prompt == PROMPT_OF.get(stem)})
            (_out_dir[0] / "prompts_sent.json").write_text(json.dumps(_sent, indent=2, ensure_ascii=False))
        return orig(prompt, out_path, *a, **kw)
    return gen


def clipping(path: Path) -> dict:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"max_volume:\s+(-?[\d.]+) dB", r.stderr)
    return {"sample_peak_db": float(m.group(1)) if m else None}


def verdict(final: Path) -> dict:
    res = t._orig_verdict(final)
    res["warnings"] = [w for w in res["warnings"] if not w.startswith("Schlagzeug-Verdacht")]
    res.update(clipping(final))
    if res["sample_peak_db"] is None or res["sample_peak_db"] >= -0.05:
        res["problems"].append(f"Clipping (Sample-Peak {res['sample_peak_db']} dB)")
    if res.get("true_peak_db") is not None and res["true_peak_db"] > -0.5:
        res["warnings"].append(f"True Peak {res['true_peak_db']} dBTP (knapp unter Vollaussteuerung, kein Clipping)")
    res["bpm_prompt"] = BPM_OF.get(Path(final).stem)
    res["ok"] = not res["problems"]
    return res


def main() -> int:
    argv = sys.argv[1:]
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else Path(__file__).resolve().parent.parent / "build" / "yoin_test4"
    _out_dir.append(out)
    out.mkdir(parents=True, exist_ok=True)
    t.TRACKS = TRACKS
    t.prompt_for = lambda extra: extra            # kein Basis-Prompt, kein Zusatz: der Prompt ist der komplette Lyria-Text
    t._orig_verdict = t.verdict
    t.verdict = verdict
    lyria.generate_track = _logging_generate(lyria.generate_track)
    rc = t.main()
    if _sent:
        bad = [s for s in _sent if not s["identical_to_spec"]]
        print(f"Prompt-Kontrolle: {len(_sent) - len(bad)}/{len(_sent)} Aufrufe wortgleich zur Vorgabe" + (f", ABWEICHUNG: {bad}" if bad else ""))
    return rc


if __name__ == "__main__":
    sys.exit(main())
