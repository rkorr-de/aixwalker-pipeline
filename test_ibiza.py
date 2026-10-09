"""Testlauf Ibiza-Linie (Rolf, 09.10.2026) – NICHT öffentlich, kein YouTube, kein DistroKid, kein Gedächtnis.

Erzeugt zur Freigabe:
  • 3 echte Lyria-Tracks, fast instrumental: nur ab und zu gehauchtes Summen im Hintergrund, KEIN Text
    (Rolf 09.10. abends: Gesang war viel zu präsent); v3: deutlich langsamer, klassischer Balearic Sunset Chillout
    im Stil der Ibiza-Sunset-Bars (Café-del-Mar-Gefühl), gemastert, als MP3 mit Song-Cover
  • eine Hörprobe aller 3 Tracks mit Überblendung (mix_preview.mp3)
  • 2 Hauptbild-Vorschläge (Nano Banana Pro, 4K), je mit Thumbnail 1280×720 und Album-Cover 3000×3000
    in der Schrift der Italien-Mixe (Cinzel-Versalien + Schreibschrift) plus Unterzeile „CHILLOUT DEEP HOUSE“;
    Stimmung dunkler/wärmer (tiefer, roter Sonnenuntergang), auf Thumbnail und Album-Cover Titel oben im Himmel,
    Dauer unten rechts; alle Bilder mit kinematografischem Orange-&-Teal-Filter (v3)
  • 3 Song-Cover (Nano Banana Pro)
und lädt alles nach Google Drive: AIX WALKER Mixe/_TEST Ibiza Sunset Lounge <Version> – <Album>.

Aufruf:  python test_ibiza.py            (echter Lauf, braucht GOOGLE_API_KEY + DRIVE_REFRESH_TOKEN)
         python test_ibiza.py --dry      (ohne API: Platzhalterbilder, keine Musik, kein Upload – nur Layout)
         python test_ibiza.py --audio-von v3   (nur neue Bilder; Songs aus build/ibiza_test_v3 wiederverwenden)
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from pipeline import audio, config, costs, images, lyria

GENRE = "Ibiza Sunset Lounge"
ALBUM = "Saffron Horizon"
VERSION = "v3.1"   # v3.1: nur Bilder neu (Filter-Korrektur), Songs aus v3   # je Entwurfsrunde neu: eigener Build-Ordner, eigene Kostenzählung, eigener Drive-Ordner
MIX_MIN = 64   # nur für die Dauer-Angabe auf dem Test-Thumbnail (echter Mix ≥ 60 Min)

# Klangidentität: klassischer Balearic Sunset Chillout wie in den legendären Ibiza-Sunset-Bars (Café-del-Mar-Gefühl).
# v3 (Rolf 09.10.): deutlich langsamer und chilliger als die Deep-House-Version (114–118 BPM war zu schnell).
# Markennamen bewusst nicht im Prompt (Lyria filtert Anlehnungen an bestehende Werke).
GENRE_TAGS = "Balearic Chillout, Ibiza Sunset Chillout, Downtempo Lounge"
SOUND = ("classic Balearic sunset chillout, the timeless music of an Ibiza sunset bar as the sun sinks into the sea: "
         "slow, laid-back downtempo groove with a soft, round, low-key kick and gentle brushed percussion and light "
         "shakers, no driving four-on-the-floor, warm deep mellow bass, lush slowly evolving pads, soft Rhodes and "
         "felt piano chords, warm nylon-string Spanish guitar melodies, subtle ambient textures and distant waves; "
         "spacious, dreamy, slightly melancholic yet warm, unhurried and deeply relaxing")
# Gesang nur als Hauch im Hintergrund, kein Text (Rolf 09.10. abends: Vocals waren viel zu präsent)
VOICE = ("almost none, the track is mostly instrumental. Only now and then a soft, breathy, wordless female humming (gentle 'mmm' and airy "
         "'ooh'), placed far in the background, very low in the mix, drenched in reverb and delay like a distant "
         "whisper, never in the foreground and never carrying the melody. No lyrics, no words, no singing of text, "
         "no vocal chops, no spoken words.")

TRACKS = [
    {"title": "Amber Tides", "bpm": 90, "mood": "warm, floating, deeply relaxing",
     "variation": "opener: long atmospheric pad and guitar intro, the soft beat enters gently after about 30 seconds, "
                  "very calm and spacious",
     "scene": "Close view of a white canopy daybed on an Ibiza beach club at a late, deep sunset, red-amber light "
              "glowing through flowing white drapes, two cocktail glasses and a candle lantern on a wooden side table, "
              "relaxed guests as warm silhouettes on daybeds further back in dim surroundings, dark sea and a deep red "
              "sun touching the horizon."},
    {"title": "Cala Heartbeat", "bpm": 94, "mood": "warm, gently uplifting, laid-back",
     "variation": "soft finger snaps, a slow nylon-guitar melody and warm Rhodes chords over a relaxed, swaying groove",
     "scene": "Cliffside beach club terrace above a small Ibiza cove at a late, deep sunset, dark pine silhouettes, "
              "glowing string lights, lounge cushions with elegant guests holding drinks in warm shadow, deep red and "
              "burnt-orange sky reflecting on the darkening water."},
    {"title": "Saltwater Promises", "bpm": 92, "mood": "dreamy, mesmerizing, warm and melancholic",
     "variation": "gentle felt-piano motif and airy pads, a long floating breakdown with a faint, distant breathy "
                  "hum, then the soft groove returns",
     "scene": "Natural-wood outdoor DJ booth on a beach club deck in Ibiza in the last minutes of sunset, guests "
              "relaxing and softly dancing barefoot on the sand as warm silhouettes, pampas grass, dark palm "
              "silhouettes, glowing lanterns, a deep crimson and dark amber sky over the sea with the red sun half "
              "below the horizon."},
]

# Zwei Hauptbild-Vorschläge (Beach Club mit Gästen, Rolf 09.10.2026) – v2 dunkler und wärmer: tiefer, roter
# Sonnenuntergang, dunklere Umgebung; oberes Drittel ruhiger Himmel für den Titel
MASTERS = {
    "A": ("A bustling upscale beach club on the coast of Ibiza at a late, deep sunset, seen at eye level from the sand: "
          "natural wood, thatched parasols and stylish white canopy drapes right on the shore, plush lounge seating, "
          "cushions and daybeds filled with relaxed, elegant guests, a stylish outdoor DJ booth in the mid-ground, palm "
          "trees, pampas grass and warm string lights, the deep red sun half below the horizon over the darkening sea, "
          "the beach club already dim and moody in warm shadow, lit by lanterns and string lights, a calm glowing deep "
          "red and burnt-orange sky in the upper half."),
    "B": ("A luxury Ibiza beach club seen from a slightly raised wooden terrace at sunset: rows of white daybeds and "
          "bohemian rattan lounges along the shoreline, elegant guests in light summer outfits chatting with cocktails, "
          "a few people swaying barefoot near a thatched DJ booth, white canopy drapes moving in the breeze, string "
          "lights and lanterns glowing, dark palm silhouettes and pampas grass, the big red sun touching the sea, "
          "fiery red reflections on the darkening water, surroundings dim and warm, a wide calm crimson and dark "
          "amber sky in the upper half."),
}


def log(msg: str) -> None:
    print(f"[ibiza-test] {msg}", flush=True)


def estimate_usd(songs: bool = True) -> float:
    p = config.PRICES_USD
    return round(len(TRACKS) * p["lyria_track"] * 1.15 * songs + len(MASTERS) * p["image_pro_4k"]
                 + len(TRACKS) * p["image_pro"], 2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="ohne API: nur Layout mit Platzhalterbildern")
    ap.add_argument("--audio-von", metavar="VERSION",
                    help="keine neuen Songs: gemasterte WAVs aus build/ibiza_test_<VERSION>/wav wiederverwenden")
    args = ap.parse_args()
    audio_src = config.ROOT / "build" / f"ibiza_test_{args.audio_von}" / "wav" if args.audio_von else None
    out = config.ROOT / "build" / f"ibiza_test_{VERSION}"
    out.mkdir(parents=True, exist_ok=True)
    if args.dry:
        config.GOOGLE_API_KEY = ""
    else:
        config.require("GOOGLE_API_KEY")
        config.require("DRIVE_REFRESH_TOKEN")
    costs.start(out / "costs.json")
    est = estimate_usd(songs=audio_src is None)
    log(f"Kostenvoranschlag: ca. {est:.2f} USD = {costs.usd_to_eur(est):.2f} EUR "
        f"({0 if audio_src else len(TRACKS)} Lyria-Tracks, {len(MASTERS)} Hauptbilder 4K, {len(TRACKS)} Song-Cover)")

    kw = config.THUMB_KEYWORD[GENRE]
    sub = config.THUMB_SUBLINE[GENRE]
    scale = config.THUMB_TEXT_SCALE.get(GENRE, 1.0)
    one = GENRE in config.THUMB_ONE_LINE
    top = GENRE in config.THUMB_TITLE_TOP
    style = images.style_for(GENRE)
    result = {"album": ALBUM, "genre": GENRE, "masters": {}, "tracks": []}

    # 1) Hauptbild-Vorschläge → Thumbnail + Album-Cover (aus EINEM Bild, wie bei Italien)
    for key, scene in MASTERS.items():
        log(f"Hauptbild {key} (Nano Banana Pro 4K) …")
        art = images.master_art(scene, GENRE)
        art.convert("RGB").save(out / f"master_{key}.jpg", "JPEG", quality=92)
        th = images.make_thumbnail(art, kw, ALBUM, out / f"thumbnail_{key}.jpg",
                                   duration=images.duration_label(MIX_MIN), text_scale=scale, subline=sub, one_line=one,
                                   title_top=top)
        al = images.make_album_cover(art, kw, ALBUM, out / f"album_3000_{key}.png", text_scale=scale,
                                     subline=sub, one_line=one, title_top=top)
        result["masters"][key] = {"thumbnail": str(th), "album_cover": str(al)}

    # 2) Songs: Cover + Lyria mit Gesang + Mastering + MP3
    wavs = []
    for i, t in enumerate(TRACKS, 1):
        log(f"Song-Cover {i}: {t['title']} …")
        art = images.color_grade(images.generate_art(t["scene"], "1:1", pro=True, style=style, image_size="2K"),
                                 GENRE)
        cover = images.make_track_cover(art, t["title"], i, ALBUM, out / "covers" / f"{i:02d} {t['title']}.png")
        prompt = lyria.build_prompt(GENRE_TAGS, t["bpm"],
                                    t["mood"], t["variation"], minutes=4, sound_design=SOUND,
                                    vocals=VOICE)
        (out / "prompts").mkdir(exist_ok=True)
        (out / "prompts" / f"{i:02d} {t['title']}.txt").write_text(prompt, encoding="utf-8")
        entry = {"title": t["title"], "bpm": t["bpm"], "cover": str(cover), "prompt": prompt}
        if not args.dry:
            if audio_src:
                wav = audio_src / f"{i:02d}.wav"
                log(f"Song {i}: {t['title']} aus {wav.parent.parent.name} wiederverwendet (neues Cover) …")
            else:
                log(f"Lyria-Track {i}: {t['title']} ({t['bpm']} BPM, Balearic Chillout, Summen im Hintergrund) …")
                raw = lyria.generate_track(prompt, out / "raw" / f"{i:02d}.mp3")
                wav = audio.master(raw, out / "wav" / f"{i:02d}.wav")
            mp3 = audio.export_mp3(wav, out / "mp3" / f"{i:02d} {t['title']}.mp3", t["title"], ALBUM, i, len(TRACKS),
                                   cover, "Chillout", date.today().year)
            entry.update({"mp3": str(mp3), "seconds": round(audio.probe_duration(mp3))})
            wavs.append(wav)
        result["tracks"].append(entry)

    files, subs = [], {}
    if wavs:
        log("Hörprobe aller Tracks mit Überblendung …")
        mixed, _ = audio.concat_wavs(wavs, out / "mix_preview.wav", crossfade_sec=6)
        prev = audio.export_mp3(mixed, out / "mix_preview.mp3", f"{ALBUM} (Test-Hörprobe)", ALBUM, 1, 1,
                                Path(result["tracks"][0]["cover"]), "Chillout", date.today().year)
        files.append(prev)
        subs["mp3"] = [Path(t["mp3"]) for t in result["tracks"]]

    files += [out / f"thumbnail_{k}.jpg" for k in MASTERS] + [out / f"album_3000_{k}.png" for k in MASTERS]
    files += [out / f"master_{k}.jpg" for k in MASTERS]
    subs["covers"] = sorted((out / "covers").glob("*.png"))
    subs["prompts"] = sorted((out / "prompts").glob("*.txt"))

    led = json.loads((out / "costs.json").read_text())
    result["costs_usd"], result["costs_eur"] = led.get("usd"), led.get("eur")
    if not args.dry:
        from pipeline import drive
        log("Upload nach Google Drive …")
        links = drive.upload_mix_package(f"_TEST Ibiza Sunset Lounge {VERSION} – {ALBUM}", files, subs)
        result["drive"] = links.get("_folder")
    (out / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"FERTIG. Kosten tatsächlich: {result['costs_usd']} USD = {result['costs_eur']} EUR · "
        f"Drive: {result.get('drive', '-')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
