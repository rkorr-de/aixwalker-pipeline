"""Mix-Video: ein Standbild pro Track (Cover auf unscharfem Hintergrund), Audio als AAC."""
import subprocess
from pathlib import Path


def build_video(frames: list[Path], starts: list[float], audio_wav: Path, total_sec: float, out: Path,
                fps: int = 30) -> Path:
    """frames[i] wird ab starts[i] gezeigt. Erzeugt 1920x1080, H.264, AAC 192k, faststart."""
    out.parent.mkdir(parents=True, exist_ok=True)
    concat = out.parent / "frames_concat.txt"
    lines = []
    for i, f in enumerate(frames):
        end = starts[i + 1] if i + 1 < len(starts) else total_sec
        dur = max(0.5, end - starts[i])
        lines.append(f"file '{f.resolve()}'\nduration {dur:.3f}")
    lines.append(f"file '{frames[-1].resolve()}'")  # letzter Frame doppelt (ffmpeg-Konvention)
    concat.write_text("\n".join(lines))
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y",
           "-f", "concat", "-safe", "0", "-i", str(concat),
           "-i", str(audio_wav),
           "-vf", f"scale=1920:1080,format=yuv420p,fps={fps}",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-tune", "stillimage", "-g", "300",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def probe(path: Path) -> dict:
    import json
    res = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return json.loads(res.stdout)
