"""Audio-Qualitätsprüfung, Mastering (Loudness), MP3-Export mit Tags und Cover."""
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from mutagen.id3 import APIC, ID3, TALB, TCON, TDRC, TIT2, TPE1, TPE2, TRCK
from mutagen.mp3 import MP3

from . import config


@dataclass
class QC:
    duration: float
    tempo: float
    silence_ratio: float
    rms_db: float
    ok: bool
    reason: str = ""


def probe_duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def quality_check(path: Path, target_bpm: int | None = None, min_sec: float = 90, max_sec: float = 480,
                  bpm_tolerance: float = 0.25) -> QC:
    """Prüft Dauer, Stille-Anteil, Pegel und (grob) Tempo. Halbes/doppeltes Tempo zählt als Treffer."""
    import librosa
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    duration = len(y) / sr
    frame = 2048
    rms = librosa.feature.rms(y=y, frame_length=frame, hop_length=512)[0]
    rms_db = float(20 * np.log10(np.mean(rms) + 1e-9))
    silence_ratio = float(np.mean(rms < 0.005))
    try:
        tempo = float(np.atleast_1d(librosa.feature.rhythm.tempo(y=y, sr=sr))[0])
    except Exception:  # noqa: BLE001
        tempo = 0.0
    ok, reason = True, ""
    if duration < min_sec:
        ok, reason = False, f"zu kurz ({duration:.0f}s)"
    elif duration > max_sec:
        ok, reason = False, f"zu lang ({duration:.0f}s)"
    elif silence_ratio > 0.15:
        ok, reason = False, f"zu viel Stille ({silence_ratio:.0%})"
    elif rms_db < -40:
        ok, reason = False, f"zu leise ({rms_db:.0f} dB)"
    elif target_bpm and tempo > 0:
        cands = [tempo, tempo / 2, tempo * 2]
        if not any(abs(c - target_bpm) / target_bpm <= bpm_tolerance for c in cands):
            ok, reason = False, f"Tempo {tempo:.0f} passt nicht zu {target_bpm} BPM"
    return QC(duration, tempo, silence_ratio, rms_db, ok, reason)


def master(src: Path, dst: Path, lufs: float = config.TARGET_LUFS, trim_silence: bool = True) -> Path:
    """Zweistufiges Loudness-Mastering (EBU R128) plus Stille-Trimming, Ausgabe als WAV."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    pre = "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.3," if trim_silence else ""
    # Pass 1: messen
    cmd1 = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-af",
            f"{pre}loudnorm=I={lufs}:TP=-1.0:LRA=11:print_format=json", "-f", "null", "-"]
    res = subprocess.run(cmd1, capture_output=True, text=True)
    j = res.stderr[res.stderr.rfind("{"):]
    try:
        m = json.loads(j)
        measured = (f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
                    f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    except Exception:  # noqa: BLE001
        measured = ""
    af = f"{pre}loudnorm=I={lufs}:TP=-1.0:LRA=11" + (":" + measured if measured else "")
    af += ",areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.5,areverse" if trim_silence else ""
    cmd2 = ["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", str(src), "-af", af,
            "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(dst)]
    subprocess.run(cmd2, check=True, capture_output=True)
    return dst


def export_mp3(src_wav: Path, dst_mp3: Path, title: str, album: str, track_no: int, total: int,
               cover_png: Path, genre: str, year: int) -> Path:
    dst_mp3.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", str(src_wav),
                    "-c:a", "libmp3lame", "-b:a", config.MP3_BITRATE, "-id3v2_version", "3", str(dst_mp3)],
                   check=True, capture_output=True)
    audio = MP3(dst_mp3)
    try:
        audio.add_tags()
    except Exception:  # noqa: BLE001
        pass
    tags = ID3(dst_mp3)
    tags.delete()
    tags.add(TIT2(encoding=3, text=title))
    tags.add(TPE1(encoding=3, text=config.ARTIST))
    tags.add(TPE2(encoding=3, text=config.ARTIST))
    tags.add(TALB(encoding=3, text=album))
    tags.add(TRCK(encoding=3, text=f"{track_no}/{total}"))
    tags.add(TCON(encoding=3, text=genre))
    tags.add(TDRC(encoding=3, text=str(year)))
    tags.add(APIC(encoding=3, mime="image/png", type=3, desc="Cover", data=cover_png.read_bytes()))
    tags.save(dst_mp3, v2_version=3)
    return dst_mp3


def concat_wavs(wavs: list[Path], dst: Path, crossfade_sec: float = 1.5) -> tuple[Path, list[float]]:
    """Fügt WAVs mit kurzem Crossfade zusammen. Liefert Datei und Startzeiten je Track (für Kapitel)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    durations = [probe_duration(w) for w in wavs]
    starts, t = [], 0.0
    for d in durations:
        starts.append(t)
        t += d - crossfade_sec
    if len(wavs) == 1:
        subprocess.run(["ffmpeg", "-y", "-i", str(wavs[0]), str(dst)], check=True, capture_output=True)
        return dst, [0.0]
    inputs = []
    for w in wavs:
        inputs += ["-i", str(w)]
    chain, prev = "", "[0:a]"
    for i in range(1, len(wavs)):
        out = f"[a{i}]" if i < len(wavs) - 1 else "[out]"
        chain += f"{prev}[{i}:a]acrossfade=d={crossfade_sec}:c1=tri:c2=tri{out};"
        prev = out
    subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-y", *inputs, "-filter_complex", chain.rstrip(";"),
                    "-map", "[out]", "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(dst)],
                   check=True, capture_output=True)
    return dst, starts
