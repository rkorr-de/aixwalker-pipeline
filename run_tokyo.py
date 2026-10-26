#!/usr/bin/env python3
"""Tokyo Work Lounge (Rolf 17.10.2026): kompletter Mix mit 4K-Standbildvideo, Spruch am Anfang, Schwarzblenden bei jedem
Songwechsel, Short (9:16 aus dem Hauptbild) und Thumbnail. Upload privat, Aufnahmeort Tokyo, Playlist.

  python run_tokyo.py --room shinjuku-sky-loft --upload                 # echter Lauf (Cloud mit API-Schlüsseln)
  python run_tokyo.py --room shinjuku-sky-loft --dry-run                # ohne APIs, Kurzfassung (Test der Blenden)

Abbruch → denselben Befehl erneut starten: fertige Tracks, Hauptbild und Video-Teile werden wiederverwendet.
"""
import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "concepts"))

from pipeline import audio, config, costs, images, loopvideo, lyria, metadata, monthly  # noqa: E402

import genre_test_tokyo_lounge_v2 as v  # noqa: E402  (PROMPT, text_layer, make_thumb)

W, H = 3840, 2160
FPS = 15
XF = 1.5                       # Überblendung der Songs (Sekunden)
MIN_MIN = 60                   # Ziel: mindestens eine Stunde
MAX_TRACKS = 30
LUFS = -16.0
ROOM_DRIVE_FOLDER = "GENRE-TEST Tokyo Work Lounge v3"

TITLE_BASE = "🎧 Tokyo Work Lounge | Slow Jazz for Deep Work & Coding"
TITLE = f"{TITLE_BASE} 🎷"   # wird in main() mit der laufenden Nummer („- Vol. N“) überschrieben
# Ordnername im Drive muss auf "(Genre, BPM)" enden (Format aller Mix-Ordner, der DistroKid-Lauf liest das Genre daraus)
GENRE_LABEL = "Slow Jazz"
BPM_LABEL = 70           # nur Beschriftung des Ordners, DistroKid fragt kein BPM ab
REUSE_SRC_MP3 = {"id": None}   # Drive-Ordner "mp3" des Quell-Mixes, wenn --reuse-music
PLAYLIST = ("Tokyo Work Lounge · Slow Jazz for Work and Coding",
            "Tokyo Work Lounge: slow, quiet jazz for deep work, coding, studying and productivity. A cozy Tokyo loft at night, "
            "a breathy tenor saxophone, felt piano and a warm sub-bass. By Aix Walker.")
TAGS = ["tokyo work lounge", "slow jazz for work and coding", "productivity music", "focus and productivity",
        "tokyo lounge jazz", "jazz for work", "coding music", "deep focus jazz", "study jazz", "quiet jazz",
        "work music instrumental", "background jazz for coding", "lofi jazz", "tokyo loft", "aix walker"]
HASHTAGS = "#deepwork #productivity #codingmusic #focusmusic #tokyo"
# Pin-Kommentar und Community-Post schreibt Claude bei JEDEM Mix neu (Rolf 18.10.2026), nicht aus einer Konstante.
# Der Kommentar wird nach "Tokyo freigeben" von Claude selbst unter den Mix geschrieben (Rolf pinnt ihn), der Post
# wird von Rolf gepostet; beide Texte stehen in der Mail (send_tokyo_mail.py --pin ... --community ...).

# (Zeilen des Spruchs, Hinweis auf die Musik steht immer in den letzten Zeilen)
QUOTES = [
    ["Start with the smallest task.", "My tracks will carry you", "the rest of the way."],
    ["Silence your phone.", "Let my music hold the room", "while you work."],
    ["One calm hour beats a distracted day.", "My tracks will keep the pace."],
    ["Slow down to focus.", "These tracks will be", "your quiet company."],
    ["Finish one thing well.", "My music stays softly beside you."],
    ["A quiet room, a clear mind.", "My tracks will do the rest."],
    ["Take a breath, then begin.", "My music will keep you steady."],
    ["Whatever you build tonight,", "my tracks will support you."],
]

def _norm(s: str) -> str:
    return " ".join(s.lower().replace("’", "'").split())


# Mitte des Schreibtischs im 16:9-Hauptbild (Anteil der Breite, 0 = links, 1 = rechts) – Standard für das Album-Cover-Fenster.
DESK_X = {"nakameguro-evening-loft": 0.72, "shinjuku-sky-loft": 0.70, "azabu-rain-loft": 0.25,
          "daikanyama-garden-loft": 0.80}


def make_album_cover(art: Image.Image, desk_x: float, size: int = 3000) -> Image.Image:
    """Album-Cover 1:1 (Rolf 19.10.2026): VOLLE Bildhöhe des Hauptbilds, das Fenster wird waagerecht so gelegt, dass der
    Schreibtisch (Mitte bei desk_x) zu sehen ist; Text wie im Thumbnail (v.text_layer)."""
    w, h = art.size
    x0 = int(round(min(max(desk_x * w - h / 2, 0), max(w - h, 0))))
    sq = art.convert("RGB").crop((x0, 0, x0 + min(h, w), h)).resize((size, size), Image.LANCZOS).convert("RGBA")
    return Image.alpha_composite(sq, v.text_layer(size, size, 0.05, 0.085, 0.043, 0.032, center=0.48)).convert("RGB")


VOL_FLOOR = 9   # Rolf 25.10.2026: heute ist Vol. 9 (Vol. 8 war doppelt vergeben). Nie darunter; bei Bedarf anheben.


def youtube_vols() -> list[int]:
    """Alle „Vol. N“ in den Titeln der eigenen Tokyo-Videos auf dem Kanal (auch privat; Rolf korrigiert Titel manchmal von Hand)."""
    import re
    from pipeline import youtube
    yt = youtube.service()
    up = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    vols, token = [], None
    for _ in range(6):                                   # bis zu 300 jüngste Uploads
        r = yt.playlistItems().list(part="snippet", playlistId=up, maxResults=50, pageToken=token).execute()
        for it in r.get("items", []):
            t = it["snippet"]["title"]
            if "Tokyo Work Lounge" in t and "Mega" not in t:
                m = re.search(r"Vol\.\s*(\d+)", t)
                if m:
                    vols.append(int(m.group(1)))
        token = r.get("nextPageToken")
        if not token:
            break
    return vols


def next_vol() -> int:
    """Laufende Nummer im Titel (Rolf 19.10.2026, verschärft 25.10.2026 nach doppeltem „Vol. 8“): höchste Nummer aus
    1) Gedächtnis „tokyo“ (Feld vol), 2) den Titeln der Tokyo-Videos auf YouTube, 3) VOL_FLOOR − 1, plus 1.
    Ist weder Gedächtnis noch YouTube lesbar, bricht der Lauf ab (lieber kein Mix als eine falsche Nummer)."""
    mem_vols, yt_vols, ok = [], [], 0
    try:
        from pipeline import memory
        for e in memory.load().get("tokyo", []):
            mem_vols.append(int(e.get("vol") or 0))
        ok += 1
    except Exception as e:  # noqa: BLE001
        log(f"Gedächtnis für Titelnummer nicht lesbar: {str(e)[:120]}")
    try:
        yt_vols = youtube_vols()
        ok += 1
    except Exception as e:  # noqa: BLE001
        log(f"YouTube-Titel für Titelnummer nicht lesbar: {str(e)[:120]}")
    if not ok:
        raise SystemExit("ABBRUCH: Titelnummer (Vol.) nicht prüfbar – weder Gedächtnis noch YouTube lesbar")
    vol = max([VOL_FLOOR - 1, *mem_vols, *yt_vols]) + 1
    log(f"Titelnummer: Vol. {vol} (Gedächtnis max {max(mem_vols or [0])}, YouTube max {max(yt_vols or [0])}, Untergrenze {VOL_FLOOR})")
    return vol


def used_quotes() -> set[str]:
    """Alle bisher verwendeten Sprüche (feste Liste + Gedächtnis „tokyo“), normalisiert."""
    used = {_norm(" ".join(q)) for q in QUOTES}
    try:
        from pipeline import memory
        for e in memory.load().get("tokyo", []):
            if e.get("quote"):
                used.add(_norm(e["quote"]))
    except Exception as e:  # noqa: BLE001
        log(f"Gedächtnis für Spruch-Prüfung nicht lesbar: {str(e)[:120]}")
    return used


def parse_quote(text: str, allow_used: bool = False) -> list[str]:
    """Prüft den neuen Spruch (Rolfs Kriterien): Englisch, 2–3 Zeilen, je Zeile höchstens 42 Zeichen, die letzte Zeile bezieht sich
    auf „my tracks / my music“, keine Zeit-/Längenangaben, noch nie verwendet."""
    lines = [l.strip() for l in text.split("|") if l.strip()]
    if not 2 <= len(lines) <= 3:
        raise SystemExit(f"Spruch muss 2 oder 3 Zeilen haben (mit | getrennt), hat {len(lines)}")
    if any(len(l) > 42 for l in lines):
        raise SystemExit("Spruch: jede Zeile höchstens 42 Zeichen")
    low = " ".join(lines).lower()
    if not ("my tracks" in low or "my music" in low or "these tracks" in low):
        raise SystemExit("Spruch muss sich auf die Musik beziehen (my tracks / my music / these tracks)")
    import re as _re
    if _re.search(r"\d|hour|minute|\bmin\b|second|\blong\b|full[- ]length", low):
        raise SystemExit("Spruch: keine Zeit-/Längenangaben")
    if not allow_used and _norm(" ".join(lines)) in used_quotes():
        raise SystemExit("Spruch wurde schon verwendet – bitte einen neuen ausdenken")
    return lines


TRACK_NAMES = ["Lantern Hours", "Quiet Circuit", "Slow Neon", "Paper Window", "Midnight Tab", "Soft Compile", "Tea Steam",
               "Late Commit", "Shoji Glow", "Low Bandwidth", "Evening Syntax", "Still Desk", "Warm Cache", "Rain on Glass",
               "Cedar Shelf", "Gentle Deploy", "Amber Standby", "Idle Cursor", "Velvet Terminal", "Nightshift Loop",
               "Calm Refactor", "Tatami Light", "Quiet Merge", "Last Train Home", "Open Floor", "Slow Release",
               "Warm Thread", "Hush Mode", "Dim Dashboard", "Lamp and Rain"]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] [tokyo] {msg}", flush=True)


def run(cmd: list, **kw) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], check=True, capture_output=True, text=True, **kw)


# ---------------------------------------------------------------- Musik
def produce_track(i: int, out: Path, dry: bool) -> Path:
    raw = out / "raw" / f"{i:02d}.mp3"
    for attempt in range(3):
        if not (raw.exists() and raw.stat().st_size > 50_000):
            if dry:
                from run_mix import synthetic_track
                synthetic_track(raw, 40, 70, i)
            else:
                lyria.generate_track(v.PROMPT, raw)   # Rolfs Prompt wörtlich
        qc = audio.quality_check(raw, target_bpm=None, min_sec=30 if dry else 90)
        log(f"Track {i:02d}: {qc.duration:.0f}s, Stille {qc.silence_ratio:.0%} → {'OK' if qc.ok else 'NEU: ' + qc.reason}")
        if qc.ok or dry:
            break
        raw.unlink(missing_ok=True)
        costs.count("lyria_retries")
    return audio.master(raw, out / "wav" / f"{i:02d}.wav", lufs=LUFS)


def make_music(out: Path, dry: bool, workers: int) -> list[Path]:
    min_sec = (2 if dry else MIN_MIN) * 60
    n0 = 3 if dry else 22
    with ThreadPoolExecutor(max_workers=workers) as ex:
        wavs = list(ex.map(lambda i: produce_track(i, out, dry), range(1, n0 + 1)))

    def length() -> float:
        return sum(audio.probe_duration(w) for w in wavs) - XF * max(0, len(wavs) - 1)

    while length() < min_sec and len(wavs) < MAX_TRACKS:
        wavs.append(produce_track(len(wavs) + 1, out, dry))
        log(f"Mix bisher {length() / 60:.1f} Min")
    return wavs


# ---------------------------------------------------------------- Bild
def fetch_main_image(room: str, out: Path, dry: bool, folder: str = ROOM_DRIVE_FOLDER, fname: str = "") -> Image.Image:
    """Das von Rolf gewählte Bild (PNG aus dem Drive-Ordner der Testläufe), auf 3840×2160 gebracht. Fehlt es, wird neu erzeugt."""
    png = out / "img" / "main_src.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    if not png.exists():
        got = False
        if dry:
            src = HERE / "concepts" / "genre-test-tokyo-lounge-v3" / "bilder" / f"{room}.jpg"
            Image.open(src).convert("RGB").save(png)
            got = True
        else:
            try:
                from pipeline import drive
                svc = drive.service()
                q = (f"name = '{folder}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false")
                folders = svc.files().list(q=q, fields="files(id,modifiedTime)", orderBy="modifiedTime desc").execute()["files"]
                for f in folders:
                    subs = [s for s in drive.list_children(svc, f["id"], folders=True) if s["name"] == "bilder"]
                    if not subs:
                        continue
                    pics = [c for c in drive.list_children(svc, subs[0]["id"], folders=False) if c["name"] == (fname or f"{room}.png")]
                    if pics:
                        pics.sort(key=lambda c: c.get("createdTime", ""), reverse=True)   # bei mehreren gleichnamigen: die NEUESTE
                        drive.download(svc, pics[0]["id"], png)
                        log(f"Bild aus Drive geladen: {pics[0]['name']} (id {pics[0]['id']}, erstellt {pics[0].get('createdTime')})")
                        got = True
                        break
            except Exception as e:  # noqa: BLE001
                log(f"Drive-Bild nicht verfügbar: {str(e)[:200]}")
        if not got:
            import genre_test_tokyo_rooms_v3 as r
            log("Bild wird neu erzeugt (4K)")
            art = images.generate_art(r.ROOMS[room], "16:9", pro=True, style=r.STYLE, image_size="4K")
            art.convert("RGB").save(png)
    art = Image.open(png).convert("RGB")
    log(f"Quellbild {art.size[0]}×{art.size[1]}")
    if art.size != (W, H):
        art = images._cover_crop(art, W, H) if hasattr(images, "_cover_crop") else art.resize((W, H), Image.LANCZOS)
        if art.size[0] < W:                       # nur beim Hochrechnen nachschärfen
            art = art.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    art.save(out / "img" / "main_4k.png")
    art.save(out / "img" / "master.jpg", "JPEG", quality=92)
    return art


# ---------------------------------------------------------------- Neuer Raum pro Mix (Rolf 19.10.2026)
FIGURINE = ("Easter egg: somewhere in the room, on the desk, a shelf, the dining table or a sideboard (a different spot in each room, never in the exact center), "
            "stands ONE small collectible manga-style anime figurine of a young woman, at most 15 cm tall (clearly tiny compared to the monitors and the chair, about the size "
            "of a tea caddy): long silver-lavender ponytail, large round white headphones, an oversized soft mint-green hoodie, small sneakers, a calm dreamy pose, "
            "painted matte PVC look on a small round black base. ")

def room_check_text(var: dict | None = None) -> str:
    """Prompt der automatischen Bildprüfung. Mit `var` (Variation, concepts/tokyo_variation.py) wird die Stuhlfarbe (cognac ODER schwarz)
    und – wenn verlangt – das schwarz-weiße Tuschebild geprüft; ohne `var` (Rolfs eigene Bilder) genügt irgendein Bürostuhl."""
    import tokyo_variation as tv
    chair = tv.check_text(var) if var else ("\"chair\" (true if an office chair stands at or near the desk), \"art_ink\" (true if a large framed abstract "
                                           "black-and-white ink painting hangs on a wall; not required), ")
    ink_ok = "" if not var or not var.get("ink") else ", and art_ink is true"
    return ("You are a strict quality checker for a photorealistic interior image. Answer ONLY with compact JSON, keys: "
            "\"desk\" (true if a complete computer workplace with exactly two monitors side by side is clearly visible somewhere in the room; it does not have to be in the foreground, it may be in the rear part of the loft), "
            "\"desk_x\" (horizontal center of that desk as a number from 0.0 at the left edge to 1.0 at the right edge), "
            "\"person_visible\" (true if a person is visible anywhere, even blurred or from behind), "
            "\"person_x\" (horizontal center of that person from 0.0 at the left edge to 1.0 at the right edge, or null if no person), "
            + chair +
            "\"figurine\" (true if one small manga-style female figurine, clearly under about 15 cm tall, is visible anywhere in the room), "
            "\"keyboard_mouse\" (true if a keyboard AND a computer mouse are visible on the desk in front of the monitors; they may look small if the desk is far away), "
            "\"text\" (true if any readable text, logo or watermark is visible), "
            "\"person_sharp\" (true if a person is shown sharp or with a visible face; false if no person or only a blurred back view), "
            "\"daylight\" (true if it looks like daytime, dusk or sunset, a window shows a bright or blue sky, or the whole image has a cold blue tint; small cyan LED accents and a glowing network rack are allowed), "
            "\"artifacts\" (true if there are obvious deformed objects, extra limbs or broken geometry), "
            f"\"ok\" (true only if desk, chair, person_visible, keyboard_mouse and figurine are true and text, person_sharp, daylight and artifacts are all false{ink_ok}).")


NEW_ROOM_CHECK = room_check_text()


def check_room_image(img: Image.Image, var: dict | None = None) -> dict | None:
    """Automatische Prüfung des neuen Raumbilds mit dem Bildverständnis-Modell. None = Prüfung nicht möglich (gilt als nicht bestanden)."""
    import base64
    import io
    import requests
    if not config.GOOGLE_API_KEY:
        return None
    buf = io.BytesIO()
    img.convert("RGB").resize((1536, 864), Image.LANCZOS).save(buf, "JPEG", quality=88)
    body = {"contents": [{"parts": [{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}},
                                    {"text": room_check_text(var)}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    for model in (config.TEXT_MODEL, config.TEXT_MODEL_FALLBACK):
        try:
            r = requests.post(f"{config.GEMINI_BASE}/models/{model}:generateContent",
                              headers={"x-goog-api-key": config.GOOGLE_API_KEY}, json=body, timeout=120)
            if r.status_code != 200:
                log(f"Bildprüfung {model}: HTTP {r.status_code}")
                continue
            res = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
            return res if isinstance(res, dict) else None
        except Exception as e:  # noqa: BLE001
            log(f"Bildprüfung {model} fehlgeschlagen: {str(e)[:160]}")
    return None


LAST_VARIATION: dict = {}   # Variation des zuletzt erzeugten neuen Raums (für result.json und Gedächtnis)


def tokyo_history() -> list[dict]:
    try:
        from pipeline import memory
        return list(memory.load().get("tokyo", []))
    except Exception as e:  # noqa: BLE001
        log(f"Gedächtnis für Raum-Variation nicht lesbar: {str(e)[:120]}")
        return []


# Rolf 23.10.2026: gilt bei JEDEM Tokyo-Bildprompt für die Person (Schreibtisch und Fenster, Frau und Mann)
ANATOMY = (" Use for the person always perfect anatomy, detailed hands, correct fingers, accurate human anatomy, "
           "beautifully detailed feet, flawless hands, highly detailed hands. ")


def build_room_prompt(slug: str, scene_file: str, side: str, person: str, choice: dict | None = None):
    """Baut Variation und komplettes Bildprompt für einen neuen Raum (ohne Bild-Erzeugung). Liefert (prompt, style, var, scene, person)."""
    import genre_test_tokyo_rooms_v3 as r
    scene = Path(scene_file).read_text(encoding="utf-8").strip()
    if len(scene) < 80 or len(scene) > 900:
        raise SystemExit("Szenentext muss 80–900 Zeichen lang sein (neuer Ort: Fenster/Ausblick, Materialien, Stimmung).")
    if "tokyo" not in scene.lower():
        raise SystemExit("Der Szenentext muss einen Ort in Tokyo nennen (Stadtteil, z. B. Daikanyama, Kagurazaka, Asakusa).")
    import tokyo_variation as tv
    import re as _re
    day = _re.search(r"\b(daylight|sunlight|sunny|sunrise|sunset|dawn|morning|noon|afternoon|golden hour|blue hour|dusk|twilight|blue sky)\b", scene, _re.I)
    if day:
        raise SystemExit(f"Der Szenentext nennt „{day.group(0)}“ – es muss eine reine Nachtszene sein (kein Tageslicht, keine Dämmerung). Bitte Szenentext ändern.")
    ch = choice or {}
    var = tv.choose(tokyo_history(), slug, ch.get("desk_pos", "auto"), ch.get("chair", "auto"), ch.get("sofa", "auto"), ch.get("art", "auto"),
                    ch.get("person_place", "auto"), person)
    if person == "auto":
        person = var["gender"]
    LAST_VARIATION.clear()
    LAST_VARIATION.update(var)
    log(f"Raum-Variation: {var}")
    import re
    keep = [x for x in re.split(r"(?<=[.!?])\s+", scene) if not re.search(r"\b(sofa|couch|desk|chair|armchair|painting|artwork|wall art|canvas|print)s?\b", x, re.I)]
    if len(keep) < len(re.split(r"(?<=[.!?])\s+", scene)) and len(" ".join(keep)) >= 80:   # Sofa/Schreibtisch/Stuhl/Wandbild legt die Variation fest
        log("Szenentext: Sätze über Sofa/Schreibtisch/Stuhl/Wandbild entfernt (die Variation legt sie fest)")
        scene = " ".join(keep)
    parts = tv.apply(var, side, r)
    prompt = r.INTRO + parts["desk"] + parts["cozy"] + (parts.get("person") or r.PERSON[person]).rstrip() + ANATOMY + FIGURINE + parts["art"] + scene
    return prompt, parts["style"], var, scene, person


def make_new_room(slug: str, scene_file: str, side: str, person: str, out: Path, max_tries: int = 3,
                  choice: dict | None = None):
    """Erzeugt für diesen Mix einen NEUEN Raum (Ort/Szene von Claude ausgedacht, `scene_file`), 4K, mit automatischer Prüfung.
    Liefert (Bild, Schreibtisch-Mitte 0–1, Person-Mitte 0–1 oder None) oder (None, None, None), wenn nach max_tries kein Bild alle Kriterien erfüllt."""
    prompt, style_, var, scene, person = build_room_prompt(slug, scene_file, side, person, choice)
    parts = {"style": style_}
    for i in range(1, max_tries + 1):
        art = images.generate_art(prompt, "16:9", pro=True, style=parts["style"], image_size="4K").convert("RGB")
        if art.size[0] < 2500:
            log(f"Neuer Raum Versuch {i}: nur {art.size}, verworfen")
            continue
        res = check_room_image(art, var)
        log(f"Neuer Raum Versuch {i}: Prüfung {res}")
        if res and res.get("ok") is True:
            dx = res.get("desk_x")
            dx = float(dx) if isinstance(dx, (int, float)) and 0.05 <= float(dx) <= 0.95 else (0.28 if side == "left" else 0.72)
            px = res.get("person_x")
            px = float(px) if isinstance(px, (int, float)) and 0.0 <= float(px) <= 1.0 else None
            png = out / "img" / "main_src.png"
            png.parent.mkdir(parents=True, exist_ok=True)
            art.save(png)
            (out / "img" / "neuer_raum.json").write_text(json.dumps({"slug": slug, "side": side, "person": person, "scene": scene,
                                                                      "check": res, "desk_x": dx, "person_x": px, "tries": i, "variation": var, "prompt": prompt}, indent=2, ensure_ascii=False))
            try:   # Bild für spätere Verwendung in Drive ablegen (bilder/<slug>.png)
                from pipeline import drive
                named = out / "img" / f"{slug}.png"
                art.save(named)
                drive.upload_mix_package(ROOM_DRIVE_FOLDER, [], {"bilder": [named]})
            except Exception as e:  # noqa: BLE001
                log(f"Raumbild nicht in Drive abgelegt: {str(e)[:160]}")
            return art, dx, px
    return None, None, None


# ---------------------------------------------------------------- Spruch (Video-Anfang)
def quote_frame(lines: list[str], dst: Path) -> Path:
    """Schwarzes 4K-Bild mit dem Spruch in Cinzel (cremeweiß, in Anführungszeichen) und darunter klein AIX WALKER."""
    img = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(img)
    F = config.ASSETS / "fonts" / "Cinzel.ttf"
    size = 112
    texts = [l.upper() for l in lines]
    texts[0] = "“" + texts[0]
    texts[-1] = texts[-1] + "”"
    while True:
        f = images._font(F, size, "Regular")
        tr = int(size * 0.14)
        widths = [images._tracked_width(d, t, f, tr) for t in texts]
        if max(widths) <= W * 0.78 or size <= 40:
            break
        size -= 4
    lh = int(size * 1.75)
    block = lh * len(texts) + int(size * 1.9)
    y = (H - block) // 2
    for t, w_ in zip(texts, widths):
        images._draw_tracked(d, ((W - w_) // 2, y), t, f, (255, 246, 228), tr)
        y += lh
    f2 = images._font(F, int(size * 0.34), "Regular")
    tr2 = int(size * 0.34 * 0.5)
    t2 = "AIX WALKER"
    w2 = images._tracked_width(d, t2, f2, tr2)
    images._draw_tracked(d, ((W - w2) // 2, y + int(size * 0.5)), t2, f2, (222, 170, 110), tr2)
    img.save(dst)
    return dst


# ---------------------------------------------------------------- Video aus Segmenten
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS), "-g", str(FPS * 10),
       "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-an"]


def seg(src: Path, dst: Path, frames: int, vf: str = "") -> Path:
    if dst.exists() and dst.stat().st_size > 1000:
        return dst
    chain = ("scale=in_range=pc:out_range=tv:out_color_matrix=bt709," + vf).rstrip(",")
    run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", FPS, "-i", src, "-vf", chain, "-frames:v", frames,
         *ENC, "-tune", "stillimage", dst])
    return dst


def fr(sec: float) -> int:
    return max(1, round(sec * FPS))


def build_video(main: Path, qpng: Path, starts: list[float], total: float, work: Path, log=log) -> Path:
    """Zeitlinie: 1,5 s Schwarz → Spruch blendet ein (2 s), steht 4,5 s, blendet aus (2 s) → 1 s Schwarz → Hauptbild blendet in 6 s ein
    und bleibt → bei jedem Songwechsel ca. 2 s zu Schwarz, 0,5 s schwarz, 3 s zurück → letzte 10 s zu Schwarz.
    Jedes Teil wird einzeln kodiert und danach ohne Neukodierung zusammengehängt."""
    work.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    total_fr = fr(total)
    pos = 0                                 # Bildnummer, bis zu der das Video fertig ist

    intro = seg(qpng, work / "intro.mp4", fr(11.0), "fade=t=in:st=1.5:d=2,fade=t=out:st=8.0:d=2")
    parts.append(intro)
    pos += fr(11.0)
    fadein = seg(main, work / "fadein.mp4", fr(6), "fade=t=in:st=0:d=6")
    parts.append(fadein)
    pos += fr(6)

    holds: dict[int, Path] = {}

    def hold(n: int) -> list[Path]:
        """n Bilder Standbild; große Stücke aus einem wiederverwendeten 40-s-Teil."""
        out_parts = []
        chunk = fr(40)
        while n >= chunk * 2:
            if chunk not in holds:
                holds[chunk] = seg(main, work / f"hold_{chunk}.mp4", chunk)
            out_parts.append(holds[chunk])
            n -= chunk
        if n > 0:
            if n not in holds:
                holds[n] = seg(main, work / f"hold_{n}.mp4", n)
            out_parts.append(holds[n])
        return out_parts

    out_fr, black_fr, in_fr = fr(2.0), fr(0.5), fr(3.0)
    dip_fr = out_fr + black_fr + in_fr
    end_fr = fr(10.0)
    end_start = total_fr - end_fr
    dips = []
    for s in starts[1:]:
        a = fr(s - 1.25)                    # Beginn der Ausblendung (Mitte der Überblendung der Songs)
        if a >= pos and a + dip_fr < end_start - fr(5):
            dips.append(a)
    n_dip = 0
    for a in dips:
        parts += hold(a - pos)
        n_dip += 1
        parts.append(seg(main, work / "dip_out.mp4", out_fr + black_fr, f"fade=t=out:st=0:d=2"))
        parts.append(seg(main, work / "dip_in.mp4", in_fr, "fade=t=in:st=0:d=3"))
        pos = a + dip_fr
    parts += hold(end_start - pos)
    parts.append(seg(main, work / "end_out.mp4", end_fr, "fade=t=out:st=0:d=10"))
    log(f"Video-Teile: {len(parts)}, Schwarzblenden bei Songwechseln: {n_dip}")
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    out = work / "video_noaudio.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out])
    return out


# ---------------------------------------------------------------- Short (9:16 aus dem Hauptbild)
def short_text_layers(lines: list[str], w: int = 1080, h: int = 1920) -> tuple[list[Image.Image], list[tuple[int, int]], int]:
    """Zentrierter Spruch: feine goldene Linie, Aussage groß in Cinzel (cremeweiß), Musik-Bezug in Gold, darunter klein ein
    Hinweis auf den Mix (ohne Zeit-/Längenangabe); weicher dunkler Verlauf dahinter."""
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    spots: list[tuple[int, int]] = []     # Mitte (x, y) jeder Zeile bzw. des Hinweises: dort laufen vorher die drei Punkte
    layers = [lay]                       # 0 = Verlauf, danach je Element eine Ebene (Linie, Zeilen, Hinweis)

    def new_layer() -> ImageDraw.ImageDraw:
        l = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        layers.append(l)
        return ImageDraw.Draw(l)

    F = config.ASSETS / "fonts" / "Cinzel.ttf"
    texts = [l.upper() for l in lines]
    size = 70
    while True:
        f = images._font(F, size, "Regular")
        tr = int(size * 0.10)
        widths = [images._tracked_width(d, t, f, tr) for t in texts]
        if max(widths) <= w * 0.86 or size <= 30:
            break
        size -= 2
    lh = int(size * 1.7)
    cta_lines = ["FULL TOKYO WORK LOUNGE MIX", "ON THE CHANNEL"]
    ssz = int(size * 0.62)
    while True:
        small = images._font(F, ssz, "Regular")
        ctr = int(ssz * 0.20)
        cws = [images._tracked_width(d, t, small, ctr) for t in cta_lines]
        if max(cws) <= w * 0.86 or ssz <= 20:
            break
        ssz -= 2
    block = int(size * 1.0) + lh * len(texts) + int(size * 0.90) + int(ssz * 1.6) * len(cta_lines) + int(size * 0.5)
    cy = int(h * 0.50)
    half = block * 1.35
    for yy in range(h):
        a = int(215 * max(0.0, 1 - abs(yy - cy) / half) ** 1.1)
        if a:
            d.line([(0, yy), (w, yy)], fill=(8, 5, 3, a))
    y = cy - block // 2
    new_layer().line([((w - 140) // 2, y), ((w + 140) // 2, y)], fill=(222, 170, 110, 255), width=3)
    y += int(size * 1.0)
    for i, (t, w_) in enumerate(zip(texts, widths)):
        col = (255, 246, 228) if i < len(texts) - 1 or len(texts) == 1 else (232, 190, 130)
        bb = d.textbbox((0, 0), "A", font=f)
        spots.append((w // 2, y + (bb[1] + bb[3]) // 2))
        images._draw_tracked(new_layer(), ((w - w_) // 2, y), t, f, col, tr)
        y += lh
    y += int(size * 0.90)
    dc = new_layer()                      # Hinweis auf den Mix: beide Zeilen auf einer Ebene
    bb = d.textbbox((0, 0), "A", font=small)
    spots.append((w // 2, y + (bb[1] + bb[3]) // 2))
    for t, w_ in zip(cta_lines, cws):
        images._draw_tracked(dc, ((w - w_) // 2, y), t, small, (245, 232, 208), ctr)
        y += int(ssz * 1.6)
    return layers, spots, size


SHORT_TOP_TEXT = ["Slow Jazz", "for Deep Work & Coding"]   # Rolf 20.10.2026: steht im oberen Drittel über die GANZE Länge des Shorts


def short_top_layer(w: int = 1080, h: int = 1920) -> Image.Image:
    """Dauerhafte Zeile im oberen Drittel (Mitte bei ca. 21 % der Höhe, unterhalb der Oberfläche von Reels/TikTok/Shorts):
    Cinzel, cremeweiß/Gold, mit weichem dunklem Verlauf dahinter, damit sie auf jedem Bildausschnitt lesbar bleibt."""
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for yy in range(int(h * 0.42)):
        a = int(150 * (1 - yy / (h * 0.42)) ** 1.3)
        if a:
            d.line([(0, yy), (w, yy)], fill=(8, 5, 3, a))
    F = config.ASSETS / "fonts" / "Cinzel.ttf"
    texts = [t.upper() for t in SHORT_TOP_TEXT]
    size = 58
    while True:
        f = images._font(F, size, "Regular")
        tr = int(size * 0.14)
        widths = [images._tracked_width(d, t, f, tr) for t in texts]
        if max(widths) <= w * 0.86 or size <= 24:
            break
        size -= 2
    lh = int(size * 1.55)
    y = int(h * 0.21) - lh
    for i, (t, w_) in enumerate(zip(texts, widths)):
        col = (232, 190, 130) if i == 0 else (255, 246, 228)
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        images._draw_tracked(ImageDraw.Draw(sh), ((w - w_) // 2 + 2, y + 3), t, f, (0, 0, 0, 170), tr)
        lay.alpha_composite(sh)
        images._draw_tracked(d, ((w - w_) // 2, y), t, f, col, tr)
        y += lh
    return lay


def short_center(desk_x: float, person_x: float | None) -> float:
    """Mitte des Short-Ausschnitts (0–1 von links): zwischen Person und Schreibtisch, der Schreibtisch bleibt sicher im Bild.
    Der Ausschnitt ist 31,6 % der Bildbreite breit (Halbbreite 0,158)."""
    if person_x is None:
        return desk_x
    c = (desk_x + person_x) / 2
    if abs(c - desk_x) > 0.118:                      # Schreibtischmitte muss mit Rand im Ausschnitt bleiben
        c = desk_x + (0.118 if c > desk_x else -0.118)
    return min(max(c, 0.17), 0.83)


SHORT_CHECK = ("These are 3 frames from a vertical video of a cozy Tokyo home office, taken at the start, middle and end of a slow camera pan. "
               "Answer ONLY with compact JSON, keys: \"desk\" (true if in ALL 3 frames a desk with at least one computer monitor is clearly visible), "
               "\"keyboard_mouse\" (true if in ALL 3 frames a keyboard or a mouse is visible on the desk), "
               "\"person\" (true if in ALL 3 frames a person is at least partly visible, even small, blurred or from behind), "
               "\"person_side\" (\"left\" or \"right\": on which side of the frames the person would be, based on the room layout, if not visible), "
               "\"ok\" (true only if desk and person are both true).")


def check_short_frames(short: Path, tmp: Path) -> dict | None:
    """Prüft den fertigen Short: Standbilder bei Anfang/Mitte/Ende, Bildverständnis-Modell. None = Prüfung nicht möglich."""
    import base64
    import io
    import requests
    if not config.GOOGLE_API_KEY:
        return None
    frames = []
    for k, t in enumerate((1.0, 10.0, 18.5)):
        f = tmp / f"short_frame_{k}.jpg"
        run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", short, "-frames:v", "1", "-vf", "scale=540:960", f])
        frames.append(Image.open(f).convert("RGB"))
    m = Image.new("RGB", (1620, 960))
    for k, fr in enumerate(frames):
        m.paste(fr, (k * 540, 0))
    m.save(tmp / "short_check.jpg", quality=88)
    buf = io.BytesIO()
    m.save(buf, "JPEG", quality=88)
    body = {"contents": [{"parts": [{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}},
                                    {"text": SHORT_CHECK}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    for model in (config.TEXT_MODEL, config.TEXT_MODEL_FALLBACK):
        try:
            r = requests.post(f"{config.GEMINI_BASE}/models/{model}:generateContent",
                              headers={"x-goog-api-key": config.GOOGLE_API_KEY}, json=body, timeout=120)
            if r.status_code != 200:
                log(f"Short-Prüfung {model}: HTTP {r.status_code}")
                continue
            res = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
            return res if isinstance(res, dict) else None
        except Exception as e:  # noqa: BLE001
            log(f"Short-Prüfung {model} fehlgeschlagen: {str(e)[:160]}")
    return None


def make_short_checked(art: Image.Image, lines: list[str], audio_in: Path, start: float, out: Path, center: float,
                       person_x: float | None = None, tries: int = 3, **kw) -> tuple[Path, dict | None]:
    """Short bauen und prüfen (Schreibtisch UND Person im Schwenk, Rolf 19.10.2026). Bei Misserfolg Ausschnitt verschieben und neu bauen (nur ffmpeg, kostet nichts)."""
    res = None
    for i in range(1, tries + 1):
        short = make_short(art, lines, audio_in, start, out, desk_x=center, **kw)
        res = check_short_frames(short, out)
        log(f"Short Versuch {i} (Ausschnittmitte {center:.2f}): Prüfung {res}")
        if res is None or res.get("ok") is True:
            break
        side = res.get("person_side")
        if res.get("desk") is not True and res.get("person") is True:
            center += -0.05 if (person_x is not None and person_x > center) or side == "right" else 0.05   # zum Schreibtisch zurück
        else:
            center += -0.06 if (person_x is not None and person_x < center) or (person_x is None and side == "left") else 0.06  # zur Person
        center = min(max(center, 0.17), 0.83)
    (out / "short_check.json").write_text(json.dumps({"center": round(center, 3), "result": res}, ensure_ascii=False, indent=2))
    return short, res


def make_short(main: Image.Image, lines: list[str], final_audio: Path, start: float, out: Path, sec: int = 20,
               xf: float = 2.0, desk_x: float = 0.70) -> Path:
    """Short als nahtlose Schleife (Rolf 17.10.2026: nicht ein-/ausblenden, soll sich unbemerkt wiederholen).
    Bild: Ausschnitt 9:16 mit der kompletten Bildhöhe (1215×2160), die Kamerafahrt läuft als Cosinus und endet exakt am Anfang.
    Text: baut sich Zeile für Zeile auf und löst sich kurz vor dem Ende weich auf (Bild bleibt durchgehend sichtbar).
    Ton: Ausschnitt, dessen Ende (xf Sekunden) in den Anfang überblendet wird, damit die Wiederholung nicht hörbar ist."""
    out.mkdir(parents=True, exist_ok=True)
    cw = round(H * 9 / 16)
    base = out / "short_base.png"
    main.save(base)
    layers, spots, fsize = short_text_layers(lines)
    r = max(4, int(fsize * 0.085))
    dot = Image.new("RGBA", (2 * r, 2 * r), (0, 0, 0, 0))
    ImageDraw.Draw(dot).ellipse([0, 0, 2 * r - 1, 2 * r - 1], fill=(232, 190, 130, 120))
    dot_path = out / "short_dot.png"
    dot.save(dot_path)
    gap = int(fsize * 0.50)
    paths = []
    for i, l in enumerate(layers):
        pth = out / f"short_text_{i}.png"
        l.save(pth)
        paths.append(pth)
    # Rolf 19.10.2026: Der Schwenk zeigt IMMER den Schreibtisch und die Person (zumindest zum Teil) → Ausschnitt um die Schreibtischmitte
    x0 = int(min(max(desk_x * W - cw / 2 - 55, 0), W - cw - 110))
    dst = out / "short.mp4"
    n_el = len(layers)
    # Aufbau über die ganze Länge (Rolf 17.10.: nicht alles am Anfang): Verlauf 0,3 s, Linie 0,6 s, Zeilen bei 1,2 / 5,2 / 9,2 s, Hinweis auf den Mix bei 12,3 s; Auflösen in den letzten 1,5 s
    t0 = [0.3, 0.6] + [1.2 + 4.0 * k for k in range(n_el - 3)] + [1.2 + 4.0 * (n_el - 3) - 0.9]
    t_out = sec - 1.6
    cmd = ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", 25, "-t", sec, "-i", base]
    for pth in paths:
        cmd += ["-loop", "1", "-framerate", 25, "-t", sec, "-i", pth]
    cmd += ["-loop", "1", "-framerate", 25, "-t", sec, "-i", dot_path]
    cmd += ["-ss", f"{start:.2f}", "-t", sec + xf, "-i", final_audio]
    top_path = out / "short_top.png"
    short_top_layer().save(top_path)
    cmd += ["-loop", "1", "-framerate", 25, "-t", sec, "-i", top_path]       # dauerhafte Zeile oben, ohne Ein-/Ausblenden (nahtlose Schleife)
    fc = (f"[0:v]crop=w={cw}:h={H}:x='{x0}+110*(1-cos(2*PI*t/{sec}))/2':y=0,scale=1080:1920:flags=lanczos[b0];")
    for i in range(n_el):
        dur = 1.2
        fc += (f"[{i + 1}:v]format=rgba,fade=t=in:st={t0[i]:.2f}:d={dur}:alpha=1,"
               f"fade=t=out:st={t_out:.2f}:d=1.4:alpha=1[t{i}];[b{i}][t{i}]overlay=0:0[b{i + 1}];")
    # laufende Punkte "..." an der Stelle des nächsten Textes, solange er noch nicht da ist (Neugier: es kommt mehr)
    n_sp = len(spots)
    n_dots = 3 * max(1, n_sp - 2)
    di = n_el + 1                                  # Eingang des Punkt-Bildes
    fc += f"[{di}:v]format=rgba,split={n_dots}" + "".join(f"[dd{k}]" for k in range(n_dots)) + ";"
    prev = f"b{n_el}"
    k = 0
    P = 1.2                                        # Dauer eines Punkte-Zyklus
    for si, (cx, cy) in enumerate(spots):
        if si == 0 or si == n_sp - 1:
            continue                               # keine Punkte vor der ersten Zeile und vor dem Mix-Hinweis (Rolf 18.10.)
        el = 2 + si                                # Ebene dieses Textes
        e = t0[el]
        for j in range(3):                         # nur ein Durchlauf: Punkt 1, 2, 3 erscheinen nacheinander und bleiben
            aj = e - 1.6 + j * 0.4
            x = cx + (j - 1) * gap - r
            y = cy - r
            fc += f"[{prev}][dd{k}]overlay=x={x}:y={y}:enable='between(t,{aj:.2f},{e:.2f})'[p{k}];"
            prev = f"p{k}"
            k += 1
    ti = di + 2                                    # Eingang der dauerhaften Zeile oben (nach dem Ton)
    fc += f"[{prev}][{ti}:v]overlay=0:0[ptop];[ptop]format=yuv420p[o];"
    ai = di + 1
    fc += (f"[{ai}:a]asplit=3[ab][at][ah];"
           f"[ab]atrim=start={xf}:end={sec},asetpts=PTS-STARTPTS[abd];"
           f"[at]atrim=start={sec}:end={sec + xf},asetpts=PTS-STARTPTS[atl];"
           f"[ah]atrim=start=0:end={xf},asetpts=PTS-STARTPTS[ahd];"
           f"[atl]afade=t=out:d={xf}:curve=qsin[af1];[ahd]afade=t=in:d={xf}:curve=qsin[af2];"
           f"[af1][af2]amix=inputs=2:duration=longest:normalize=0[acf];"
           f"[abd][acf]concat=n=2:v=0:a=1[ao]")
    cmd += ["-filter_complex", fc, "-map", "[o]", "-map", "[ao]", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
            "-c:a", "aac", "-b:a", "192k", "-t", sec, "-movflags", "+faststart", dst]
    run(cmd)
    return dst


# ---------------------------------------------------------------- Texte
def parse_description(path: str) -> str:
    """Neuer Beschreibungstext pro Mix (Rolf 19.10.2026): Claude schreibt ihn frisch, passend zu Raum, Spruch und Stimmung.
    Datei mit 2–4 Absätzen, Englisch, 250–1200 Zeichen, ohne Zeit-/Längenangaben; die Standardsätze der alten Beschreibung sind tabu."""
    import re
    text = Path(path).read_text(encoding="utf-8").strip()
    if not 250 <= len(text) <= 1200:
        raise SystemExit(f"Beschreibungstext: {len(text)} Zeichen, erlaubt sind 250–1200.")
    if re.search(r"\d+\s*(hour|hours|minute|minutes|min|hr)\b|\b(hour|hours|minutes)\b|full[- ]length", text, re.I):
        raise SystemExit("Beschreibungstext: keine Zeit-/Längenangaben.")
    low = text.lower()
    for old in ("hang your coat on the hook", "nothing here pulls at your attention", "the lounge is always open"):
        if old in low:
            raise SystemExit(f"Beschreibungstext: alte Standardformulierung „{old}“ nicht wiederverwenden.")
    return text


def description(chapter_text: str, total_min: int, intro: str = "", var: dict | None = None, vol: int = 0) -> str:
    if not intro:   # Notfall-Rückfall, wenn kein neuer Text übergeben wurde
        intro = (
            "Hang your coat on the hook. Leave the noise with it.\n\n"
            "A quiet loft high above Tokyo at night. A long desk with two screens, a cognac leather office chair pushed back, "
            "a small black tea tray, one warm lamp and the city glowing amber outside the window. A breathy tenor saxophone, "
            "single felt piano notes, a deep warm sub-bass and a slow, soft groove. Nothing here pulls at your attention.\n\n"
            f"For deep work, coding, studying, writing and productivity. About {metadata.hours_wording(total_min)}, uninterrupted.")
    import tokyo_shop
    shop = tokyo_shop.shop_block(var, vol)   # Amazon-Partnerlinks der im Raum gewählten Geräte (nur wenn Variation bekannt)
    return (
        f"{intro}\n\n"
        + (f"{shop}\n\n" if shop else "") +
        f"Chapters\n{chapter_text}\n\n"
        f"Music by {config.ARTIST}, created with AI. Images: AI-generated.\n"
        f"{HASHTAGS}")


def short_texts(lines: list[str], video_url: str) -> tuple[str, str, list[str]]:
    quote = " ".join(lines)
    title = f"{lines[0]} 🎧 Tokyo Work Lounge #shorts"[:100]
    desc = (f"{quote}\nQuiet jazz for deep work, coding and productivity. The full Tokyo Work Lounge mix is on the channel: "
            f"{video_url}\n\n{HASHTAGS} #shorts")
    return title, desc, ["tokyo work lounge", "slow jazz", "productivity", "coding music", "focus music", "shorts", "aix walker"]


# ---------------------------------------------------------------- Kandidaten fürs Hauptbild, Musik übernehmen
def make_image_candidates(args, out: Path) -> int:
    import genre_test_tokyo_rooms_v3 as r
    from pipeline import drive
    pngs = []
    for i in range(1, args.make_image + 1):
        art = images.generate_art(r.ROOMS[args.room], "16:9", pro=True, style=r.STYLE, image_size="4K")
        p = out / "img" / f"kandidat_{i}.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        art.convert("RGB").save(p)
        art.convert("RGB").resize((1600, 900)).save(out / "img" / f"kandidat_{i}.jpg", quality=88)
        log(f"Kandidat {i}: {art.size[0]}×{art.size[1]}")
        pngs.append(p)
    links = drive.upload_mix_package(args.image_folder, [], {"bilder": pngs})
    log(f"Drive: {links.get('_folder')}")
    (out / "kandidaten.json").write_text(json.dumps({"folder": args.image_folder, "files": [p.name for p in pngs],
                                                    "sizes": [Image.open(p).size for p in pngs]}, indent=2))
    return 0


def reuse_music(room: str, out: Path) -> list[Path]:
    """Die 22 Songs des ersten Mixes aus dem Drive-Ordner holen und als WAV bereitstellen (gleiche Musik, gleiche Reihenfolge)."""
    from pipeline import drive
    svc = drive.service()
    root = drive.ensure_folder(svc, drive.ROOT_FOLDER)
    folders = [f for f in drive.list_children(svc, root, folders=True) if "Tokyo Work Lounge" in f["name"] and room in f["name"] and "v2" not in f["name"]]
    if not folders:
        raise RuntimeError("Drive-Ordner des ersten Tokyo-Mixes nicht gefunden")
    mp3_dir = [f for f in drive.list_children(svc, folders[-1]["id"], folders=True) if f["name"] == "mp3"][0]
    mp3s = [f for f in drive.list_children(svc, mp3_dir["id"], folders=False) if f["name"].endswith(".mp3")]
    REUSE_SRC_MP3["id"] = mp3_dir["id"]
    wavs = []
    for i, f in enumerate(mp3s, 1):
        wav = out / "wav" / f"{i:02d}.wav"
        if not wav.exists():
            src = drive.download(svc, f["id"], out / "raw" / f"{i:02d}.mp3")
            run(["ffmpeg", "-v", "error", "-y", "-i", src, "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", wav])
        wavs.append(wav)
    log(f"{len(wavs)} Songs aus Drive übernommen ({folders[-1]['name']})")
    return wavs


# ---------------------------------------------------------------- nur Short
def short_only(args, out: Path, lines: list[str]) -> int:
    from pipeline import drive, youtube
    art = fetch_main_image(args.room, out, False, args.image_folder, args.image_file)
    svc = drive.service()
    root = drive.ensure_folder(svc, drive.ROOT_FOLDER)
    folders = [f for f in drive.list_children(svc, root, folders=True) if "Tokyo Work Lounge" in f["name"] and args.room in f["name"] and "v2" not in f["name"]]
    if not folders:
        raise RuntimeError("Drive-Ordner des Tokyo-Mixes nicht gefunden")
    folder = folders[-1]
    mp3_dir = [f for f in drive.list_children(svc, folder["id"], folders=True) if f["name"] == "mp3"][0]
    mp3s = [f for f in drive.list_children(svc, mp3_dir["id"], folders=False) if f["name"].endswith(".mp3")]
    pick = mp3s[min(2, len(mp3s) - 1)]
    song = drive.download(svc, pick["id"], out / "work" / "short_song.mp3")
    log(f"Short-Ton aus „{pick['name']}“ (Ordner {folder['name']})")
    short, _chk = make_short_checked(art, lines, song, 35, out / "short",
                                     args.short_desk_x or args.cover_desk_x or DESK_X.get(args.room, 0.70))
    url = f"https://youtu.be/{args.mix_video_id}" if args.mix_video_id else "(Link zum Mix)"
    s_title, s_desc, s_tags = short_texts(lines, url)
    sid = youtube.upload_video(short, s_title, s_desc, s_tags, privacy="private", location=youtube.TOKYO)
    log(f"Short hochgeladen (privat): https://youtube.com/shorts/{sid}")
    (out / "short_result.json").write_text(json.dumps({"short_id": sid, "mix_video_id": args.mix_video_id,
                                                        "title": s_title, "track": pick["name"]}, indent=2))
    log("Fertig: Short")
    return 0


# ---------------------------------------------------------------- Ablauf
# ---------------------------------------------------------------- Bild von Rolf (Phase A: Prompt-Mail, Phase B: Mix aus Drive-Bild)
def prompt_phase(args) -> int:
    """Phase A (Rolf 22.10.2026): komplettes Bildprompt bauen, Plan + Prompt in Drive („Tokyo Hauptbild“) ablegen und Rolf mailen. Keine Kosten."""
    import tokyo_inbox as ib
    from pipeline import drive
    if not (args.scene_file and args.quote_text and args.description_file):
        raise SystemExit("--prompt-only braucht --scene-file, --quote-text und --description-file")
    if args.room in {str(e.get("room")) for e in tokyo_history()}:
        raise SystemExit(f"Raum-Kennung {args.room} wurde schon verwendet – neue Kennung wählen.")
    lines = parse_quote(args.quote_text)
    desc = parse_description(args.description_file)
    prompt, style, var, scene, person = build_room_prompt(args.room, args.scene_file, args.desk_side, args.person,
                                                          {"desk_pos": args.desk_pos, "chair": args.chair, "sofa": args.sofa, "art": args.art, "person_place": args.person_place})
    plan = {"date": ib.today(), "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"), "room": args.room, "side": args.desk_side,
            "person": person, "place_text": "sitzt arbeitend am Schreibtisch (Blick über die Schulter)" if var.get("at_desk") else "steht am Fenster und schaut hinaus",
            "scene": scene, "variation": var, "quote": "|".join(lines), "description": desc, "prompt": prompt, "style": style,
            "vol": args.vol or next_vol(), "status": "wartet auf Bild"}
    svc = drive.service()
    fid = ib.save_plan(svc, plan)
    mid = ib.send_prompt_mail(plan, fid)
    log(f"Plan + Bildprompt in Drive „{ib.FOLDER}“ abgelegt, Mail gesendet ({mid}). Raum {args.room}, Variation: {var}")
    return 0


def apply_inbox(args) -> int | None:
    """Phase B: Plan und Rolfs Bild aus Drive holen. None = weiter mit dem Mix; sonst Exit-Code (4 kein Plan, 5 noch kein Bild, 6 läuft schon/fertig)."""
    import tokyo_inbox as ib
    from pipeline import drive
    svc = drive.service()
    plan, fid, _ = ib.load_plan(svc)
    if not plan:
        log("Kein Plan für heute (Phase A nicht gelaufen).")
        return 4
    if plan.get("status") == "fertig":
        log("Mix für heute ist schon fertig.")
        return 6
    if plan.get("status") == "gestartet" and plan.get("started"):
        age = (datetime.now(timezone.utc) - datetime.strptime(plan["started"], "%Y-%m-%dT%H:%M:%S.000Z").replace(tzinfo=timezone.utc)).total_seconds()
        if age < 3 * 3600:
            log(f"Mix läuft schon (gestartet vor {age / 60:.0f} Min).")
            return 6
    pic = {"id": plan["image_id"], "name": plan.get("image_name", "bild")} if plan.get("image_id") else ib.newest_image(svc, fid, plan["created"])
    local = Path("build") / "tokyo_in.png"  # Rückfall: Rolfs Bild liegt lokal bereit (drive.file sieht selbst hochgeladene Dateien nicht)
    if not pic and local.exists():
        pic = {"id": "local", "name": "tokyo_in.png"}
    if not pic:
        log("Noch kein Bild im Ordner.")
        return 5
    raw = Path("build") / "inbox_image"
    if pic["id"] == "local":
        raw = local
    else:
        drive.download(svc, pic["id"], raw)
    im = Image.open(raw).convert("RGB")
    dst = Path("build") / "inbox_image.png"
    im.save(dst)
    log(f"Bild von Rolf: {pic['name']} ({im.size[0]}×{im.size[1]})")
    dfile = Path("build") / "inbox_desc.txt"
    dfile.write_text(plan["description"], encoding="utf-8")
    args.main_image, args.room, args.desk_side, args.person = str(dst), plan["room"], plan["side"], plan["person"]
    args.quote_text, args.description_file, args.new_room = plan["quote"], str(dfile), False
    if not args.vol:
        args.vol = plan.get("vol", 0)
    LAST_VARIATION.clear()
    LAST_VARIATION.update(plan["variation"])
    ib.mark(svc, plan, fid, status="gestartet", started=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"), image_id=pic["id"], image_name=pic["name"])
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", default="shinjuku-sky-loft")
    ap.add_argument("--quote", type=int, default=0, help="Nummer des Spruchs (0 bis 7) – nur Notfall-Rückfall")
    ap.add_argument("--quote-text", default="", help="NEUER Spruch dieses Mixes (Rolf 19.10.2026: bei jedem Mix neu, von Claude ausgedacht), "
                                                      "Zeilen mit | getrennt, z. B. 'Open one tab, finish one task.|My tracks will keep you company.'")
    ap.add_argument("--description-file", default="", help="NEUER Beschreibungstext dieses Mixes (englisch, 2–4 Absätze, von Claude pro Mix frisch geschrieben)")
    ap.add_argument("--cover-desk-x", type=float, default=0.0, help="Mitte des Schreibtischs im Hauptbild (0–1, von links) für den Album-Cover-Ausschnitt; 0 = Standard des Raums")
    ap.add_argument("--new-room", action="store_true", help="NEUER Raum für diesen Mix: Bild wird neu erzeugt (Szene aus --scene-file) und automatisch geprüft; --room ist dann die neue Kennung")
    ap.add_argument("--scene-file", default="", help="Datei mit dem neuen Orts-/Szenentext (englisch, 80–900 Zeichen, von Claude pro Mix neu erfunden)")
    ap.add_argument("--existing-video-id", default=None, help="schon hochgeladenes Video übernehmen (kein neuer Upload)")
    ap.add_argument("--desk-side", default="right", choices=["left", "right"], help="Seite des Schreibtischs im neuen Raum (abwechseln)")
    ap.add_argument("--desk-pos", default="auto", choices=["auto", "front", "back"], help="Schreibtisch vorn oder im hinteren Teil der Wohnung (auto = abwechselnd, automatisch)")
    ap.add_argument("--chair", default="auto", choices=["auto", "cognac", "black", "eames", "aeron"], help="Bürostuhl: eames (cognac) oder aeron (schwarz, Onyx Black); auto = wechselnd")
    ap.add_argument("--person-place", default="auto", choices=["auto", "window", "desk"], help="Person: am Fenster (unscharf) oder arbeitend am Schreibtisch (Blick über die Schulter)")
    ap.add_argument("--sofa", default="auto", choices=["auto", "fabric", "leather"], help="Couch: Stoff oder Leder (auto = automatisch wechselnd)")
    ap.add_argument("--art", default="auto", help="Wandbild: auto | ink (schwarz-weißes japanisches Tuschebild) | other | Schlüssel aus concepts/tokyo_variation.py")
    ap.add_argument("--person", default="auto", choices=["auto", "woman", "man"], help="Person im neuen Raum: Frau oder Mann (auto = automatisch wechselnd)")
    ap.add_argument("--main-image", default="", help="fertiges Hauptbild (von Rolf erzeugt, 16:9) statt Drive/Neuerzeugung; --room ist dann die Kennung des Raums")
    ap.add_argument("--prompt-only", action="store_true", help="Phase A: nur Bildprompt bauen, in Drive ablegen und Rolf mailen (braucht --new-room-Angaben, --scene-file, --quote-text, --description-file)")
    ap.add_argument("--from-inbox", action="store_true", help="Phase B: Plan + Rolfs Bild aus Drive „Tokyo Hauptbild“ holen (Exit 5 = noch kein Bild, 6 = läuft/fertig, 4 = kein Plan)")
    ap.add_argument("--vol", type=int, default=0, help="Nummer im Titel („- Vol. N“); ohne Angabe: automatisch hochgezählt")
    ap.add_argument("--out", default=None)
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--public", action="store_true")
    ap.add_argument("--drive", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--image-folder", default=ROOM_DRIVE_FOLDER, help="Drive-Ordner (Unterordner bilder) mit dem Hauptbild")
    ap.add_argument("--image-file", default="", help="Dateiname des gewählten Hauptbildes (PNG)")
    ap.add_argument("--make-image", type=int, default=0, help="nur N Kandidaten für das Hauptbild (4K) erzeugen und in Drive ablegen")
    ap.add_argument("--reuse-music", action="store_true", help="Musik aus dem Drive-Ordner des ersten Mixes übernehmen (keine neue Erzeugung)")
    ap.add_argument("--album-cover", default="", help="eigenes Album-Cover (quadratisch, jpg/png) für DistroKid; sonst Ausschnitt des Hauptbilds")
    ap.add_argument("--short-only", action="store_true", help="nur den Short neu bauen (Musik aus dem Drive-Ordner des Mixes)")
    ap.add_argument("--mix-video-id", default="", help="YouTube-ID des Mixes (für den Link in der Short-Beschreibung)")
    ap.add_argument("--short-desk-x", type=float, default=0.0, help="Schreibtischmitte (0.0-1.0 von links) für den Short-Ausschnitt; sonst wie beim Cover")
    args = ap.parse_args()
    global TITLE
    if args.prompt_only:
        return prompt_phase(args)
    if args.from_inbox:
        rc = apply_inbox(args)
        if rc is not None:
            return rc
    vol = args.vol or next_vol()
    TITLE = f"{TITLE_BASE} - Vol. {vol}🎷"
    log(f"Titel: {TITLE}")
    out = Path(args.out or f"build/tokyo-{args.room}")
    for sub in ("raw", "wav", "mp3", "img", "work", "short", "thumb"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        config.GOOGLE_API_KEY = ""
    costs.start(out / "costs.json")
    lines = parse_quote(args.quote_text, allow_used=args.short_only) if args.quote_text else QUOTES[args.quote % len(QUOTES)]
    if args.make_image:
        return make_image_candidates(args, out)
    if args.short_only:
        return short_only(args, out, lines)
    log(f"Tokyo Work Lounge, Raum {args.room}, Spruch: {' '.join(lines)}, dry_run={args.dry_run}")

    new_desk_x = None
    new_person_x = None
    if args.main_image:
        import shutil
        dst = out / "img" / "main_src.png"
        dst.parent.mkdir(parents=True, exist_ok=True)
        Image.open(args.main_image).convert("RGB").save(dst)
        log(f"Hauptbild von Rolf übernommen: {args.main_image} ({Image.open(dst).size})")
        if not args.dry_run:
            try:   # fürs Archiv in Drive bilder/<raum>.png ablegen
                from pipeline import drive
                named = out / "img" / f"{args.room}.png"
                shutil.copy(dst, named)
                drive.upload_mix_package(ROOM_DRIVE_FOLDER, [], {"bilder": [named]})
            except Exception as e:  # noqa: BLE001
                log(f"Raumbild nicht in Drive abgelegt: {str(e)[:160]}")
            chk = check_room_image(Image.open(dst), dict(LAST_VARIATION) or None)   # Schreibtisch- und Personenposition für Cover/Short messen
            log(f"Eigenes Bild geprüft: {chk}")
            if chk:
                dx_ = chk.get("desk_x"); px_ = chk.get("person_x")
                new_desk_x = float(dx_) if isinstance(dx_, (int, float)) and 0.05 <= float(dx_) <= 0.95 else None
                new_person_x = float(px_) if isinstance(px_, (int, float)) and 0.0 <= float(px_) <= 1.0 else None
    if args.new_room and not args.dry_run and not args.main_image:
        if not args.scene_file:
            raise SystemExit("--new-room braucht --scene-file")
        art_new, new_desk_x, new_person_x = make_new_room(args.room, args.scene_file, args.desk_side, args.person, out,
                                                          choice={"desk_pos": args.desk_pos, "chair": args.chair, "sofa": args.sofa, "art": args.art, "person_place": args.person_place})
        if art_new is None:
            log("NEUER RAUM: kein Bild hat nach 3 Versuchen alle Kriterien erfüllt – Abbruch vor der Musik (kein Geld für Musik ausgegeben). "
                "Mit vorhandenem Raum (--room shinjuku-sky-loft|nakameguro-evening-loft|azabu-rain-loft) neu starten und im Bericht melden.")
            return 3
    art = fetch_main_image(args.room, out, args.dry_run, args.image_folder, args.image_file)
    wavs = reuse_music(args.room, out) if args.reuse_music else make_music(out, args.dry_run, args.workers)
    mix, starts = monthly.join_tracks(wavs, out / "wav" / "mix.flac", xf=XF)
    total = audio.probe_duration(mix)
    total_min = int(round(total / 60))
    names = TRACK_NAMES[:len(wavs)]
    chapter_text = metadata.chapters(names, starts)
    log(f"Mix {metadata.fmt_ts(total)}, {len(wavs)} Songs")
    aac = loopvideo.encode_audio(mix, out / "work" / "audio.m4a")

    # Thumbnail (Text mittig), Cover für die MP3-Tags
    thumb = v.make_thumb(art, out / "thumb" / "thumb.jpg", 1920, 1080)
    cover = out / "img" / "cover.jpg"
    images.crop_aspect(art, 1, 1).resize((1400, 1400), Image.LANCZOS).save(cover, "JPEG", quality=90)
    for i, (n, w_) in enumerate(zip(names, wavs), 1):
        if args.reuse_music:
            break                                  # Musik unverändert, MP3s liegen schon im Drive-Ordner des ersten Laufs
        audio.export_mp3(w_, out / "mp3" / f"{i:02d} - {config.ARTIST} - {n}.mp3", n, "Tokyo Work Lounge", i, len(wavs),
                         cover, "Jazz", date.today().year)

    # Video (4K, Standbild, Blenden), dann mit Ton zusammenführen
    qpng = quote_frame(lines, out / "work" / "quote.png")
    vid_silent = build_video(out / "img" / "main_4k.png", qpng, starts, total, out / "work" / "parts")
    mp4 = out / "tokyo_work_lounge.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", vid_silent, "-i", aac, "-c", "copy", "-shortest", "-movflags", "+faststart", mp4])
    log(f"Video fertig: {mp4.stat().st_size / 1e6:.0f} MB, {metadata.fmt_ts(total)}")

    # Short (aus dem Hauptbild)
    s_start = starts[min(2, len(starts) - 1)] + 25
    desk_c = args.cover_desk_x or new_desk_x or DESK_X.get(args.room, 0.70)
    center = args.short_desk_x or short_center(desk_c, new_person_x)
    short, short_chk = make_short_checked(art, lines, mix, min(s_start, max(0, total - 30)), out / "short", center, new_person_x)
    log(f"Short fertig: {short}")

    # Upload (privat, Aufnahmeort Tokyo, Playlist) – Shorts bleiben privat, bis Rolf zustimmt
    video_id, video_url, short_id = None, "(nicht hochgeladen)", None
    privacy = "public" if args.public else "private"
    desc = description(chapter_text, total_min, parse_description(args.description_file) if args.description_file else "", dict(LAST_VARIATION) or None, vol)
    if args.upload:
        from pipeline import youtube
        if args.existing_video_id:   # Video wurde schon hochgeladen (Lauf brach danach ab) → nicht doppelt hochladen
            video_id = args.existing_video_id
            log(f"Vorhandenes Video übernommen: https://youtu.be/{video_id}")
        else:
            video_id = youtube.upload_video(mp4, TITLE, desc, TAGS, privacy=privacy, location=youtube.TOKYO)
        video_url = f"https://youtu.be/{video_id}"
        log(f"Hochgeladen ({privacy}): {video_url}")
        yt_pending, yt_errors = [], {}
        ok, err = youtube.retry(lambda: youtube.set_thumbnail(video_id, thumb), label="Thumbnail")
        if not ok:
            log(f"Thumbnail NICHT gesetzt: {err[:400]}")
            yt_pending.append("thumbnail")
            yt_errors["thumbnail"] = err
        def _pl():
            pid = youtube.ensure_playlist(*PLAYLIST)
            youtube.add_to_playlist(video_id, pid)
            return pid
        ok, err = youtube.retry(_pl, label="Playlist")
        if ok:
            log(f"Playlist „{PLAYLIST[0]}“ eingetragen")
        else:
            log(f"Playlist NICHT eingetragen: {err[:400]}")
            yt_pending.append("playlist")
            yt_errors["playlist"] = err
        s_title, s_desc, s_tags = short_texts(lines, video_url)
        try:
            short_id = youtube.upload_video(short, s_title, s_desc, s_tags, privacy="private", location=youtube.TOKYO)
            log(f"Short hochgeladen (privat): https://youtube.com/shorts/{short_id}")
        except Exception as e:  # noqa: BLE001
            log(f"Short nicht hochgeladen: {str(e)[:160]}")
            yt_pending.append("short")
        if yt_pending:   # das Video ist jetzt länger verarbeitet: noch eine Runde
            if "thumbnail" in yt_pending and youtube.retry(lambda: youtube.set_thumbnail(video_id, thumb), tries=2, wait=120, label="Thumbnail (2. Runde)")[0]:
                yt_pending.remove("thumbnail")
            if "playlist" in yt_pending and youtube.retry(lambda: youtube.add_to_playlist(video_id, youtube.ensure_playlist(*PLAYLIST)), tries=2, wait=120, label="Playlist (2. Runde)")[0]:
                yt_pending.remove("playlist")
        if yt_pending:
            log(f"YOUTUBE OFFEN: {yt_pending} – Fehler: {json.dumps(yt_errors, ensure_ascii=False)[:800]}")
        try:   # alle älteren Tokyo-Mixe ohne Thumbnail/Playlist nachziehen (best effort)
            rr = subprocess.run([sys.executable, str(Path(__file__).parent / "repair_tokyo_youtube.py"), "--days", "14"], capture_output=True, text=True, timeout=900)
            log("Reparatur Thumbnail/Playlist:\n" + (rr.stdout or "")[-1500:] + (rr.stderr or "")[-500:])
        except Exception as e:  # noqa: BLE001
            log(f"Reparaturlauf fehlgeschlagen: {e}")

    meta = out / "metadata.txt"
    meta.write_text("\n".join(["TITEL", TITLE, "", "BESCHREIBUNG", desc, "", "TAGS", ", ".join(TAGS), "",
                               "SPRUCH", " ".join(lines)]), encoding="utf-8")
    drive_links = {}
    if args.drive and not args.dry_run:
        try:
            from pipeline import drive
            folder = (f"{date.today().isoformat()} – Tokyo Work Lounge – {args.room}{' v2' if args.reuse_music else ''} "
                      f"({GENRE_LABEL}, {BPM_LABEL} BPM)")
            # Album-Cover für DistroKid: album_3000.png (3000x3000). Vorrang: --album-cover, sonst quadratischer Ausschnitt des Hauptbilds.
            album = out / "img" / "album_3000.png"
            src_cover = Path(args.album_cover) if args.album_cover else None
            if src_cover:
                im = Image.open(src_cover).convert("RGB").resize((3000, 3000), Image.LANCZOS)
            else:
                dx = args.cover_desk_x or new_desk_x or DESK_X.get(args.room, 0.70)
                im = make_album_cover(art, dx, 3000)
            im.save(album, "PNG", optimize=True)
            drive_links = drive.upload_mix_package(folder, [album, thumb, out / "img" / "master.jpg", meta],
                                                   {"mp3": sorted((out / "mp3").glob("*.mp3")), "short": [short]})
            if args.reuse_music and REUSE_SRC_MP3["id"]:
                # Musik unverändert: die MP3s serverseitig in den mp3-Ordner des neuen Mix-Ordners kopieren (Namen bleiben)
                svc = drive.service()
                new_root = drive.ensure_folder(svc, drive.ROOT_FOLDER)
                new_folder = drive.ensure_folder(svc, folder, new_root)
                dst = drive.ensure_folder(svc, "mp3", new_folder)
                have = {f["name"] for f in drive.list_children(svc, dst, folders=False)}
                n = 0
                for f in drive.list_children(svc, REUSE_SRC_MP3["id"], folders=False):
                    if f["name"].endswith(".mp3") and f["name"] not in have:
                        svc.files().copy(fileId=f["id"], body={"name": f["name"], "parents": [dst]}, fields="id").execute()
                        n += 1
                log(f"{n} MP3s aus dem Quell-Mix in den neuen Drive-Ordner kopiert")
            log(f"Drive: {drive_links.get('_folder')}")
        except Exception as e:  # noqa: BLE001
            log(f"Drive-Ablage fehlgeschlagen: {e}")
            drive_links = {"error": str(e)}

    cost_line = costs.report()
    log(cost_line)
    result = {"room": args.room, "video_id": video_id, "video_url": video_url, "short_id": short_id, "short_check": (short_chk or None), "vol": vol, "variation": dict(LAST_VARIATION) or None, "privacy": privacy,
              "duration_sec": total, "duration_min": total_min, "songs": len(wavs), "quote": lines, "title": TITLE,
              "cost_usd": costs.total_usd(), "cost_report": cost_line, "drive": drive_links,
              "boundaries": [round(s, 1) for s in starts], "video_mb": round(mp4.stat().st_size / 1e6)}
    (out / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    if args.upload and not args.dry_run:
        try:
            from pipeline import memory
            mem = memory.load()
            mem.setdefault("tokyo", []).append({"date": date.today().isoformat(), "room": args.room, "video_id": video_id,
                                                "short_id": short_id, "duration_min": total_min, "songs": len(wavs),
                                                "privacy": privacy, "vol": vol, "quote": " ".join(lines), "cost_usd": costs.total_usd(),
                                                "variation": dict(LAST_VARIATION) or None})
            # Die Abend-Aufgabe „Mix-Link und veröffentlichen“ (19:45) liest nur die Liste „shorts2“ → Tokyo-Short dort eintragen,
            # sonst bliebe er privat und ohne Mix-Verknüpfung (gefunden 19.10.2026).
            mem.setdefault("shorts2", []).append({"date": date.today().isoformat(), "id": f"tokyo-{date.today().isoformat()}",
                                                  "title": s_title, "video_id": short_id, "mix_video_id": video_id,
                                                  "cost_usd": 0.0, "tokyo": True}) if short_id else None
            memory.save(mem)
        except Exception as e:  # noqa: BLE001
            log(f"Gedächtnis nicht gespeichert: {str(e)[:160]}")
    if args.from_inbox and not args.dry_run:
        try:   # Plan in Drive als „fertig“ kennzeichnen, damit die stündliche Prüfung nichts doppelt startet
            import tokyo_inbox as ib
            from pipeline import drive
            svc_ = drive.service()
            plan_, fid_, _ = ib.load_plan(svc_)
            if plan_:
                ib.mark(svc_, plan_, fid_, status="fertig", video_id=video_id)
        except Exception as e:  # noqa: BLE001
            log(f"Plan nicht als fertig markiert: {str(e)[:160]}")
    log(f"Fertig: {total_min} Min, Video {video_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
