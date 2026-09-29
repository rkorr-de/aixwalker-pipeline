#!/usr/bin/env python3
"""Baut aus einem Konzept (JSON) das komplette Mix-Paket und lädt es optional privat auf YouTube.

Aufruf:
  python run_mix.py concept.json --out build/2026-10-02 [--upload] [--dry-run] [--publish-at 2026-10-02T16:00:00Z]

Konzept-JSON (Beispiel in concepts/example.json):
{
  "slug": "iron-focus-vol1",
  "album": "Iron Focus Vol. 1",
  "genre": "Slow Gym Beats",
  "bpm": 80,
  "mood": "dark, heavy, hypnotic",
  "playlist": "gym",
  "minutes_per_track": 3,
  "tracks": [ {"title": "Beneath the Bar", "variation": "deep 808, sparse hats"}, ... ],
  "art_prompt": "...",            # Motiv für Album/Thumbnail
  "track_art_prompts": ["...", ...],  # optional, sonst art_prompt mit Variation
  "thumbnail_headline": "IRON FOCUS",
  "thumbnail_sub": "80 BPM · 40 MIN",
  "yt_title": "...", "hook": "...", "intro": "...", "use_line": "...", "cta_question": "...",
  "hashtags": ["#GymMusic", ...], "tags": [...],
  "ab_titles": [...], "ab_thumbs": [...], "shorts": [{"start":"12:40","end":"13:20","overlay":"...","why":"..."}],
  "title_de": "...", "teaser_de": "...", "pinned_comment": "..."
}
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import date
from pathlib import Path

from pipeline import audio, config, images, lyria, metadata, video


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def synthetic_track(out: Path, seconds: int, bpm: int, seed: int) -> Path:
    """Test-Audio ohne API: Bassdrum-Puls + Rauschen, damit die Pipeline ohne Kosten läuft."""
    beat = 60 / bpm
    subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-y", "-f", "lavfi", "-t", str(seconds),
                    "-i", f"sine=frequency={55 + seed * 3}:sample_rate=44100",
                    "-f", "lavfi", "-t", str(seconds), "-i", "anoisesrc=color=brown:amplitude=0.05:sample_rate=44100",
                    "-filter_complex",
                    f"[0:a]tremolo=f={1 / beat:.3f}:d=0.9,volume=0.6[k];[k][1:a]amix=inputs=2:normalize=0,"
                    f"afade=t=in:d=1,afade=t=out:st={seconds - 2}:d=2[a]",
                    "-map", "[a]", "-c:a", "libmp3lame", "-b:a", "128k", str(out)],
                   check=True, capture_output=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("concept")
    ap.add_argument("--out", default=None)
    ap.add_argument("--upload", action="store_true", help="privat auf YouTube hochladen")
    ap.add_argument("--publish-at", default=None, help="RFC3339, z. B. 2026-10-02T16:00:00Z (geplante Veröffentlichung)")
    ap.add_argument("--dry-run", action="store_true", help="synthetisches Audio statt Lyria, keine Bild-API")
    ap.add_argument("--max-retries", type=int, default=2, help="Neuversuche pro Track bei QC-Fehler")
    args = ap.parse_args()

    concept = json.loads(Path(args.concept).read_text(encoding="utf-8"))
    out = Path(args.out or f"build/{concept['slug']}")
    for sub in ("raw", "wav", "mp3", "covers", "video", "thumbnail", "frames"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        config.GOOGLE_API_KEY = ""  # erzwingt prozedurale Bilder
    year = date.today().year
    tracks = concept["tracks"]
    total = len(tracks)
    album = concept["album"]
    genre = concept["genre"]
    bpm = int(concept["bpm"])
    log(f"Mix „{album}“: {total} Tracks, {genre}, {bpm} BPM, dry_run={args.dry_run}")

    # 1) Tracks erzeugen + QC + Mastering
    wavs, covers, frames = [], [], []
    for i, t in enumerate(tracks, 1):
        raw = out / "raw" / f"{i:02d}.mp3"
        for attempt in range(args.max_retries + 1):
            if args.dry_run:
                synthetic_track(raw, int(concept.get("minutes_per_track", 3) * 60 * (0.9 + 0.05 * (i % 3))), bpm, i)
            else:
                prompt = lyria.build_prompt(genre, bpm, concept["mood"], t["variation"], concept.get("minutes_per_track", 3))
                lyria.generate_track(prompt, raw)
            qc = audio.quality_check(raw, target_bpm=None if args.dry_run else bpm)
            log(f"Track {i:02d} „{t['title']}“: {qc.duration:.0f}s, Tempo {qc.tempo:.0f}, Stille {qc.silence_ratio:.0%}, "
                f"{qc.rms_db:.0f} dB → {'OK' if qc.ok else 'NEU: ' + qc.reason}")
            if qc.ok or args.dry_run:
                break
        wav = audio.master(raw, out / "wav" / f"{i:02d}.wav")
        wavs.append(wav)
        # Cover
        art_prompt = (concept.get("track_art_prompts") or [None] * total)[i - 1] or \
            f"{concept['art_prompt']} Variation: {t['variation']}."
        art = images.generate_art(art_prompt, "1:1")
        cover = images.make_track_cover(art, t["title"], i, album, out / "covers" / f"{i:02d}.png")
        covers.append(cover)
        frames.append(images.make_video_frame(cover, out / "frames" / f"{i:02d}.png"))
        audio.export_mp3(wav, out / "mp3" / f"{i:02d} - {config.ARTIST} - {t['title']}.mp3",
                         t["title"], album, i, total, cover, genre, year)

    # 2) Zusammenschnitt + Kapitel
    mix_wav, starts = audio.concat_wavs(wavs, out / "wav" / "mix.wav")
    total_sec = audio.probe_duration(mix_wav)
    chapter_text = metadata.chapters([t["title"] for t in tracks], starts)
    log(f"Mix gesamt {metadata.fmt_ts(total_sec)}; Kapitel:\n{chapter_text}")

    # 3) Album-Cover, Thumbnail, Video
    album_art = images.generate_art(concept["art_prompt"], "1:1", pro=True)
    images.make_album_cover(album_art, album, f"{genre} · {bpm} BPM", out / "covers" / "album_3000.png")
    thumb_art = images.generate_art(concept.get("thumbnail_prompt", concept["art_prompt"]), "16:9", pro=True)
    total_min = int(round(total_sec / 60))
    thumbs = []
    for k, headline in enumerate([concept["thumbnail_headline"], *concept.get("ab_thumbs", [])[:2]]):
        thumbs.append(images.make_thumbnail(thumb_art, headline, concept.get("thumbnail_sub", f"{bpm} BPM · {total_min} MIN"),
                                            out / "thumbnail" / f"thumb_{'ABC'[k]}.jpg"))
    mp4 = video.build_video(frames, starts, mix_wav, total_sec, out / "video" / f"{concept['slug']}.mp4")
    info = video.probe(mp4)
    log(f"Video: {mp4.name} {json.dumps(info['format'])}")

    # 4) Metadaten
    playlist_id = config.PLAYLISTS.get(concept.get("playlist", "gym"), config.PLAYLISTS["gym"])
    yt_title = concept["yt_title"]
    assert len(yt_title) <= 100, "Titel zu lang"
    desc = metadata.description(concept, chapter_text, playlist_id, total_min)
    tags = concept["tags"]
    video_url = "(wird nach Upload eingetragen)"

    # 5) Upload (privat)
    video_id = None
    if args.upload:
        from pipeline import youtube
        log("Upload auf YouTube (privat) …")
        video_id = youtube.upload_video(mp4, yt_title, desc, tags, publish_at=args.publish_at)
        video_url = f"https://youtu.be/{video_id}"
        youtube.set_thumbnail(video_id, thumbs[0])
        youtube.add_to_playlist(video_id, playlist_id)
        log(f"Hochgeladen: {video_url} (privat{', geplant ' + args.publish_at if args.publish_at else ''})")

    metadata.write_metadata(out / "metadata.txt", concept, yt_title, desc, tags, chapter_text,
                            concept.get("ab_titles", []), concept.get("ab_thumbs", []), concept.get("shorts", []), video_url)

    # 6) ZIP
    zip_path = out.parent / f"{concept['slug']}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for sub in ("mp3", "covers", "video", "thumbnail"):
            for f in sorted((out / sub).glob("*")):
                if f.suffix in (".mp3", ".png", ".jpg", ".mp4"):
                    z.write(f, f"{sub}/{f.name}")
        z.write(out / "metadata.txt", "metadata.txt")
    shutil.rmtree(out / "frames", ignore_errors=True)
    result = {"zip": str(zip_path), "video": str(mp4), "video_id": video_id, "video_url": video_url,
              "duration_sec": total_sec, "chapters": chapter_text, "title": yt_title, "thumbnails": [str(t) for t in thumbs]}
    (out / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    log(f"Fertig: {zip_path} ({zip_path.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
