#!/usr/bin/env python3
"""Baut aus einem Konzept (JSON) das komplette Mix-Paket, lädt Mix + 2 Shorts privat auf YouTube und legt das
Paket auf Google Drive ab.

Aufruf:
  python run_mix.py concept.json --out build/<slug> [--upload] [--drive] [--dry-run] [--publish-at ...]

Konzept-JSON (Beispiel in concepts/example.json):
{
  "slug": "iron-focus-vol1",
  "album": "Iron Focus Vol. 1",
  "genre": "Slow Gym Beats",
  "bpm": 80,
  "mood": "dark, heavy, hypnotic",
  "playlist": "gym",
  "minutes_per_track": 5,            # Wunschlänge je Track (Lyria liefert ca. 3–6 Min)
  "min_minutes": 60,                 # Mix wird so lange mit Zusatz-Tracks verlängert, bis erreicht
  "tracks": [ {"title": "Beneath the Bar", "variation": "deep 808, sparse hats"}, ... ],
  "extra_tracks": [{"title": "...", "variation": "..."}, ...],  # Reserve, falls Mindestlänge nicht erreicht
  "art_prompt": "...", "thumbnail_prompt": "...",
  "thumbnail_headline": "IRON FOCUS", "thumbnail_sub": "80 BPM · 60 MIN",
  "yt_title": "...", "hook": "...", "intro": "...", "use_line": "...", "cta_question": "...",
  "hashtags": [...], "tags": [...], "ab_titles": [...], "ab_thumbs": [...],
  "short_overlays": ["the drop before the set", "tunnel vision"],   # Hook-Texte für die 2 Shorts (max. 4 Wörter)
  "short_titles": ["...", "..."],                                   # optional
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

from pipeline import audio, config, costs, images, lyria, metadata, shorts, video


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


def produce_track(i: int, t: dict, concept: dict, out: Path, args, bpm: int) -> Path:
    """Erzeugt (oder nutzt) raw/NN.mp3, prüft Qualität, liefert gemasterte WAV."""
    raw = out / "raw" / f"{i:02d}.mp3"
    minutes = concept.get("minutes_per_track", config.DEFAULT_MINUTES_PER_TRACK)
    for attempt in range(args.max_retries + 1):
        if raw.exists() and raw.stat().st_size > 50_000 and attempt == 0 and not args.dry_run:
            log(f"Track {i:02d}: vorhandene Datei wird wiederverwendet")
        elif args.dry_run:
            synthetic_track(raw, int(minutes * 60 * (0.9 + 0.05 * (i % 3))), bpm, i)
        else:
            prompt = lyria.build_prompt(concept["genre"], bpm, concept["mood"], t["variation"], minutes)
            lyria.generate_track(prompt, raw)
        qc = audio.quality_check(raw, target_bpm=None if args.dry_run else bpm)
        log(f"Track {i:02d} „{t['title']}“: {qc.duration:.0f}s, Tempo {qc.tempo:.0f}, Stille {qc.silence_ratio:.0%}, "
            f"{qc.rms_db:.0f} dB → {'OK' if qc.ok else 'NEU: ' + qc.reason}")
        if qc.ok or args.dry_run:
            break
        raw.unlink(missing_ok=True)
    return audio.master(raw, out / "wav" / f"{i:02d}.wav")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("concept")
    ap.add_argument("--out", default=None)
    ap.add_argument("--upload", action="store_true", help="Mix + Shorts privat auf YouTube hochladen")
    ap.add_argument("--drive", action="store_true", help="Paket in Google Drive ablegen (Ordner je Mix)")
    ap.add_argument("--no-shorts", action="store_true", help="keine Shorts erzeugen")
    ap.add_argument("--publish-at", default=None, help="RFC3339, z. B. 2026-10-02T16:00:00Z (geplante Veröffentlichung)")
    ap.add_argument("--dry-run", action="store_true", help="synthetisches Audio statt Lyria, keine Bild-API")
    ap.add_argument("--max-retries", type=int, default=2, help="Neuversuche pro Track bei QC-Fehler")
    args = ap.parse_args()

    concept = json.loads(Path(args.concept).read_text(encoding="utf-8"))
    out = Path(args.out or f"build/{concept['slug']}")
    for sub in ("raw", "wav", "mp3", "covers", "video", "thumbnail", "frames", "shorts"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        config.GOOGLE_API_KEY = ""  # erzwingt prozedurale Bilder
    year = date.today().year
    tracks = list(concept["tracks"])
    album = concept["album"]
    genre = concept["genre"]
    bpm = int(concept["bpm"])
    min_sec = float(concept.get("min_minutes", config.MIN_MIX_MINUTES)) * 60
    log(f"Mix „{album}“: {len(tracks)} Tracks geplant, {genre}, {bpm} BPM, Ziel ≥ {min_sec / 60:.0f} Min, dry_run={args.dry_run}")
    costs.start(out / "costs.json")
    est = costs.estimate(concept)
    log(f"Kostenvoranschlag: {est['usd']:.2f} $ ≈ {est['eur']:.2f} € ({est['tracks_expected']} Tracks erwartet)")

    # 1) Tracks erzeugen + QC + Mastering; bei Bedarf Zusatz-Tracks bis zur Mindestlänge
    wavs: list[Path] = []
    extra = list(concept.get("extra_tracks") or [])   # Reserve-Tracks (Titel + Variation) für die Mindestlänge
    n0 = len(tracks)
    i = 0
    while True:
        if i < len(tracks):
            t = tracks[i]
        else:
            total_now = sum(audio.probe_duration(w) for w in wavs) - 1.5 * max(0, len(wavs) - 1)
            if total_now >= min_sec:
                break
            k = i - n0
            if k < len(extra):
                t = dict(extra[k])
            else:
                src = tracks[(k - len(extra)) % n0]
                t = {"title": f"{src['title']} (Reprise)", "variation": f"{src['variation']}, alternate take, new melodic motif"}
            tracks.append(t)
            log(f"Mix bisher {total_now / 60:.1f} Min < {min_sec / 60:.0f} Min → Zusatz-Track {i + 1:02d} „{t['title']}“")
        i += 1
        wavs.append(produce_track(i, t, concept, out, args, bpm))
        if i >= len(tracks):
            total_now = sum(audio.probe_duration(w) for w in wavs) - 1.5 * (len(wavs) - 1)
            if total_now >= min_sec:
                break
            if i >= 40:
                log("Abbruch der Verlängerung: 40 Tracks erreicht")
                break
    total = len(tracks)

    # 1b) Cover, MP3s, Video-Frames (nach der Zählung, damit TRCK n/total stimmt)
    covers, frames = [], []
    for i, t in enumerate(tracks, 1):
        art_prompt = (concept.get("track_art_prompts") or [None] * total)[i - 1] or \
            f"{concept['art_prompt']} Variation: {t['variation']}."
        art = images.generate_art(art_prompt, "1:1")
        cover = images.make_track_cover(art, t["title"], i, album, out / "covers" / f"{i:02d}.png")
        covers.append(cover)
        frames.append(images.make_video_frame(cover, out / "frames" / f"{i:02d}.png"))
        audio.export_mp3(wavs[i - 1], out / "mp3" / f"{i:02d} - {config.ARTIST} - {t['title']}.mp3",
                         t["title"], album, i, total, cover, genre, year)
    log(f"{total} Tracks fertig (MP3 + Cover)")

    # 2) Zusammenschnitt + Kapitel
    mix_wav, starts = audio.concat_wavs(wavs, out / "wav" / "mix.wav")
    total_sec = audio.probe_duration(mix_wav)
    total_min = int(round(total_sec / 60))
    concept["total_min"] = total_min
    chapter_text = metadata.chapters([t["title"] for t in tracks], starts)
    log(f"Mix gesamt {metadata.fmt_ts(total_sec)}; Kapitel:\n{chapter_text}")

    # 3) Album-Cover, Thumbnail, Video
    album_art = images.generate_art(concept["art_prompt"], "1:1", pro=True)
    images.make_album_cover(album_art, album, f"{genre} · {bpm} BPM", out / "covers" / "album_3000.png")
    thumb_art = images.generate_art(concept.get("thumbnail_prompt", concept["art_prompt"]), "16:9", pro=True)
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

    # 5) Upload Mix (privat)
    video_id = None
    if args.upload:
        from pipeline import youtube
        log("Upload Mix auf YouTube (privat) …")
        video_id = youtube.upload_video(mp4, yt_title, desc, tags, publish_at=args.publish_at)
        video_url = f"https://youtu.be/{video_id}"
        youtube.set_thumbnail(video_id, thumbs[0])
        youtube.add_to_playlist(video_id, playlist_id)
        log(f"Hochgeladen: {video_url} (privat{', geplant ' + args.publish_at if args.publish_at else ''})")

    # 6) Shorts: beste Passagen → 9:16-Clips → Upload (privat)
    short_list: list[dict] = []
    if not args.no_shorts:
        overlays = concept.get("short_overlays") or [s.get("overlay", "feel this") for s in concept.get("shorts", [])]
        overlays = (overlays + ["feel the drop", "lock in"])[: config.SHORTS_COUNT]
        passages = shorts.find_passages(mix_wav, starts, total_sec, config.SHORT_CLIP_SEC, config.SHORTS_COUNT)
        for k, p in enumerate(passages):
            t_title = tracks[p["track_index"]]["title"]
            frame = shorts.make_short_frame(thumb_art, covers[p["track_index"]], overlays[k], t_title,
                                            out / "shorts" / f"short_{k + 1}_frame.png")
            clip = shorts.build_short(frame, mix_wav, p["start"], p["end"], out / "shorts" / f"short_{k + 1}.mp4")
            s_title, s_desc, s_tags = shorts.short_metadata(concept, k, p, t_title, overlays[k], video_url)
            entry = {**p, "overlay": overlays[k], "track_title": t_title, "file": str(clip), "title": s_title}
            if args.upload:
                from pipeline import youtube
                sid = youtube.upload_video(clip, s_title, s_desc, s_tags)
                try:
                    youtube.set_thumbnail(sid, frame)
                except Exception as e:  # noqa: BLE001
                    log(f"Short-Thumbnail nicht gesetzt: {e}")
                entry["video_id"], entry["url"] = sid, f"https://youtube.com/shorts/{sid}"
                log(f"Short {k + 1} hochgeladen (privat): {entry['url']}")
            short_list.append(entry)
        log(f"Shorts: {len(short_list)} Clips ({config.SHORT_CLIP_SEC}s) aus den stärksten Passagen")

    shorts_text = shorts.write_shorts_section(short_list) if short_list else "(keine)"
    metadata.write_metadata(out / "metadata.txt", concept, yt_title, desc, tags, chapter_text,
                            concept.get("ab_titles", []), concept.get("ab_thumbs", []), concept.get("shorts", []),
                            video_url, shorts_text)

    # 7) ZIP
    zip_path = out.parent / f"{concept['slug']}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for sub in ("mp3", "covers", "thumbnail"):
            for f in sorted((out / sub).glob("*")):
                if f.suffix in (".mp3", ".png", ".jpg"):
                    z.write(f, f"{sub}/{f.name}")
        z.write(out / "metadata.txt", "metadata.txt")
    shutil.rmtree(out / "frames", ignore_errors=True)

    # 8) Google Drive: neuer Ordner je Mix
    drive_links = {}
    if args.drive:
        try:
            from pipeline import drive
            folder = f"{date.today().isoformat()} – {album} ({genre}, {bpm} BPM)"
            files = [zip_path, out / "covers" / "album_3000.png", out / "metadata.txt", thumbs[0],
                     *[Path(s["file"]) for s in short_list]]
            drive_links = drive.upload_mix_package(folder, files)
            log(f"Drive: {drive_links['_folder']}")
        except Exception as e:  # noqa: BLE001
            log(f"Drive-Ablage fehlgeschlagen (DRIVE_REFRESH_TOKEN fehlt/ungültig → python auth_youtube.py url drive): {e}")
            drive_links = {"error": str(e)}

    cost_line = costs.report()
    log(cost_line)
    result = {"cost_usd": costs.total_usd(), "cost_eur": costs.usd_to_eur(costs.total_usd()), "cost_report": cost_line,
              "cost_estimate_usd": est["usd"], "zip": str(zip_path), "zip_mb": round(zip_path.stat().st_size / 1e6, 1), "video": str(mp4),
              "video_mb": round(mp4.stat().st_size / 1e6, 1), "video_id": video_id, "video_url": video_url,
              "duration_sec": total_sec, "duration_min": total_min, "tracks": total, "chapters": chapter_text,
              "title": yt_title, "thumbnails": [str(t) for t in thumbs], "shorts": short_list, "drive": drive_links}
    (out / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    log(f"Fertig: {zip_path} ({zip_path.stat().st_size / 1e6:.1f} MB, ohne Video); Video: {mp4} "
        f"({mp4.stat().st_size / 1e6:.1f} MB, {total_min} Min); Shorts: {len(short_list)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
