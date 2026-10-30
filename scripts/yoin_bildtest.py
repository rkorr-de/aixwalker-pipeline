#!/usr/bin/env python3
"""YOIN Rooms Bildtest (Rolf 30.10.2026): 2 Hauptbilder (Nano Banana Pro, 4K, 16:9) mit Viertel-Bezug im Ausblick,
Thumbnails (Raumname exakt mittig, 70 % der Breite, Cormorant Garamond Light), fünf englische Texte je Bild (Claude-API),
Ablage in Drive und GENAU EINE Mail. Reiner Sichttest: keine MP3s, kein Lyria, kein Video, kein YouTube, kein DistroKid.

  python scripts/yoin_bildtest.py --stage images     # 2 × 4K-Bild (ca. 0,24 $ je Bild), Rohbild ohne Text als PNG
  python scripts/yoin_bildtest.py --stage thumbs     # 1280×720-Thumbnails + Prüfung (Mitte, Breite, Lesbarkeit bei 320 px)
  python scripts/yoin_bildtest.py --stage texts      # Titel, Beschreibung, Vorspann-Zeile, Anpinn-Kommentar, Community-Post
  python scripts/yoin_bildtest.py --stage drive      # YOIN Rooms/Bildtest 2026-10-30 (neben „AIX WALKER Mixe“), Link-Freigabe
  python scripts/yoin_bildtest.py --stage mail       # genau eine Mail; ein zweiter Aufruf wird verweigert (mail_sent.json)

Jede Stufe nutzt die Ergebnisse der vorigen aus build/yoin_bildtest/state.json; ein erneuter Lauf zahlt kein Bild doppelt.
"""
import argparse
import base64
import contextlib
import io
import json
import re
import subprocess
import sys
from email.message import EmailMessage
from pathlib import Path

import requests
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from pipeline import config, costs, images  # noqa: E402

OUT = ROOT / "build" / "yoin_bildtest"
STATE = OUT / "state.json"
DRIVE_PATH = "YOIN Rooms/Bildtest 2026-10-30"
MAIL_TO = "rolf.korr@gmail.com"
MAIL_SUBJECT = "YOIN Rooms Bildtest – 2 Hauptbilder mit Viertel-Bezug"
USD_EUR = 0.92
COST_LIMIT_EUR = 1.5          # Sicherung: mehr als 3 × 4K-Bild gibt der Test nie aus

BASE_PROMPT = (
    "Organic architectural wide-angle photography of an ultra-spacious minimalist luxury cafe on the 2nd floor of an architecturally "
    "striking building in Daikanyama, Tokyo. Expansive floor-to-ceiling organic curved windows overlook the illuminated streets of Tokyo "
    "and distant skyline silhouettes shrouded in subtle evening dusk fog. High deep charcoal-black painted ceiling featuring a colossal, "
    "avant-garde modern chandelier sculpture emitting faint, subtle, and warm 2600K ambient glow as a dramatic architectural centerpiece. "
    "In the deeper background, a sleek minimalist coffee bar counter in brushed dark bronze and ribbed stone, outfitted with a premium "
    "matte-black multi-group espresso machine, precision grinders, and artisan barista accessories. Modern designer lounge chairs and low "
    "tables arranged along the windows with wide open circulation. Material palette: smooth polished concrete flooring, warm textured "
    "modern concrete walls, dark bronze accents, and organic wabi-sabi rock details. Abstract minimalist indoor greenery, calm meditative "
    "low-cortisol atmosphere, quiet luxury, photorealistic, cinematic dusk lighting, 8k, 16:9."
)


def _swap(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"Stelle nicht eindeutig im Basisprompt: {old!r}"
    return text.replace(old, new)


PROMPT_B = _swap(_swap(BASE_PROMPT, "in Daikanyama, Tokyo", "in Nakameguro, Tokyo"),
                 "overlook the illuminated streets of Tokyo and distant skyline silhouettes",
                 "overlook the Meguro River canal lined with bare cherry trees and softly glowing lanterns, "
                 "the low-rise lit streets of Nakameguro and distant skyline silhouettes")

ROOMS = {
    "A": {"name": "DAIKANYAMA DUSK", "district": "Daikanyama", "prompt": BASE_PROMPT},
    "B": {"name": "NAKAMEGURO LANTERN HOUR", "district": "Nakameguro", "prompt": PROMPT_B},
}

# ------------------------------------------------------------------ Zustand


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def save_state(state: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def eur(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def de(x) -> str:
    """Zahl mit Dezimalkomma (Mail an Rolf)."""
    return str(x).replace(".", ",")


# ------------------------------------------------------------------ Stufe 1: Hauptbilder

def stage_images(state: dict) -> None:
    costs.start(OUT / "ledger.json", limit_eur=COST_LIMIT_EUR)
    state.setdefault("images", {})
    for key, room in ROOMS.items():
        path = OUT / f"hauptbild_{key}.png"
        info = state["images"].get(key, {})
        if path.exists() and info.get("ok"):
            print(f"[images] {key}: vorhanden, wird wiederverwendet")
            continue
        (OUT / f"prompt_{key}.txt").write_text(room["prompt"], encoding="utf-8")
        info = {"ok": False, "attempts": 0, "log": []}
        for attempt in (1, 2):                      # „einmal neu erzeugen“
            failed_before = costs._ledger.get("image_failed", 0)
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    # style="" → der Standard-Suffix der Funktion wird NICHT angehängt, der Prompt bleibt unverändert
                    img = images.generate_art(room["prompt"], "16:9", pro=True, image_size="4K", style="")
            finally:
                images.RAW_ART.clear()              # kein atexit-Upload nach „AIX WALKER Mixe/_rohdaten“
                sys.stdout.write(buf.getvalue())
            info["attempts"] += 1
            info["log"] += [ln for ln in buf.getvalue().splitlines() if ln.strip()]
            if costs._ledger.get("image_failed", 0) > failed_before:
                print(f"[images] {key}: Versuch {attempt} ohne Bild")
                continue
            img.save(path, "PNG")
            info.update(ok=True, size=list(img.size), prompt_chars=len(room["prompt"]))
            break
        state["images"][key] = info
        save_state(state)
    led = costs._ledger
    n4k, npro = led.get("image_pro_4k", 0), led.get("image_pro", 0)
    usd = n4k * config.PRICES_USD["image_pro_4k"] + npro * config.PRICES_USD["image_pro"]
    state["cost"] = {"image_pro_4k": n4k, "image_pro": npro, "image_failed": led.get("image_failed", 0),
                     "usd": round(usd, 2), "eur": round(usd * USD_EUR, 2)}
    save_state(state)
    print(f"[images] Kosten: {n4k} × 4K, {npro} × Pro = {usd:.2f} $ = {state['cost']['eur']:.2f} €")


# ------------------------------------------------------------------ Schrift

FONT_CACHE = OUT / "fonts"
FONT_URLS = ["https://raw.githubusercontent.com/google/fonts/main/ofl/cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf",
             "https://github.com/google/fonts/raw/main/ofl/cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf"]


def find_font() -> tuple[Path, str, bool]:
    """Cormorant Garamond Light: erst Repo (assets/), dann installierte Schriften (fc-list), dann Download aus google/fonts,
    zuletzt Cinzel aus der Pipeline. Liefert (Pfad, Beschreibung, ist_cormorant)."""
    for p in sorted((ROOT / "assets").rglob("*ormorant*aramond*.ttf")):
        return p, f"Repo: {p.relative_to(ROOT)}", True
    try:
        out = subprocess.run(["fc-list", ":family=Cormorant Garamond", "file", "style"], capture_output=True, text=True, timeout=20).stdout
        light = [ln.split(":")[0] for ln in out.splitlines() if "Light" in ln and "Italic" not in ln]
        if light:
            return Path(light[0]), f"installiert: {light[0]}", True
    except Exception:  # noqa: BLE001
        pass
    FONT_CACHE.mkdir(parents=True, exist_ok=True)
    dst = FONT_CACHE / "CormorantGaramond[wght].ttf"
    if not dst.exists():
        for url in FONT_URLS:
            try:
                r = requests.get(url, timeout=60)
                if r.status_code == 200 and len(r.content) > 100_000:
                    dst.write_bytes(r.content)
                    break
                print(f"[font] {url} → HTTP {r.status_code}")
            except Exception as e:  # noqa: BLE001
                print(f"[font] {url} → {e}")
    if dst.exists():
        return dst, "Download aus github.com/google/fonts (ofl/cormorantgaramond, Variable Font, Gewicht 300 = Light)", True
    return ROOT / "assets" / "fonts" / "Cinzel.ttf", "Ersatz: Cinzel aus der Pipeline (Cormorant Garamond war nicht beschaffbar)", False


def load_font(path: Path, size: float) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(path), size)
    try:
        axes = f.get_variation_axes()
        f.set_variation_by_axes([300 if a["name"] in (b"Weight", "Weight") else a["default"] for a in axes])
    except (OSError, AttributeError):
        pass                                        # statische Schrift: kein Gewichts-Regler
    return f


# ------------------------------------------------------------------ Stufe 2: Thumbnails

TW, TH = 1280, 720
CREAM = (0xF2, 0xEC, 0xE0)
TEXT_FRAC = 0.70            # Textbreite = 70 % der Bildbreite
TRACK_EM = 0.07             # „leicht gesperrt“
SS = 4                      # Überabtastung beim Zeichnen: Maße auf ein Viertel Pixel genau


def _text_mask(text: str, font: ImageFont.FreeTypeFont, track: float, canvas: tuple[int, int], origin: tuple[float, float]) -> Image.Image:
    """Zeichnet `text` Zeichen für Zeichen (Kerning bleibt über die Präfixbreiten erhalten) in eine L-Maske."""
    m = Image.new("L", canvas, 0)
    d = ImageDraw.Draw(m)
    ox, oy = origin
    for i, ch in enumerate(text):
        x = font.getlength(text[: i + 1]) - font.getlength(ch) + track * i
        d.text((ox + x, oy), ch, font=font, fill=255)
    return m


def _ink_bbox(mask: Image.Image, thr: int = 128) -> tuple[int, int, int, int]:
    return mask.point(lambda v: 255 if v >= thr else 0).getbbox()


def render_name_mask(text: str, font_path: Path) -> tuple[Image.Image, dict]:
    """Maske (TW×TH) mit dem Text, dessen ECHTE Tintenbox genau 70 % der Breite misst und bei (640, 360) zentriert ist."""
    cw, ch = TW * SS, TH * SS
    want_w = TEXT_FRAC * TW * SS
    lo, hi = 10.0, 400.0
    for _ in range(40):                               # Schriftgröße so wählen, dass die gemessene Tintenbreite passt
        size = (lo + hi) / 2
        f = load_font(font_path, size)
        probe = _text_mask(text, f, size * TRACK_EM, (cw * 2, ch), (cw * 0.1, ch * 0.3))
        x0, _, x1, _ = _ink_bbox(probe)
        if x1 - x0 < want_w:
            lo = size
        else:
            hi = size
    f = load_font(font_path, (lo + hi) / 2)
    track = f.size * TRACK_EM
    for _ in range(12):                               # Feinabgleich über die Laufweite: Tintenbreite auf ≤ 1 px (4×) genau
        probe = _text_mask(text, f, track, (cw * 2, ch), (cw * 0.1, ch * 0.3))
        bx0, by0, bx1, by1 = _ink_bbox(probe)
        diff = want_w - (bx1 - bx0)
        if abs(diff) <= 1:
            break
        track += diff / (len(text) - 1)
    # Tintenmitte → Bildmitte (aus der gemessenen Box, nicht aus Schätzwerten)
    ox = cw * 0.1 + (cw / 2 - (bx0 + bx1) / 2)
    oy = ch * 0.3 + (ch / 2 - (by0 + by1) / 2)
    big = _text_mask(text, f, track, (cw, ch), (ox, oy))
    mask = big.resize((TW, TH), Image.LANCZOS)
    return mask, {"font_size_px_1x": round(f.size / SS, 2), "track_px_1x": round(track / SS, 2), "track_em": round(track / f.size, 3),
                  "bbox4": list(_ink_bbox(big, 128))}


def measure(bbox4: list) -> dict:
    """Maße der echten Tintenbox (gemessen in 4-facher Auflösung, Genauigkeit 0,25 px), umgerechnet auf 1280×720."""
    x0, y0, x1, y1 = [v / SS for v in bbox4]
    return {"bbox": [x0, y0, x1, y1], "width_px": round(x1 - x0, 2), "width_frac": round((x1 - x0) / TW, 4),
            "center_x": round((x0 + x1) / 2, 2), "center_y": round((y0 + y1) / 2, 2), "height_px": round(y1 - y0, 2)}


def _lum(rgb) -> float:
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(rgb[0]) + 0.7152 * ch(rgb[1]) + 0.0722 * ch(rgb[2])


def contrast_ratio(l1: float, l2: float) -> float:
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def make_thumbnail(art: Image.Image, name: str, font_path: Path, out: Path, shadow: bool) -> dict:
    base = images.crop_aspect(art.convert("RGB"), 16, 9).resize((TW, TH), Image.LANCZOS)
    base = Image.blend(base, Image.new("RGB", (TW, TH), (0, 0, 0)), 0.10)     # schwarze Abdunklung, 10 % Deckkraft
    mask, fontinfo = render_name_mask(name, font_path)
    thumb = base
    if shadow:                                                                    # weicher Schatten direkt an der Schrift (zwei Radien)
        wide = mask.filter(ImageFilter.GaussianBlur(12)).point(lambda v: min(185, int(v * 3.5)))
        tight = mask.filter(ImageFilter.GaussianBlur(3)).point(lambda v: min(205, int(v * 1.9)))
        thumb = Image.composite(Image.new("RGB", (TW, TH), (0, 0, 0)), thumb, ImageChops.lighter(wide, tight))
    pre_text = thumb                                                              # Untergrund inkl. Schatten, ohne Schrift
    thumb = Image.composite(Image.new("RGB", (TW, TH), CREAM), thumb, mask)
    thumb.save(out, "PNG")

    m = measure(fontinfo.pop("bbox4"))
    res = {**fontinfo, **m, "shadow": shadow}
    res["center_dx"] = round(m["center_x"] - TW / 2, 2)
    res["center_dy"] = round(m["center_y"] - TH / 2, 2)
    res["inside"] = m["bbox"][0] >= 0 and m["bbox"][1] >= 0 and m["bbox"][2] <= TW and m["bbox"][3] <= TH
    res["margin_left_px"], res["margin_top_px"] = round(m["bbox"][0], 1), round(m["bbox"][1], 1)
    res["bbox"] = [round(v, 2) for v in m["bbox"]]
    # Lesbarkeit: Untergrund direkt um die Buchstaben (Ring von 2–6 px um die Striche, inkl. Schatten) gegen Creme; bei 320 px Breite
    # zusätzlich Versalhöhe und Strichdeckung (eine dünne Light-Schrift verliert beim Verkleinern an Deckkraft)
    ring = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(13)), mask.filter(ImageFilter.MaxFilter(5)))
    px, rp, mp = pre_text.load(), ring.load(), mask.load()
    near = sorted(_lum(px[x, y]) for y in range(TH) for x in range(TW) if rp[x, y] > 200 and mp[x, y] < 8)
    res["ring_luminance_median"] = round(near[len(near) // 2], 3)
    res["ring_luminance_p90"] = round(near[int(len(near) * 0.9)], 3)
    res["contrast_ratio_median"] = round(contrast_ratio(_lum(CREAM), res["ring_luminance_median"]), 2)
    res["contrast_ratio_p90"] = round(contrast_ratio(_lum(CREAM), res["ring_luminance_p90"]), 2)
    small_mask = mask.resize((320, 180), Image.LANCZOS)
    res["cap_height_px_320"] = round(m["height_px"] / 4, 1)
    res["peak_alpha_320"] = round(small_mask.getextrema()[1] / 255, 2)
    res["readable_320"] = bool(res["contrast_ratio_p90"] >= 4.5 and res["cap_height_px_320"] >= 6 and res["peak_alpha_320"] >= 0.5)
    small = thumb.resize((320, 180), Image.LANCZOS)
    small.save(out.with_name(out.stem + "_320.png"))
    small.resize((960, 540), Image.NEAREST).save(out.with_name(out.stem + "_320x3.png"))
    return res


def stage_thumbs(state: dict, shadow: bool) -> None:
    font_path, font_desc, is_cormorant = find_font()
    state["font"] = {"path": str(font_path), "desc": font_desc, "cormorant_light": is_cormorant}
    print(f"[thumbs] Schrift: {font_desc}")
    state.setdefault("thumbs", {})
    for key, room in ROOMS.items():
        src = OUT / f"hauptbild_{key}.png"
        if not src.exists():
            print(f"[thumbs] {key}: kein Hauptbild, übersprungen")
            continue
        res = make_thumbnail(Image.open(src), room["name"], font_path, OUT / f"thumbnail_{key}.png", shadow)
        state["thumbs"][key] = res
        ok = abs(res["width_frac"] - TEXT_FRAC) <= 0.0005 and abs(res["center_dx"]) <= 0.3 and abs(res["center_dy"]) <= 0.3 and res["inside"]
        print(f"[thumbs] {key} {room['name']}: Breite {res['width_px']} px = {res['width_frac'] * 100:.1f} %, Mitte "
              f"({res['center_x']}, {res['center_y']}), Maß+Lage {'OK' if ok else 'ABWEICHUNG'}, bei 320 px: Kontrast "
              f"{res['contrast_ratio_median']}:1 (Median) / {res['contrast_ratio_p90']}:1 (hellste 10 %), Versalhöhe {res['cap_height_px_320']} px, Strichdeckung {res['peak_alpha_320']}, "
              f"lesbar={res['readable_320']}")
        res["geometry_ok"] = ok
    save_state(state)


# ------------------------------------------------------------------ Stufe 3: Texte

TEXT_SYSTEM = ("You write calm, precise English YouTube copy for \"YOIN Rooms\", a new quiet Tokyo cafe-jazz channel "
               "(instrumental cafe jazz for focus, work and reading). You answer with valid JSON only, no commentary, no code fence.")

TEXT_PROMPT = """Write copy for TWO different videos. Each video shows one room: an ultra-spacious, minimalist luxury cafe on the 2nd floor of an architecturally striking building, with floor-to-ceiling organic curved windows, a high charcoal-black ceiling with one large sculptural chandelier in a faint warm glow, a dark bronze and ribbed-stone coffee bar far back, designer lounge chairs, polished concrete, wabi-sabi rock details and a little abstract greenery, in the evening dusk.

Room A: name "DAIKANYAMA DUSK", district Daikanyama, Tokyo. The windows overlook the lit streets of Tokyo and distant skyline silhouettes in soft evening fog. District mood you may use: quiet, leafy, low-rise, design-minded, unhurried.
Room B: name "NAKAMEGURO LANTERN HOUR", district Nakameguro, Tokyo. The windows overlook the Meguro River canal lined with bare cherry trees and softly glowing lanterns, the low-rise lit streets of Nakameguro and distant skyline silhouettes. District mood you may use: riverside, canal, bare cherry branches, lantern glow, low-rise lit streets, an evening walk by the water.

Every text must feel tied to ITS district (atmosphere, light, mood of the neighbourhood). Use only the moods listed above; no invented facts (no history, famous places, shops, events), no brand names or business names, no digits anywhere, nothing about opening hours, no fixed publishing days or upload rhythm, no statements about how long the music or video is.
The two rooms must get clearly different texts: different sentence openings, different adjectives and verbs, no shared sentences or phrases. Natural shared words like Tokyo, cafe, jazz, work, focus, reading are fine.

For EACH room return these JSON fields:
- "title": video title under 100 characters, pattern "<Room name in Title Case> | <search phrase>", for example "Daikanyama Dusk | Quiet Tokyo Cafe Jazz for Deep Work". The two search phrases must differ in wording (not just the room name).
- "desc_room": 2 or 3 sentences about the room and its district, with 1 or 2 subtle emoji.
- "desc_usage": one short paragraph (1 or 2 sentences) about using it for focus, work and reading, with at most 1 emoji.
- "desc_japanese": exactly one line in Japanese (natural, calm, mentions the district or its mood), at most 1 emoji.
- "intro_line": the in-video opening line: 4 to 7 words, calm, NOT an imperative (it must not start with a verb like Let, Take, Find, Sit, Breathe, Come, Join, Listen, Relax, Enjoy, Stay), with a quiet reference to the district. Plain text, no quotation marks.
- "pin_lines": a list of 3 or 4 short lines (each under 80 characters) for the pinned comment, each with emoji or symbols such as ✦ ☕ 🌙 · ; one of them is a question to viewers about the district or the time of day. Do NOT repeat the intro line here; it is added in front by the script.
- "community_post": a short community post (2 to 4 short lines) with emoji, exactly one sentence about the district, ending with a question or a poll idea (write "Poll idea:" followed by the question and 2 to 4 answer options separated by " / " if you choose a poll).

Return {"A": {...}, "B": {...}} and nothing else."""

STOP = set("""about above after again also always another around because been before being between both cannot could does doing down during each even ever every from have having here into just like more most much must never only other over same should some such than that their them then there these they this those through under until very want were what when where which while will with within without would your yours yourself their theirs ours""".split())
GENERIC = set("tokyo cafe café jazz work focus reading quiet deep calm evening soft warm light room music space time slow".split())
BRANDS = ["starbucks", "blue bottle", "tsutaya", "t-site", "muji", "ikea", "apple", "spotify", "youtube", "google", "nespresso", "la marzocco",
          "nike", "uniqlo", "instagram", "tiktok", "netflix"]
IMPERATIVES = {"let", "take", "find", "sit", "breathe", "come", "join", "listen", "relax", "enjoy", "stay", "feel", "watch", "settle", "slow",
               "drift", "unwind", "rest", "pause", "begin", "start", "welcome", "imagine", "bring", "keep", "follow", "meet", "step", "wander",
               "linger", "gather", "close", "open", "think", "wait", "sink", "float"}
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿⌀-⏿]")
JAPANESE = re.compile("[぀-ヿ一-鿿]")
WEEKDAYS = re.compile(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|daily|weekly|every (day|week|monday|tuesday|wednesday|thursday|friday|"
                      r"saturday|sunday)|new (mix|video|upload)s?|uploads?)\b", re.I)
LENGTH = re.compile(r"\b(hours|an hour|one hour|hour of|hour-long|minutes?|mins?|hrs?|all-night|all night)\b", re.I)
PLACEHOLDER = "[Tracklist folgt im echten Lauf]"


def claude_text(prompt: str, system: str, max_tokens: int = 5000) -> tuple[str, str]:
    key = __import__("os").environ["AIXWALKER_CLAUDE_KEY"]
    last = None
    for model in (__import__("os").environ.get("YOIN_TEXT_MODEL", "claude-opus-5-5"), "claude-sonnet-5-5"):
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=240,
                          headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                          json={"model": model, "max_tokens": max_tokens, "system": system,
                                "messages": [{"role": "user", "content": prompt}]})
        if r.status_code == 200:
            return "".join(b.get("text", "") for b in r.json()["content"] if b.get("type") == "text"), model
        last = f"{model}: HTTP {r.status_code} {r.text[:200]}"
        print(f"[texte] {last}")
    raise RuntimeError(f"Claude-API nicht erreichbar: {last}")


def parse_json(text: str) -> dict:
    s, e = text.find("{"), text.rfind("}")
    return json.loads(text[s:e + 1])


def _sentences(s: str) -> int:
    return len(re.findall(r"[.!?…](?=\s|$|[^\w\s]|\s*[\U0001F000-\U0001FAFF])", s))


def content_words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-zà-ÿ]{4,}", s.lower()) if w not in STOP and w not in GENERIC}


def full_text(t: dict) -> str:
    return " ".join([t["title"], t["desc_room"], t["desc_usage"], t["intro_line"], *t["pin_lines"], t["community_post"]])


def assemble(t: dict) -> dict:
    t = dict(t)
    t["description"] = f"{t['desc_room'].strip()}\n\n{t['desc_usage'].strip()}\n\n{PLACEHOLDER}\n\n{t['desc_japanese'].strip()}"
    t["pin_comment"] = "\n".join([t["intro_line"].strip(), *[ln.strip() for ln in t["pin_lines"]]])
    return t


def validate(texts: dict) -> list[str]:
    bad = []
    for k, t in texts.items():
        for f in ("title", "desc_room", "desc_usage", "desc_japanese", "intro_line", "pin_lines", "community_post"):
            if not t.get(f):
                bad.append(f"{k}: Feld {f} fehlt")
        if bad:
            return bad
        allt = full_text(t) + " " + t["desc_japanese"]
        if len(t["title"]) >= 100 or " | " not in t["title"]:
            bad.append(f"{k}: Titel ≥100 Zeichen oder ohne ' | '")
        if re.search(r"\d", allt):
            bad.append(f"{k}: enthält Ziffern")
        if WEEKDAYS.search(allt):
            bad.append(f"{k}: nennt Veröffentlichungstage/Rhythmus")
        if LENGTH.search(re.sub(r"lantern hour", "", allt, flags=re.I)):
            bad.append(f"{k}: nennt Längen/Stunden")
        if any(b in allt.lower() for b in BRANDS):
            bad.append(f"{k}: Markenname")
        if not 2 <= _sentences(t["desc_room"]) <= 3:
            bad.append(f"{k}: desc_room hat {_sentences(t['desc_room'])} Sätze (2–3 verlangt)")
        if not JAPANESE.search(t["desc_japanese"]) or "\n" in t["desc_japanese"].strip():
            bad.append(f"{k}: japanische Zeile fehlt oder hat mehrere Zeilen")
        if JAPANESE.search(t["title"] + t["desc_room"] + t["desc_usage"] + t["intro_line"] + " ".join(t["pin_lines"]) + t["community_post"]):
            bad.append(f"{k}: Japanisch außerhalb der japanischen Zeile")
        words = re.findall(r"[A-Za-z’'-]+", t["intro_line"])
        if not 4 <= len(words) <= 7:
            bad.append(f"{k}: Vorspann-Zeile hat {len(words)} Wörter (4–7)")
        if words and words[0].lower() in IMPERATIVES:
            bad.append(f"{k}: Vorspann-Zeile beginnt mit Imperativ '{words[0]}'")
        if not 3 <= len(t["pin_lines"]) <= 4:
            bad.append(f"{k}: Anpinn-Kommentar hat {len(t['pin_lines'])} Zeilen nach der Vorspann-Zeile (3–4)")
        if not any("?" in ln for ln in t["pin_lines"]):
            bad.append(f"{k}: keine Frage im Anpinn-Kommentar")
        if "?" not in t["community_post"]:
            bad.append(f"{k}: keine Frage im Community-Post")
        desc_emoji = len(EMOJI.findall(t["desc_room"] + t["desc_usage"] + t["desc_japanese"]))
        if not 1 <= desc_emoji <= 5:
            bad.append(f"{k}: {desc_emoji} Emoji in der Beschreibung (1–5)")
        if len(EMOJI.findall(" ".join(t["pin_lines"]))) < 3 or len(EMOJI.findall(t["community_post"])) < 2:
            bad.append(f"{k}: zu wenige Emoji/Symbole in Anpinn-Kommentar oder Community-Post")
    a, b = texts["A"], texts["B"]
    if content_words(a["intro_line"]) & content_words(b["intro_line"]):
        bad.append(f"Vorspann-Zeilen teilen Wörter: {content_words(a['intro_line']) & content_words(b['intro_line'])}")
    pa, pb = a["title"].split("|", 1)[1], b["title"].split("|", 1)[1]
    if pa.strip().lower() == pb.strip().lower():
        bad.append("Titel haben dieselbe Suchphrase")
    wa, wb = content_words(full_text(a)), content_words(full_text(b))
    jac = len(wa & wb) / max(1, len(wa | wb))
    if jac > 0.2:
        bad.append(f"Wortüberschneidung zu hoch ({jac:.2f}): {sorted(wa & wb)}")
    return bad


def stage_texts(state: dict) -> None:
    feedback = ""
    texts, model, problems = None, None, []
    for attempt in range(1, 4):
        raw, model = claude_text(TEXT_PROMPT + feedback, TEXT_SYSTEM)
        try:
            texts = parse_json(raw)
        except Exception as e:  # noqa: BLE001
            problems = [f"JSON nicht lesbar: {e}"]
        else:
            problems = validate(texts)
        print(f"[texte] Versuch {attempt} ({model}): {'OK' if not problems else problems}")
        if not problems:
            break
        feedback = "\n\nYour previous answer broke these rules, fix them and return the complete JSON again:\n- " + "\n- ".join(problems)
    assert texts is not None, "keine lesbare Antwort"
    state["texts"] = {k: assemble(v) for k, v in texts.items()}
    state["texts_meta"] = {"model": model, "problems": problems}
    if not problems:
        wa, wb = content_words(full_text(texts["A"])), content_words(full_text(texts["B"]))
        state["texts_meta"]["word_overlap"] = sorted(wa & wb)
    for key, room in ROOMS.items():
        (OUT / "upload").mkdir(exist_ok=True)
        (OUT / "upload" / f"texte_{key}.txt").write_text(text_file(key, room, state["texts"][key]), encoding="utf-8")
    save_state(state)


def text_file(key: str, room: dict, t: dict) -> str:
    return "\n".join([
        f"YOIN Rooms Bildtest 2026-10-30 – Bild {key}: {room['name']} (Viertel: {room['district']}, Tokyo)", "",
        "1. VIDEOTITEL-VORSCHLAG", t["title"], "",
        "2. BESCHREIBUNG FÜR YOUTUBE", t["description"], "",
        "3. TEXT IM VIDEO (VORSPANN-ZEILE)", t["intro_line"], "",
        "4. ANPINN-KOMMENTAR", t["pin_comment"], "",
        "5. COMMUNITY-POST", t["community_post"], ""])


# ------------------------------------------------------------------ Stufe 4: Drive

def stage_drive(state: dict) -> None:
    up = OUT / "upload"
    up.mkdir(exist_ok=True)
    files = []
    for key in ROOMS:
        for src, name in ((OUT / f"hauptbild_{key}.png", f"hauptbild_{key}.png"), (OUT / f"thumbnail_{key}.png", f"thumbnail_{key}.png"),
                          (up / f"texte_{key}.txt", f"texte_{key}.txt")):
            dst = up / name
            if src != dst and src.exists():
                dst.write_bytes(src.read_bytes())
            if dst.exists():
                files.append(dst)
    r = subprocess.run([sys.executable, str(HERE / "drive_share_upload.py"), "--path", DRIVE_PATH, "--next-to", "AIX WALKER Mixe", *map(str, files)],
                       capture_output=True, text=True, timeout=1800)
    sys.stderr.write(r.stderr[-1500:])
    if r.returncode != 0:
        raise RuntimeError(f"Drive-Upload fehlgeschlagen: {r.stderr[-600:]}")
    state["drive"] = json.loads(r.stdout[r.stdout.index("{"):])
    save_state(state)
    d = state["drive"]
    print(f"[drive] Ordner: {d['folder']} ({d['folder_access']})")
    for n, v in d["files"].items():
        print(f"[drive] {n}: {v['link']} ({v['access']}, {v['bytes']} von {v['local_bytes']} Bytes)")


# ------------------------------------------------------------------ Stufe 5: Mail

def build_mail(state: dict) -> str:
    d, c, fnt = state["drive"], state["cost"], state["font"]
    lines = ["Hallo Rolf,", "",
             "hier der Sichttest für YOIN Rooms: zwei Hauptbilder (Nano Banana Pro, 4K, 16:9) mit Ausblick auf je ein Tokyoter Viertel, "
             "dazu Thumbnail und die fünf Texte pro Bild. Es wurde NICHTS an Musik, Video, YouTube, DistroKid oder den Aix-Walker-Mixen "
             "gemacht; geplante Aufgaben sind unverändert.", "",
             f"Drive-Ordner (Link-Freigabe, Leser): {d['folder']}", ""]
    for key, room in ROOMS.items():
        t, im, th = state["texts"][key], state["images"][key], state["thumbs"].get(key, {})
        lines += ["=" * 70, f"BILD {key}: {room['name']}   (Viertel: {room['district']}, Tokyo)", "=" * 70,
                  f"Hauptbild (4K, ohne Text): {d['files'][f'hauptbild_{key}.png']['link']}" if f"hauptbild_{key}.png" in d["files"] else "Hauptbild: FEHLT",
                  f"Thumbnail (1280×720): {d['files'][f'thumbnail_{key}.png']['link']}" if f"thumbnail_{key}.png" in d["files"] else "Thumbnail: FEHLT",
                  f"Alle Texte als Datei: {d['files'][f'texte_{key}.txt']['link']}", "",
                  "1) VIDEOTITEL-VORSCHLAG", t["title"], "",
                  "2) BESCHREIBUNG FÜR YOUTUBE", t["description"], "",
                  "3) TEXT IM VIDEO (VORSPANN-ZEILE)", t["intro_line"], "",
                  "4) ANPINN-KOMMENTAR", t["pin_comment"], "",
                  "5) COMMUNITY-POST", t["community_post"], ""]
    eur_total = c["eur"]
    n_img = c["image_pro_4k"] + c["image_pro"]
    lines += ["=" * 70, "TECHNIK UND KOSTEN", "=" * 70,
              f"Bildkosten tatsächlich: {eur(eur_total)} € ({n_img} erzeugte Bilder, {eur(c['usd'])} $ bei ca. 0,24 $ je 4K-Bild, Kurs 0,92). "
              f"Die Texte kommen über die Claude-API (Modell {state['texts_meta']['model']}), das ist in dieser Summe nicht enthalten.",
              ("Schrift: Cormorant Garamond Light wurde verwendet – " if fnt["cormorant_light"] else "Schrift: Cormorant Garamond Light war NICHT verfügbar – ")
              + fnt["desc"] + ".",
              "Bildformat: " + ", ".join(f"{k}: {im['size'][0]}×{im['size'][1]} px" for k, im in state["images"].items() if im.get("ok")) + ".",
              "Prompt: Basisprompt wortgetreu, Bild B nur an den beiden genannten Stellen geändert; kein Standard-Suffix angehängt (style leer)."]
    for key in ROOMS:
        th = state["thumbs"].get(key)
        if th:
            verdict = th.get("visual_320") or ("lesbar" if th["readable_320"] else "GRENZWERTIG")
            lines.append(f"Thumbnail {key}: Textbreite {de(th['width_px'])} von {TW} px = {de(round(th['width_frac'] * 100, 1))} %, Textmitte "
                         f"({de(th['center_x'])} | {de(th['center_y'])}) bei Bildmitte ({TW // 2} | {TH // 2}), Text vollständig im Bild; "
                         f"Kontrast Creme gegen den Untergrund direkt um die Buchstaben {de(th['contrast_ratio_median'])}:1 (Median) und "
                         f"{de(th['contrast_ratio_p90'])}:1 (an den hellsten Stellen; Faustregel 4,5:1); bei 320 px Breite Versalhöhe ca. "
                         f"{de(th['cap_height_px_320'])} px – {verdict}."
                         + (" Mit weichem dunklem Schatten direkt an der Schrift (von dir nicht verlangt, nur für die Lesbarkeit)." if th.get("shadow") else ""))
    notes = state.get("notes", [])
    for key, im in state["images"].items():
        if im["attempts"] > 1 or not im.get("ok"):
            notes.append(f"Bild {key}: {im['attempts']} Anläufe" + ("" if im.get("ok") else " – KEIN Bild erhalten") + "; Log: " + " | ".join(im["log"])[:400])
    if state["texts_meta"]["problems"]:
        notes.append("Texte: Prüfung nicht ganz bestanden: " + "; ".join(state["texts_meta"]["problems"]))
    lines += ["", "Hinweise / Fehler / Neuversuche:", *([f"- {n}" for n in notes] or ["- keine Fehler, kein Neuversuch nötig."]), "",
              "Bitte kurz dein Urteil:", "1. Bildwirkung (beide Bilder)?", "2. Ist der Viertel-Bezug im Bild sichtbar (Daikanyama vs. Nakameguro)?",
              "3. Text und Thumbnail (Schrift, Größe, Lesbarkeit)?", "4. Beschreibung und die übrigen Texte?", "", "Danke!", "Claude"]
    return "\n".join(lines)


def stage_mail(state: dict) -> None:
    flag = OUT / "mail_sent.json"
    if flag.exists():
        print(f"[mail] bereits gesendet ({flag.read_text()}), es geht keine zweite Mail raus")
        return
    from pipeline import mailer
    text = build_mail(state)
    (OUT / "mail.txt").write_text(text, encoding="utf-8")
    msg = EmailMessage()
    msg["To"] = MAIL_TO
    msg["From"] = "me"
    msg["Subject"] = MAIL_SUBJECT
    msg.set_content(text)                           # Plain-Text, kein HTML
    for key in ROOMS:
        p = OUT / f"thumbnail_{key}.png"
        if p.exists():
            msg.add_attachment(p.read_bytes(), maintype="image", subtype="png", filename=f"thumbnail_{key}.png")
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    r = mailer._service().users().messages().send(userId="me", body={"raw": raw}).execute()
    flag.write_text(json.dumps({"id": r.get("id"), "to": MAIL_TO}))
    print(f"[mail] gesendet an {MAIL_TO}: {r.get('id')}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["images", "thumbs", "texts", "drive", "mail", "all"], required=True)
    ap.add_argument("--shadow", action="store_true", help="sehr weicher Schatten direkt an der Thumbnail-Schrift")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    state = load_state()
    todo = ["images", "thumbs", "texts", "drive", "mail"] if a.stage == "all" else [a.stage]
    for st in todo:
        {"images": lambda: stage_images(state), "thumbs": lambda: stage_thumbs(state, a.shadow), "texts": lambda: stage_texts(state),
         "drive": lambda: stage_drive(state), "mail": lambda: stage_mail(state)}[st]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
