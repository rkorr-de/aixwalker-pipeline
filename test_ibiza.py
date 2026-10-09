"""Testlauf Ibiza-Linie (Rolf, 09.10.2026) – NICHT öffentlich, kein YouTube, kein DistroKid, kein Gedächtnis.

Erzeugt zur Freigabe:
  • 3 echte Lyria-Tracks MIT Gesang (Original-Textzeilen), gemastert, als MP3 mit Song-Cover
  • eine Hörprobe aller 3 Tracks mit Überblendung (mix_preview.mp3)
  • 2 Hauptbild-Vorschläge (Nano Banana Pro, 4K), je mit Thumbnail 1280×720 und Album-Cover 3000×3000
    in der Schrift der Italien-Mixe (Cinzel-Versalien + Schreibschrift) plus Unterzeile „CHILLOUT DEEP HOUSE“
  • 3 Song-Cover (Nano Banana Pro)
und lädt alles nach Google Drive: AIX WALKER Mixe/_TEST Ibiza Sunset Lounge – <Album>.

Aufruf:  python test_ibiza.py            (echter Lauf, braucht GOOGLE_API_KEY + DRIVE_REFRESH_TOKEN)
         python test_ibiza.py --dry      (ohne API: Platzhalterbilder, keine Musik, kein Upload – nur Layout)
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from pipeline import audio, config, costs, images, lyria

GENRE = "Ibiza Sunset Lounge"
ALBUM = "Saffron Horizon"
MIX_MIN = 64   # nur für die Dauer-Angabe auf dem Test-Thumbnail (echter Mix ≥ 60 Min)

# Klangidentität aus Rolfs JSON / Musik-Prompt
SOUND = ("warm and atmospheric Chillout Deep House for an Ibiza sunset lounge: steady soft four-on-the-floor beat with "
         "gentle low-passed kicks and organic shakers, deep pulsating sidechained sub-bass, lush floating minor-key "
         "synthesizer pads, soft Rhodes electric piano chords, occasional filtered synth plucks and gentle guitar; "
         "warm, mesmerizing, hypnotic and deeply relaxing")
VOICE = ("soulful, breathy, ethereal female voice, background vocal snippets and rhythmic vocal chops drenched in lush "
         "reverb and delay, spatial and hypnotic, sung clearly in English with these original lyrics: ")

TRACKS = [
    {"title": "Amber Tides", "bpm": 114, "mood": "warm, floating, relaxing",
     "variation": "opener: long atmospheric pad intro, the soft kick enters after about 30 seconds, gentle and spacious",
     "lyrics": "(Ooh) Amber light on the water, hold me slow, hold me slow. (Ooh) Every wave pulls me further, "
               "let it go, let it go. Chops: slow... slow... let it go.",
     "scene": "Close view of a white canopy daybed on an Ibiza beach club at golden hour, amber sunlight glowing "
              "through flowing white drapes, two cocktail glasses on a wooden side table, relaxed guests on daybeds "
              "further back, calm sea and low orange sun."},
    {"title": "Cala Heartbeat", "bpm": 116, "mood": "warm, euphoric, groovy",
     "variation": "build: light claps, filtered synth plucks and short clean guitar licks, the groove becomes more present",
     "lyrics": "Feel it in the sand, feel it in the air, your heartbeat, my heartbeat, everywhere. (Hey, hey) "
               "Sun is going down but we're not going home, stay in the glow, you're not alone. "
               "Chops: heart-beat... every-where... (hey).",
     "scene": "Cliffside beach club terrace above a small Ibiza cove at sunset, pine trees, string lights, lounge "
              "cushions with elegant guests holding drinks, orange and pink sky reflecting on crystal-clear water."},
    {"title": "Saltwater Promises", "bpm": 118, "mood": "euphoric, mesmerizing, uplifting yet relaxed",
     "variation": "peak: full sub-bass, airy pluck arpeggio, longer sung phrase, then a long breakdown of pads and "
                  "echoing vocals before the final groove",
     "lyrics": "Saltwater promises under a violet sky, you said forever, I didn't ask why. (Ohh) Carry me higher, "
               "carry me home, into the sunset, never alone. Chops: promises... promises... (ohh)... home.",
     "scene": "Natural-wood outdoor DJ booth on a beach club deck in Ibiza at the last minutes of sunset, guests "
              "relaxing and softly dancing barefoot on the sand, pampas grass, palm silhouettes, glowing lanterns, "
              "deep pink and violet sky over the sea with the sun touching the horizon."},
]

# Zwei neue Hauptbild-Vorschläge (Beach Club mit Gästen, Rolf 09.10.2026)
MASTERS = {
    "A": ("A bustling upscale beach club on the coast of Ibiza during golden hour, seen at eye level from the sand: "
          "natural wood, thatched parasols and stylish white canopy drapes right on the shore, plush lounge seating, "
          "cushions and daybeds filled with relaxed, elegant guests, a stylish outdoor DJ booth in the mid-ground, palm "
          "trees, pampas grass and warm string lights, the sun sinking low on the horizon over the sparkling sea, calm "
          "glowing sky in the upper half."),
    "B": ("A luxury Ibiza beach club seen from a slightly raised wooden terrace at sunset: rows of white daybeds and "
          "bohemian rattan lounges along the shoreline, elegant guests in light summer outfits chatting with cocktails, "
          "a few people swaying barefoot near a thatched DJ booth, white canopy drapes moving in the breeze, string "
          "lights and lanterns just switched on, palm trees and pampas grass, the big orange sun touching the sea, "
          "golden reflections on the water, wide soft pink-orange sky in the upper half."),
}


def log(msg: str) -> None:
    print(f"[ibiza-test] {msg}", flush=True)


def estimate_usd() -> float:
    p = config.PRICES_USD
    return round(len(TRACKS) * p["lyria_track"] * 1.15 + len(MASTERS) * p["image_pro_4k"]
                 + len(TRACKS) * p["image_pro"], 2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="ohne API: nur Layout mit Platzhalterbildern")
    args = ap.parse_args()
    out = config.ROOT / "build" / "ibiza_test"
    out.mkdir(parents=True, exist_ok=True)
    if args.dry:
        config.GOOGLE_API_KEY = ""
    else:
        config.require("GOOGLE_API_KEY")
        config.require("DRIVE_REFRESH_TOKEN")
    costs.start(out / "costs.json")
    est = estimate_usd()
    log(f"Kostenvoranschlag: ca. {est:.2f} USD = {costs.usd_to_eur(est):.2f} EUR "
        f"({len(TRACKS)} Lyria-Tracks, {len(MASTERS)} Hauptbilder 4K, {len(TRACKS)} Song-Cover)")

    kw = config.THUMB_KEYWORD[GENRE]
    sub = config.THUMB_SUBLINE[GENRE]
    scale = config.THUMB_TEXT_SCALE.get(GENRE, 1.0)
    one = GENRE in config.THUMB_ONE_LINE
    style = images.style_for(GENRE)
    result = {"album": ALBUM, "genre": GENRE, "masters": {}, "tracks": []}

    # 1) Hauptbild-Vorschläge → Thumbnail + Album-Cover (aus EINEM Bild, wie bei Italien)
    for key, scene in MASTERS.items():
        log(f"Hauptbild {key} (Nano Banana Pro 4K) …")
        art = images.master_art(scene, GENRE)
        art.convert("RGB").save(out / f"master_{key}.jpg", "JPEG", quality=92)
        th = images.make_thumbnail(art, kw, ALBUM, out / f"thumbnail_{key}.jpg",
                                   duration=images.duration_label(MIX_MIN), text_scale=scale, subline=sub, one_line=one)
        al = images.make_album_cover(art, kw, ALBUM, out / f"album_3000_{key}.png", text_scale=scale,
                                     subline=sub, one_line=one)
        result["masters"][key] = {"thumbnail": str(th), "album_cover": str(al)}

    # 2) Songs: Cover + Lyria mit Gesang + Mastering + MP3
    wavs = []
    for i, t in enumerate(TRACKS, 1):
        log(f"Song-Cover {i}: {t['title']} …")
        art = images.generate_art(t["scene"], "1:1", pro=True, style=style, image_size="2K")
        cover = images.make_track_cover(art, t["title"], i, ALBUM, out / "covers" / f"{i:02d} {t['title']}.png")
        prompt = lyria.build_prompt("Chillout Deep House, Ibiza Sunset Lounge, Melodic Deep House", t["bpm"],
                                    t["mood"], t["variation"], minutes=4, sound_design=SOUND,
                                    vocals=VOICE + t["lyrics"])
        (out / "prompts").mkdir(exist_ok=True)
        (out / "prompts" / f"{i:02d} {t['title']}.txt").write_text(prompt, encoding="utf-8")
        entry = {"title": t["title"], "bpm": t["bpm"], "cover": str(cover), "prompt": prompt}
        if not args.dry:
            log(f"Lyria-Track {i}: {t['title']} ({t['bpm']} BPM, mit Gesang) …")
            raw = lyria.generate_track(prompt, out / "raw" / f"{i:02d}.mp3")
            wav = audio.master(raw, out / "wav" / f"{i:02d}.wav")
            mp3 = audio.export_mp3(wav, out / "mp3" / f"{i:02d} {t['title']}.mp3", t["title"], ALBUM, i, len(TRACKS),
                                   cover, "Deep House", date.today().year)
            entry.update({"mp3": str(mp3), "seconds": round(audio.probe_duration(mp3))})
            wavs.append(wav)
        result["tracks"].append(entry)

    files, subs = [], {}
    if wavs:
        log("Hörprobe aller Tracks mit Überblendung …")
        mixed, _ = audio.concat_wavs(wavs, out / "mix_preview.wav", crossfade_sec=6)
        prev = audio.export_mp3(mixed, out / "mix_preview.mp3", f"{ALBUM} (Test-Hörprobe)", ALBUM, 1, 1,
                                Path(result["tracks"][0]["cover"]), "Deep House", date.today().year)
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
        links = drive.upload_mix_package(f"_TEST Ibiza Sunset Lounge – {ALBUM}", files, subs)
        result["drive"] = links.get("_folder")
    (out / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"FERTIG. Kosten tatsächlich: {result['costs_usd']} USD = {result['costs_eur']} EUR · "
        f"Drive: {result.get('drive', '-')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
