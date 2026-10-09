#!/usr/bin/env python3
"""Freitags-Mix der Winter-Cabin-Linie (Rolf 09.10.2026): ≥ 120 Min Cozy Lofi Ambient / Smooth Jazz als 4K-Kaminfilm.

Ablauf: Lyria-Tracks (parallel, ohne Tempoprüfung, −16 LUFS) → Mix mit Überblendungen + gemeinfreies Kaminknistern →
EIN Hauptbild 4K (Nano Banana Pro) → 3 Veo-Clips in 4K (Start = Ende = Hauptbild, automatisch geprüft) → nahtloser
Kaminfilm (pipeline/loopvideo.py) → Streaming-Upload zu YouTube ohne Videodatei auf der Platte (pipeline/streamupload.py)
→ Thumbnail C, 2 Shorts S1 v2 (15-s-Loops) → Playlist, Kommentar → Drive (ohne das lange Video) → result.json.
Kein Album-Cover, keine Track-Cover, kein DistroKid. Aufruf normalerweise über run_auto.py --genre "Cozy Winter Cabin".

  python run_cabin.py concepts/<slug>.json --out build/<slug> --upload --public --drive
  python run_cabin.py concepts/<slug>.json --out build/<slug> --dry-run      # ohne APIs, kurze Testlänge, Datei statt Upload

Abbruch → denselben Befehl erneut starten: fertige Tracks (raw/), Hauptbild und geprüfte Clips werden wiederverwendet.
"""
import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from PIL import Image

from pipeline import audio, cabin_art, config, costs, images, loopvideo, lyria, metadata, monthly, shorts

CRACKLE = config.ASSETS / "ambience" / "fireplace_crackle_loop.m4a"
SHORT_SEC = 15


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] [cabin] {msg}", flush=True)


# ---------------------------------------------------------------- Musik
def produce_track(i: int, t: dict, concept: dict, out: Path, dry: bool, lufs: float, retries: int = 2) -> Path:
    raw = out / "raw" / f"{i:02d}.mp3"
    for attempt in range(retries + 1):
        if raw.exists() and raw.stat().st_size > 50_000 and attempt == 0:
            pass
        elif dry:
            from run_mix import synthetic_track
            synthetic_track(raw, 50, int(concept["bpm"]), i)
        else:
            g = concept["genre"]
            prompt = lyria.build_prompt(config.LYRIA_GENRE_TAGS.get(g, g), int(concept["bpm"]), concept["mood"],
                                        t["variation"], 3, concept.get("sound_design", ""))
            lyria.generate_track(prompt, raw)
        qc = audio.quality_check(raw, target_bpm=None, min_sec=30 if dry else 90)   # ruhige Musik: keine Tempoprüfung
        log(f"Track {i:02d} „{t['title']}“: {qc.duration:.0f}s, Stille {qc.silence_ratio:.0%} → {'OK' if qc.ok else 'NEU: ' + qc.reason}")
        if qc.ok or dry:
            break
        raw.unlink(missing_ok=True)
        costs.count("lyria_retries")
    return audio.master(raw, out / "wav" / f"{i:02d}.wav", lufs=lufs)


def make_music(concept: dict, out: Path, dry: bool, fmt: dict, workers: int) -> tuple[list[dict], list[Path]]:
    tracks = list(concept["tracks"])
    extra = list(concept.get("extra_tracks") or [])
    min_sec = (3 if dry else fmt["min_minutes"]) * 60
    if dry:
        tracks = tracks[:4]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        wavs = list(ex.map(lambda a: produce_track(a[0] + 1, a[1], concept, out, dry, fmt["lufs"]), enumerate(tracks)))

    def length():
        return sum(audio.probe_duration(w) for w in wavs) - 1.5 * max(0, len(wavs) - 1)

    while length() < min_sec and len(tracks) < fmt["max_tracks"]:
        k = len(tracks) - len(concept["tracks"])
        t = dict(extra[k]) if k < len(extra) else {
            "title": f"Winter Ember {k - len(extra) + 1:02d}",
            "variation": f"completely new composition, distinct melody and chord progression (unique seed {k}), "
                         f"consistent with the mix: {concept.get('mood', '')}"}
        tracks.append(t)
        log(f"Mix bisher {length() / 60:.1f} Min < {min_sec / 60:.0f} Min → Zusatz-Track {len(tracks):02d} „{t['title']}“")
        wavs.append(produce_track(len(tracks), t, concept, out, dry, fmt["lufs"]))
    return tracks, wavs


# ---------------------------------------------------------------- Bild + Kaminfilm-Clips
def master_frame(concept: dict, out: Path, dry: bool) -> Image.Image:
    p = out / "img" / "frame_4k.png"
    if p.exists():
        return Image.open(p).convert("RGB")
    p.parent.mkdir(parents=True, exist_ok=True)
    if dry:
        art = images.procedural_art("16:9")
    else:
        art = images.generate_art(concept["thumbnail_prompt"], "16:9", pro=True,
                                  style=images.style_for(concept["genre"]), image_size="4K")
    frame = cabin_art.fire_right(loopvideo.frame_16x9(art))   # Kamin immer rechts → Thumbnail-Text immer oben links
    frame.save(p)
    frame.save(out / "img" / "master.jpg", "JPEG", quality=92)
    return frame


def _static_clip(frame_png: Path, dst: Path) -> Path:
    """Dry-Run: 8-s-Clip aus dem Standbild (mit leichtem Rauschen, damit die Prüfung Bewegung sieht)."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(frame_png), "-t", "8", "-r", "24",
                    "-vf", "noise=alls=8:allf=t", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    str(dst)], check=True)
    return dst


def make_clips(frame: Image.Image, out: Path, n: int, dry: bool) -> list[Path]:
    """n Veo-Clips; jeder wird geprüft, ein durchgefallener einmal neu erzeugt. Mind. 2 gute Clips nötig."""
    d = out / "clips"
    d.mkdir(parents=True, exist_ok=True)
    names = "ABCDEFGH"[:n]

    def one(name: str) -> Path | None:
        p = d / f"{name}.mp4"
        for attempt in range(2):
            if not (p.exists() and attempt == 0):
                if dry:
                    _static_clip(out / "img" / "frame_4k.png", p)
                else:
                    try:
                        loopvideo.generate_clip(frame, p)
                    except Exception as e:  # noqa: BLE001
                        log(f"Clip {name}: Veo-Fehler {str(e)[:200]}")
                        p.unlink(missing_ok=True)
                        continue
            qc = loopvideo.check_clip(p)
            log(f"Clip {name}: {json.dumps(qc)}")
            if qc["ok"] or dry:
                return p
            p.rename(d / f"{name}_abgelehnt_{attempt}.mp4")
        return None

    with ThreadPoolExecutor(max_workers=n) as ex:
        clips = [c for c in ex.map(one, names) if c]
    if len(clips) < 2:
        raise RuntimeError(f"nur {len(clips)} gültige Kaminfilm-Clips – mindestens 2 nötig")
    return clips


def short_center(frame: Image.Image, k: int) -> float:
    """Bildmitte (0–1) des senkrechten Ausschnitts. Rolf 09.10.: Shorts müssen sich sichtbar unterscheiden –
    Short 1 = Kamin, Short 2 = Fensterfront mit Schneefall, Sofa und Kerzentisch (gut 0,4 Bildbreiten vom Feuer weg)."""
    fx = cabin_art.fire_x(frame)
    if k % 2 == 0:
        return fx
    return min(max(fx - 0.36 if fx >= 0.5 else fx + 0.36, 0.16), 0.84)


def make_short(clips: list[Path], k: int, frame: Image.Image, final_wav: Path, start: float, question: str,
               out: Path) -> Path:
    """15-s-Short S1 v2: zwei Segmente (X→Y→X) ergeben eine nahtlose Schleife; senkrechter Ausschnitt (siehe
    short_center: Kamin bzw. Fenster/Sofa)."""
    x, y = clips[k % len(clips)], clips[(k + 1) % len(clips)]
    loop4k = out / "shorts" / f"loop_{k + 1}.mp4"
    loopvideo.build_segment([(x, y), (y, x)], loop4k)
    overlay = cabin_art.short_overlay(question, out / "shorts" / f"overlay_{k + 1}.png")
    cw = round(loopvideo.H * 9 / 16)
    cx = int(min(max(short_center(frame, k) * loopvideo.W - cw / 2, 0), loopvideo.W - cw))
    dst = out / "shorts" / f"short_{k + 1}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(loop4k), "-i", str(overlay), "-ss", f"{start:.2f}",
                    "-t", str(SHORT_SEC), "-i", str(final_wav), "-filter_complex",
                    f"[0:v]crop={cw}:{loopvideo.H}:{cx}:0,scale=1080:1920:flags=lanczos,eq=gamma=1.12:saturation=1.12[v];"
                    "[v][1:v]overlay=0:0[o]", "-map", "[o]", "-map", "2:a",
                    "-af", f"afade=t=in:d=0.4,afade=t=out:st={SHORT_SEC - 0.6}:d=0.6", "-c:v", "libx264", "-crf", "18",
                    "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", str(SHORT_SEC),
                    "-movflags", "+faststart", str(dst)], check=True)
    loop4k.unlink(missing_ok=True)
    return dst


# ---------------------------------------------------------------- Texte
def short_texts(concept: dict, question: str, video_url: str) -> tuple[str, str, list[str]]:
    title = f"Cozy Winter Cabin ❄️🔥 {question} #shorts"[:100]
    desc = (f"{question} 🔥❄️\nThe full {concept['album']} fireplace film in 4K with relaxing music: {video_url}\n\n"
            f"Cozy Winter Cabin · Relaxing Fireplace Chillout 4K by {config.ARTIST}\n"
            "#shorts #cozycabin #fireplace #winter #AixWalker")
    tags = ["cozy winter cabin", "fireplace", "cozy cabin", "snow", "winter ambience", "4k", "shorts", "aixwalker"]
    return title, desc, tags


def write_metadata(path: Path, title: str, desc: str, tags: list[str], chapter_text: str, concept: dict,
                   short_list: list[dict]) -> None:
    lines = ["TITEL", title, "", "BESCHREIBUNG", desc, "", "TAGS", ", ".join(tags), "", "KAPITEL", chapter_text, "",
             "ANGEPINNTER KOMMENTAR", concept.get("pinned_comment", ""), "", "COMMUNITY-BEITRAG",
             metadata.community_post(concept, "(Link zum Video)"), "", "SHORTS"]
    lines += [f"- {s['title']} → {s.get('url', '(nicht hochgeladen)')}" for s in short_list]
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------- Ablauf
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("concept")
    ap.add_argument("--out", default=None)
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--public", action="store_true")
    ap.add_argument("--drive", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=3, help="gleichzeitige Lyria-Aufrufe")
    args = ap.parse_args()
    concept = json.loads(Path(args.concept).read_text(encoding="utf-8"))
    out = Path(args.out or f"build/{concept['slug']}")
    for sub in ("raw", "wav", "mp3", "img", "clips", "shorts", "thumbnail", "video", "work"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        config.GOOGLE_API_KEY = ""
    genre, album = concept["genre"], concept["album"].strip()
    fmt = config.LINE_FORMAT[genre]
    costs.start(out / "costs.json")
    log(f"Mix „{album}“ ({genre}, {concept['bpm']} BPM), Ziel ≥ {fmt['min_minutes']} Min, dry_run={args.dry_run}")

    # 1) Bild + Clips parallel zur Musik starten (Veo braucht ca. 6 Min je Clip)
    frame = master_frame(concept, out, args.dry_run)
    log(f"Hauptbild {frame.size[0]}×{frame.size[1]}")
    with ThreadPoolExecutor(max_workers=1) as bg:
        clips_future = bg.submit(make_clips, frame, out, fmt["veo_clips"], args.dry_run)
        tracks, wavs = make_music(concept, out, args.dry_run, fmt, args.workers)
        clips = clips_future.result()
    log(f"{len(tracks)} Tracks, {len(clips)} Kaminfilm-Clips: {[c.name for c in clips]}")

    # 2) Mix, Kapitel, Knistern, MP3s (mit Hauptbild als Cover-Tag, für den 2-Wochen-/Monats-Zusammenschnitt)
    mix, starts = monthly.join_tracks(wavs, out / "wav" / "mix.flac", xf=1.5)
    total_sec = audio.probe_duration(mix)
    total_min = int(round(total_sec / 60))
    concept["total_min"] = total_min
    metadata.fill_concept(concept, total_min)
    chapter_text = metadata.chapters([t["title"] for t in tracks], starts)
    final_wav = loopvideo.mix_with_crackle(mix, CRACKLE, out / "wav" / "final.wav")
    aac = loopvideo.encode_audio(final_wav, out / "work" / "audio.m4a")
    cover = out / "img" / "cover.jpg"
    images.crop_aspect(frame, 1, 1).resize((1400, 1400), Image.LANCZOS).save(cover, "JPEG", quality=90)
    for i, (t, w) in enumerate(zip(tracks, wavs), 1):
        audio.export_mp3(w, out / "mp3" / f"{i:02d} - {config.ARTIST} - {t['title']}.mp3", t["title"], album, i,
                         len(tracks), cover, genre, date.today().year)
    log(f"Mix {metadata.fmt_ts(total_sec)}, {len(tracks)} Tracks, Knistern darunter")

    # 3) Kaminfilm vorbereiten (Segmente), Thumbnail
    playlist_file = loopvideo.prepare_video(clips, total_sec, out / "work", log=log)
    thumb = cabin_art.make_thumbnail(frame, images.duration_label(total_min), out / "thumbnail" / "thumb_C.jpg")

    # 4) Texte
    from pipeline.planner import unify_title
    title = unify_title(concept["yt_title"], album, config.THUMB_KEYWORD.get(genre), max_len=100)[:100]
    playlist_id = config.PLAYLISTS.get("cabin") or "PLAYLIST"
    if args.upload:
        from pipeline import youtube
        playlist_id = youtube.playlist_for("cabin")
        log(f"Playlist „{config.PLAYLIST_TITLES['cabin'][0]}“: {playlist_id}")
    desc = metadata.description(concept, chapter_text, playlist_id, total_min)
    desc = desc.replace("mastered for headphones and speakers",
                        "4K fireplace film with real crackling fire sounds, mastered quietly for background listening")
    tags = concept["tags"]

    # 5) Hauptvideo: Upload als Strom (keine Datei) bzw. im Dry-Run als Datei
    privacy = "public" if args.public else "private"
    video_id, video_url, comment_id = None, "(nicht hochgeladen)", None
    if args.upload:
        from pipeline import streamupload, youtube
        log(f"Streaming-Upload Kaminfilm 4K ({privacy}) …")
        up = streamupload.upload_stream(loopvideo.mux_command(playlist_file, aac), title, desc, tags, privacy=privacy,
                                        log=log)
        video_id = up["video_id"]
        video_url = f"https://youtu.be/{video_id}"
        log(f"Hochgeladen: {video_url} ({up['bytes'] / 1e9:.1f} GB in {up['seconds'] / 60:.0f} Min)")
        youtube.set_thumbnail(video_id, thumb)
        youtube.add_to_playlist(video_id, playlist_id)
        if args.public and concept.get("pinned_comment"):
            try:
                comment_id = youtube.post_comment(video_id, concept["pinned_comment"])
            except Exception as e:  # noqa: BLE001
                log(f"Kommentar nicht gepostet: {str(e)[:160]}")
    else:
        mp4 = out / "video" / f"{concept['slug']}.mp4"
        subprocess.run(loopvideo.mux_command(playlist_file, aac, str(mp4)), check=True)
        log(f"Dry-Run/ohne Upload: Video als Datei {mp4} ({mp4.stat().st_size / 1e6:.0f} MB)")

    # 6) Shorts (S1 v2): 15-s-Schleifen, Frage wechselt
    short_list = []
    passages = shorts.find_passages(final_wav, starts, total_sec, SHORT_SEC, config.SHORTS_COUNT,
                                    min_gap_sec=60 if args.dry_run else 600)
    q0 = (date.today().toordinal() * 2) % len(cabin_art.SHORT_QUESTIONS)
    for k, p in enumerate(passages):
        q = cabin_art.SHORT_QUESTIONS[(q0 + k) % len(cabin_art.SHORT_QUESTIONS)]
        clip = make_short(clips, k, frame, final_wav, p["start"], q, out)
        s_title, s_desc, s_tags = short_texts(concept, q, video_url)
        entry = {"start": p["start"], "end": p["start"] + SHORT_SEC, "track_title": tracks[p["track_index"]]["title"],
                 "overlay": q, "title": s_title, "file": str(clip)}
        if args.upload:
            from pipeline import youtube
            entry["video_id"] = youtube.upload_video(clip, s_title, s_desc, s_tags, privacy=privacy)
            entry["url"] = f"https://youtube.com/shorts/{entry['video_id']}"
            log(f"Short {k + 1} hochgeladen ({privacy}): {entry['url']}")
        short_list.append(entry)

    write_metadata(out / "metadata.txt", title, desc, tags, chapter_text, concept, short_list)

    # 7) Drive: nur die Projektdateien (MP3s, Hauptbild, Loop-Clips, Thumbnail, Metadaten, Shorts) – nicht das Video
    drive_links = {}
    if args.drive:
        try:
            from pipeline import drive
            folder = f"{date.today().isoformat()} – {album} ({genre}, 4K)"
            drive_links = drive.upload_mix_package(folder, [thumb, out / "img" / "master.jpg", out / "metadata.txt"],
                                                   {"mp3": sorted((out / "mp3").glob("*.mp3")), "loop_clips": clips,
                                                    "shorts": [Path(s["file"]) for s in short_list]})
            log(f"Drive: {drive_links['_folder']}")
        except Exception as e:  # noqa: BLE001
            log(f"Drive-Ablage fehlgeschlagen: {e}")
            drive_links = {"error": str(e)}

    cost_line = costs.report()
    log(cost_line)
    result = {"cost_usd": costs.total_usd(), "cost_eur": costs.usd_to_eur(costs.total_usd()), "cost_report": cost_line,
              "video_id": video_id, "video_url": video_url, "duration_sec": total_sec, "duration_min": total_min,
              "tracks": len(tracks), "chapters": chapter_text, "title": title, "description": desc, "tags": tags,
              "privacy": privacy if args.upload else None, "comment_id": comment_id, "thumbnails": [str(thumb)],
              "shorts": short_list, "drive": drive_links, "clips": [c.name for c in clips], "format": "cabin-4k"}
    (out / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    log(f"Fertig: {total_min} Min, Video {video_url}, Shorts {len(short_list)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
