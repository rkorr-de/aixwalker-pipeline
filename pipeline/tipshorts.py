"""Tipp-Shorts (Wachstumsplan 2026/27, Säulen 2 und 3 – Rolf 15.10.2026):

- „wellness“:   „Sleep & Relax Tips“ – ein belegter Tipp zu Schlaf/Entspannung, führt zu einem Spa- bzw. Sleep-Mix
- „dolcevita“:  „Dolce Vita / Luxury Escapes“ – ein Ort an der Amalfiküste/am Comer See mit 2–3 echten Fakten,
                 führt zum neuesten Italien-Mix

Die Themen liegen als Warteschlange in Drive („AIX WALKER Mixe/_memory/tip_queue.json“). Die Sonntags-Recherche
(eigene Routine, mit Websuche) füllt sie über `python run_tip_short.py --add <datei.json>`; beim allerersten Lauf
wird sie aus `tips/seed.json` im Repository angelegt. Ein Eintrag:

  {"id": "wellness-bedroom-temp", "kind": "wellness", "label": "SLEEP TIP",
   "hook": "Your bedroom might be too warm",
   "lines": ["Most people sleep best in a cool room.", "Aim for about 16–19 °C (60–67 °F)."],
   "scene": "Bildbeschreibung (Englisch, outdoor oder Spa, ohne Text)",
   "music_genre": "Chillout Sleep",            # Musik + Ziel-Mix: Chillout Sleep | Dark Ambient Spa |
                                                #   Mediterranean Spa Lounge | Italian Chillout
   "sources": [{"title": "…", "url": "https://…"}],
   "used": null}                                 # Datum, sobald hochgeladen

Text im Bild und alle Metadaten Englisch. Keine Heilversprechen, keine Medikamente (prüft validate_entry grob).
"""
import json
import re
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

from . import config, shorts
from .images import (_draw_tracked, _fit_tracked, _font, _soft_shadow, _tracked_width, _wrap, crop_aspect)

KINDS = ("wellness", "dolcevita")
MUSIC_GENRES = ("Chillout Sleep", "Dark Ambient Spa", "Mediterranean Spa Lounge", "Italian Chillout")
QUEUE_NAME = "tip_queue.json"
SEED = config.ROOT / "tips" / "seed.json"
LOCAL_QUEUE = config.ROOT / "build" / "tip_queue.local.json"

# Grobe Sicherung gegen Heilversprechen/Medizinisches (Rolf 15.10.2026: nur allgemeine Wellness)
_BANNED = re.compile(r"\b(cure[sd]?|heal[s]?|treat(s|ment)?|insomnia disorder|medication|melatonin|pill[s]?|dose|"
                     r"diagnos\w*|disease|depression|anxiety disorder|guaranteed)\b", re.I)


def validate_entry(e: dict) -> list[str]:
    """Liefert eine Liste von Problemen (leer = in Ordnung)."""
    p = []
    if e.get("kind") not in KINDS:
        p.append(f"kind muss {KINDS} sein")
    if not re.fullmatch(r"[a-z0-9-]{3,60}", str(e.get("id", ""))):
        p.append("id: 3–60 Zeichen a-z, 0-9, -")
    hook = str(e.get("hook", ""))
    if not 8 <= len(hook) <= 48:
        p.append("hook: 8–48 Zeichen")
    lines = e.get("lines") or []
    if not 2 <= len(lines) <= 3 or any(not 6 <= len(str(x)) <= 46 for x in lines):
        p.append("lines: 2–3 Zeilen mit je 6–46 Zeichen (sonst wird die Schrift zu klein)")
    if not 4 <= len(str(e.get("label", ""))) <= 18:
        p.append("label: 4–18 Zeichen (z. B. SLEEP TIP, RELAX TIP, DOLCE VITA)")
    if len(str(e.get("scene", ""))) < 40:
        p.append("scene: Bildbeschreibung fehlt/zu kurz")
    if e.get("music_genre") not in MUSIC_GENRES:
        p.append(f"music_genre muss {MUSIC_GENRES} sein")
    srcs = e.get("sources") or []
    if not srcs or any(not str(s.get("url", "")).startswith("https://") for s in srcs):
        p.append("sources: mindestens eine https-Quelle")
    text = " ".join([hook, *map(str, lines)])
    if e.get("kind") == "wellness" and _BANNED.search(text):
        p.append(f"medizinisches Wort im Text: {_BANNED.search(text).group(0)}")
    if re.search(r"[^\x00-ɏ–—’° ]", text.replace("°", "")):
        p.append("bitte keine Emojis/Sonderzeichen im Bildtext (die Schrift kann sie nicht)")
    return p


# ---------------------------------------------------------------- Warteschlange (Drive, Rückfall lokal)

def _drive():
    from . import drive
    svc = drive.service()
    return drive, svc, drive.memory_folder(svc)


def load_queue(use_drive: bool) -> list[dict]:
    if use_drive:
        drive, svc, folder = _drive()
        fid = drive.find_file(svc, QUEUE_NAME, folder)
        if fid:
            return json.loads(drive.read_text(svc, fid))
    elif LOCAL_QUEUE.exists():
        return json.loads(LOCAL_QUEUE.read_text(encoding="utf-8"))
    return json.loads(SEED.read_text(encoding="utf-8")) if SEED.exists() else []


def save_queue(queue: list[dict], use_drive: bool) -> None:
    text = json.dumps(queue, indent=2, ensure_ascii=False)
    if use_drive:
        drive, svc, folder = _drive()
        drive.write_text(svc, QUEUE_NAME, text, folder)
    else:
        LOCAL_QUEUE.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_QUEUE.write_text(text, encoding="utf-8")


def add_entries(queue: list[dict], new: list[dict]) -> tuple[int, list[str]]:
    """Hängt gültige, noch unbekannte Einträge an. Liefert (Anzahl, Meldungen)."""
    known = {e["id"] for e in queue}
    known_hooks = {e["hook"].lower() for e in queue}
    added, msgs = 0, []
    for e in new:
        probs = validate_entry(e)
        if e.get("id") in known or str(e.get("hook", "")).lower() in known_hooks:
            probs.append("schon in der Warteschlange")
        if probs:
            msgs.append(f"{e.get('id', '?')}: übersprungen – {'; '.join(probs)}")
            continue
        queue.append({**e, "used": None, "added": date.today().isoformat()})
        known.add(e["id"])
        known_hooks.add(e["hook"].lower())
        added += 1
    return added, msgs


def next_entry(queue: list[dict], kind: str) -> dict | None:
    return next((e for e in queue if e.get("kind") == kind and not e.get("used")), None)


# ---------------------------------------------------------------- Bild

def _balanced(d, text: str, font, max_w: int) -> list[str]:
    """Passt die Zeile nicht, wird sie in zwei etwa gleich lange Hälften geteilt (kein einzelnes Wort allein)."""
    if d.textlength(text, font=font) <= max_w:
        return [text]
    words = text.split()
    best = None
    for k in range(1, len(words)):
        a, b = " ".join(words[:k]), " ".join(words[k:])
        wmax = max(d.textlength(a, font=font), d.textlength(b, font=font))
        if best is None or wmax < best[0]:
            best = (wmax, [a, b])
    return best[1] if best and best[0] <= max_w else _wrap(d, text, font, max_w)


def make_tip_frame(art: Image.Image, label: str, hook: str, lines: list[str], out: Path,
                   pill_label: str = "FULL MIX · LINK BELOW", w: int = 1080, h: int = 1920) -> Path:
    """9:16-Bild: Hauptbild randlos, oben Kennzeile + Hook (Cinzel, 3D-Schatten), darunter der Tipp in 2–3 Zeilen,
    unten der leuchtende Knopf. Gleicher sicherer Bereich wie die Musik-Shorts (shorts.SAFE_TOP/SAFE_BOTTOM).
    Schreibt <out>.layout.json für visuals.build_short_animated (atmendes Licht um den Knopf)."""
    a = art.convert("RGB")
    if abs(a.width / a.height - w / h) > 0.01:
        a = crop_aspect(a, 9, 16)
    bg = a.resize((w, h), Image.LANCZOS)
    bg = ImageEnhance.Contrast(ImageEnhance.Color(bg).enhance(1.08)).enhance(1.04)
    # Abdunkeln: oben stärker (Hook + Tipp stehen dort), unten für die App-Zone
    ov = Image.new("L", (w, h), 0)
    od = ImageDraw.Draw(ov)
    for yy in range(h):
        a_ = 0
        if yy < 1150:
            a_ = int(175 * (1 - yy / 1150) ** 1.25)
        elif yy > 1080:
            a_ = int(185 * ((yy - 1080) / (h - 1080)) ** 1.5)
        od.line([(0, yy), (w, yy)], fill=a_)
    bg = Image.composite(Image.new("RGB", (w, h), (6, 8, 12)), bg, ov)
    d = ImageDraw.Draw(bg)
    boxes: list[tuple[int, int, int, int]] = []
    y = shorts.SAFE_TOP

    # 1) Kennzeile (SLEEP TIP / DOLCE VITA)
    kw = label.upper()
    fk = _fit_tracked(d, kw, config.FONT_TITLE, 780, 46, 30, 0.22, "Bold")
    tk = fk.size * 0.22
    kx = (w - _tracked_width(d, kw, fk, tk)) / 2
    kb = d.textbbox((0, 0), kw, font=fk)
    _soft_shadow(bg, lambda md: _draw_tracked(md, (kx, y - kb[1]), kw, fk, 255, tk), radius=10, alpha=170)
    d = ImageDraw.Draw(bg)
    _draw_tracked(d, (kx, y - kb[1]), kw, fk, config.CREAM, tk)
    boxes.append((int(kx), y, int(kx + _tracked_width(d, kw, fk, tk)), y + kb[3] - kb[1]))
    y += kb[3] - kb[1] + 34

    # 2) Hook groß (max. 3 Zeilen)
    hk = hook.upper().strip()
    size = 112
    while True:
        fh = _font(config.FONT_HEAD, size, "Bold")
        hl = _wrap(d, hk, fh, w - 2 * 90)
        if len(hl) <= 3 or size <= 64:
            break
        size -= 4
    hl = hl[:3]
    lh = int(fh.size * 1.06)
    hb = [d.textbbox((0, 0), ln, font=fh) for ln in hl]
    pos = [((w - (b[2] - b[0])) / 2 - b[0], y - hb[0][1] + i * lh) for i, (ln, b) in enumerate(zip(hl, hb))]

    def paint_hook(md):
        for (x, yy), ln in zip(pos, hl):
            md.text((x, yy), ln, font=fh, fill=255)

    shorts._extrude(bg, paint_hook, lambda dd, dx, dy, col: [dd.text((x + dx, yy + dy), ln, font=fh, fill=col)
                                                             for (x, yy), ln in zip(pos, hl)], fh.size)
    d = ImageDraw.Draw(bg)
    for (x, yy), ln in zip(pos, hl):
        d.text((x, yy), ln, font=fh, fill=config.WHITE)
        bb = d.textbbox((x, yy), ln, font=fh)
        boxes.append((bb[0], bb[1], bb[2] + 8, bb[3] + 8))
    y = max(b[3] for b in boxes) + 56

    # 3) Tipp-Zeilen (Manrope, hell, weicher Schatten); unterhalb y≈950 nur schmal (Like-Spalte rechts)
    tsize = 54
    while True:
        ft = _font(config.FONT_BODY, tsize, "SemiBold")
        wrapped: list[str] = []
        for ln in lines:
            wrapped += _balanced(d, ln, ft, 860)
        tl = int(ft.size * 1.32)
        bottom = y + tl * len(wrapped)
        wide_low = any(d.textbbox((0, 0), ln, font=ft)[2] > shorts.LOW_MAX_W
                       for i, ln in enumerate(wrapped) if y + (i + 1) * tl > 940)
        ok = bottom < 1020 and not wide_low and len(wrapped) <= 6
        single = len(wrapped) == len(lines)          # jede Aussage in einer Zeile – erst ab 44 px wird umgebrochen
        if (ok and (single or tsize <= 44)) or tsize <= 38:
            break
        tsize -= 2
    tpos = []
    for i, ln in enumerate(wrapped):
        b = d.textbbox((0, 0), ln, font=ft)
        tpos.append(((w - (b[2] - b[0])) / 2 - b[0], y + i * tl - b[1], ln))

    def paint_tip(md):
        for x, yy, ln in tpos:
            md.text((x, yy), ln, font=ft, fill=255)

    _soft_shadow(bg, paint_tip, radius=12, alpha=200)
    _soft_shadow(bg, paint_tip, radius=3, alpha=170, offset=(2, 3))
    d = ImageDraw.Draw(bg)
    for x, yy, ln in tpos:
        d.text((x, yy), ln, font=ft, fill=config.WHITE)
        bb = d.textbbox((x, yy), ln, font=ft)
        boxes.append((bb[0], bb[1], bb[2] + 4, bb[3] + 4))

    # 4) Knopf unten (wie bei den Musik-Shorts)
    fp = _fit_tracked(d, pill_label, config.FONT_TITLE, shorts.LOW_MAX_W - 2 * 54 - 56, 42, 28, 0.10, "Bold")
    tp = fp.size * 0.10
    lb = d.textbbox((0, 0), pill_label, font=fp)
    tri = int(fp.size * 0.78)
    pw = int(54 + tri + 26 + _tracked_width(d, pill_label, fp, tp) + 54)
    ph = int(fp.size * 2.45)
    px0, py1 = (w - pw) // 2, shorts.SAFE_BOTTOM
    py0 = py1 - ph
    pill = (px0, py0, px0 + pw, py1)
    _soft_shadow(bg, lambda md: md.rounded_rectangle(pill, radius=ph // 2, fill=255), radius=22, alpha=150,
                 offset=(0, 8))
    d = ImageDraw.Draw(bg)
    d.rounded_rectangle(pill, radius=ph // 2, fill=config.CREAM)
    cy = (py0 + py1) // 2
    tx0 = px0 + 54
    ink = (24, 26, 30)
    d.polygon([(tx0, cy - tri // 2), (tx0, cy + tri // 2), (tx0 + int(tri * 0.86), cy)], fill=ink)
    _draw_tracked(d, (tx0 + tri + 26, cy - (lb[1] + lb[3]) / 2), pill_label, fp, ink, tp)

    shorts._check_no_overlap(boxes + [pill])
    out.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out, "PNG")
    Path(str(out) + ".layout.json").write_text(json.dumps({"cover": pill, "text": boxes, "kind": "pill"}))
    return out


# ---------------------------------------------------------------- Metadaten (Englisch)

TAGS = {
    "wellness": ["sleep tips", "relaxation tips", "how to sleep better", "sleep music", "relaxing music",
                 "spa music", "wellness", "self care", "calm music", "shorts"],
    "dolcevita": ["dolce vita", "amalfi coast", "lake como", "italy travel", "italian chillout music",
                  "italian lounge music", "luxury travel", "italy", "travel italy", "shorts"],
}
HASHTAGS = {"wellness": "#sleeptips #relaxing #spamusic #Shorts",
            "dolcevita": "#dolcevita #italy #italianmusic #Shorts"}


def short_title(e: dict) -> str:
    tail = "Sleep & Relax Tips" if e["kind"] == "wellness" else "Dolce Vita · Italian Chillout"
    t = f"{e['hook']} – {tail}"
    return f"{t[:100 - len(' #Shorts')].rstrip()} #Shorts"


def short_description(e: dict, mix: dict | None) -> str:
    body = "\n".join(e["lines"])
    srcs = "\n".join(f"Source: {s.get('title') or s['url']} – {s['url']}" for s in e.get("sources", []))
    if mix and mix.get("video_id"):
        full = f"🎧 Full mix: {mix.get('yt_title') or mix.get('album')} – https://youtu.be/{mix['video_id']}"
    else:
        full = f"🎧 More calm music: {config.CHANNEL_URL}"
    note = ("General wellness information, not medical advice." if e["kind"] == "wellness"
            else "Mood visuals are AI-generated; places and facts are real.")
    return (f"{e['hook']}\n\n{body}\n\n{full}\n\n{srcs}\n\n{note}\nVisuals AI-generated. Original music by "
            f"{config.ARTIST} (AI-assisted).\n\n{HASHTAGS[e['kind']]}")


# ---------------------------------------------------------------- Moderner Look (Rolf 15.10.2026, 21:18)
# „Modern, mit moderner viraler Schrift und Design“ – Recherche (editoria.in, blitzcutai.com, 2026): fette serifenlose
# Versalien (Montserrat ExtraBold/Black ist die meistgenutzte Short-Schrift), weiß mit dunkler Kontur, EIN Schlüsselwort
# farbig hervorgehoben, Text in kurzen Blöcken, die nacheinander erscheinen, mittig, nie im unteren App-Bereich.
# Umsetzung: Label-Chip oben, Hook in Montserrat Black mit dicker Kontur + goldenem Schlüsselwort, Tipp-Zeilen als
# weiße Textboxen (TikTok-Stil), die nacheinander einblenden, langsamer Zoom ins Bild, Knopf „FULL MIX“ unten.

GOLD = (255, 201, 77)
INK = (18, 20, 24)
REVEAL_FIRST, REVEAL_STEP = 1.4, 2.2      # Sekunden: erste Tipp-Box, Abstand der weiteren
CTA_AT = 0.6


def _mont(size: int, weight: str = "Black"):
    return _font(config.FONT_TITLE, size, weight)


def _layer(w: int = 1080, h: int = 1920) -> Image.Image:
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def _pick_highlight(hook: str, wanted: str | None) -> str:
    words = [re.sub(r"[^\w°-]", "", x) for x in hook.split()]
    if wanted and wanted.upper() in hook.upper():
        return wanted.upper()
    num = next((x for x in words if re.search(r"\d", x)), None)
    if num:
        return num.upper()
    long_ = sorted((x for x in words if len(x) > 3), key=len, reverse=True)
    return (long_[0] if long_ else words[-1]).upper()


def build_layers(art: Image.Image, entry: dict, out_dir: Path, pill_label: str = "FULL MIX · LINK BELOW",
                 w: int = 1080, h: int = 1920) -> dict:
    """Erzeugt die Ebenen als PNG (Hintergrund groß für den Zoom, Abdunklung, Label, Hook, Tipp-Boxen, Knopf) und
    eine Vorschau mit allen Ebenen. Prüft den sicheren Bereich. Liefert {bg, shade, label, hook, tips[], cta, preview,
    layout}."""
    out_dir.mkdir(parents=True, exist_ok=True)
    a = art.convert("RGB")
    if abs(a.width / a.height - w / h) > 0.01:
        if a.width / a.height > w / h:
            # Querformat/Quadrat → Hochkant-Ausschnitt; bei Dolce Vita etwas nach rechts (dort steht die Frau im Italien-Bild)
            cw = int(a.height * w / h)
            cx = int((a.width - cw) * (0.68 if entry.get("kind") == "dolcevita" else 0.5))
            a = a.crop((cx, 0, cx + cw, a.height))
        else:
            a = crop_aspect(a, 9, 16)
    zw, zh = int(w * 1.08) // 2 * 2, int(h * 1.08) // 2 * 2
    bg = ImageEnhance.Contrast(ImageEnhance.Color(a.resize((zw, zh), Image.LANCZOS)).enhance(1.10)).enhance(1.05)
    bg.save(out_dir / "L0_bg.png")

    # Abdunklung oben (Text) und unten (App-Bereich)
    shade = _layer(w, h)
    sd = ImageDraw.Draw(shade)
    for yy in range(h):
        a_ = int(165 * (1 - yy / 1250) ** 1.3) if yy < 1250 else 0
        if yy > 1150:
            a_ = max(a_, int(190 * ((yy - 1150) / (h - 1150)) ** 1.4))
        sd.line([(0, yy), (w, yy)], fill=(6, 8, 12, a_))
    shade.save(out_dir / "L1_shade.png")

    probe = ImageDraw.Draw(_layer(10, 10))
    boxes: list[tuple[int, int, int, int]] = []

    # 1) Label-Chip (gold, dunkle Schrift)
    lab = entry["label"].upper()
    fl = _mont(38, "ExtraBold")
    tl = fl.size * 0.16
    lw = _tracked_width(probe, lab, fl, tl)
    lb = probe.textbbox((0, 0), lab, font=fl)
    cw, ch = int(lw + 2 * 30), int((lb[3] - lb[1]) + 2 * 18)
    cx0, cy0 = (w - cw) // 2, shorts.SAFE_TOP
    label = _layer(w, h)
    _soft_shadow(label, lambda md: md.rounded_rectangle((cx0, cy0, cx0 + cw, cy0 + ch), radius=ch // 2, fill=255),
                 radius=14, alpha=120, offset=(0, 6))
    ld = ImageDraw.Draw(label)
    ld.rounded_rectangle((cx0, cy0, cx0 + cw, cy0 + ch), radius=ch // 2, fill=GOLD + (255,))
    _draw_tracked(ld, (cx0 + 30, cy0 + 18 - lb[1]), lab, fl, INK + (255,), tl)
    boxes.append((cx0, cy0, cx0 + cw, cy0 + ch))
    label.save(out_dir / "L2_label.png")
    y = cy0 + ch + 34

    # 2) Hook: Montserrat Black, Versalien, dicke Kontur, Schlüsselwort gold (max. 3 Zeilen)
    hook = entry["hook"].upper().strip()
    hl_word = _pick_highlight(hook, entry.get("highlight"))
    size = 108
    while True:
        fh = _mont(size, "Black")
        lines = _wrap(probe, hook, fh, w - 2 * 80)
        if len(lines) <= 3 or size <= 60:
            break
        size -= 4
    lines = lines[:3]
    stroke = max(5, int(fh.size * 0.085))
    lh = int(fh.size * 1.08)
    hook_l = _layer(w, h)
    paint = []
    for i, ln in enumerate(lines):
        bb = probe.textbbox((0, 0), ln, font=fh, stroke_width=stroke)
        x = (w - (bb[2] - bb[0])) / 2 - bb[0]
        yy = y + i * lh - bb[1]
        paint.append((x, yy, ln))
        boxes.append((int(x + bb[0]), int(yy + bb[1]), int(x + bb[2]), int(yy + bb[3])))
    _soft_shadow(hook_l, lambda md: [md.text((x, yy), ln, font=fh, fill=255, stroke_width=stroke, stroke_fill=255)
                                     for x, yy, ln in paint], radius=18, alpha=140, offset=(0, 8))
    hd = ImageDraw.Draw(hook_l)
    space = probe.textlength(" ", font=fh)
    for x, yy, ln in paint:
        cx = x
        for wd in ln.split(" "):
            plain = re.sub(r"[^\w°-]", "", wd)
            col = GOLD if plain and plain == hl_word else config.WHITE
            hd.text((cx, yy), wd, font=fh, fill=col + (255,), stroke_width=stroke, stroke_fill=INK + (255,))
            cx += probe.textlength(wd, font=fh) + space
    hook_l.save(out_dir / "L3_hook.png")
    y = max(b[3] for b in boxes) + 46

    # 3) Tipp-Boxen (weiß, dunkle Schrift, abgerundet) – je Aussage eine Box, nacheinander eingeblendet
    pill_h_est = 110
    limit = shorts.SAFE_BOTTOM - pill_h_est - 40
    tsize = 46
    while True:
        ft = _mont(tsize, "Bold")
        blocks = [_balanced(probe, t, ft, 640) for t in entry["lines"]]
        lhh = int(ft.size * 1.22)
        heights = [len(bl) * lhh + 2 * 16 for bl in blocks]
        bottom = y + sum(heights) + 18 * (len(blocks) - 1)
        widest = max(probe.textlength(s, font=ft) for bl in blocks for s in bl)
        if (bottom <= limit and widest <= 640) or tsize <= 34:
            break
        tsize -= 2
    tips = []
    for k, (bl, hh) in enumerate(zip(blocks, heights)):
        bw = int(max(probe.textlength(s, font=ft) for s in bl) + 2 * 26)
        bx0 = (w - bw) // 2
        layer = _layer(w, h)
        _soft_shadow(layer, lambda md: md.rounded_rectangle((bx0, y, bx0 + bw, y + hh), radius=20, fill=255),
                     radius=16, alpha=110, offset=(0, 6))
        dd = ImageDraw.Draw(layer)
        dd.rounded_rectangle((bx0, y, bx0 + bw, y + hh), radius=20, fill=(255, 255, 255, 240))
        for i, s in enumerate(bl):
            sb = probe.textbbox((0, 0), s, font=ft)
            dd.text(((w - (sb[2] - sb[0])) / 2 - sb[0], y + 16 + i * lhh - sb[1] + (lhh - (sb[3] - sb[1])) / 2 - 2),
                    s, font=ft, fill=INK + (255,))
        boxes.append((bx0, y, bx0 + bw, y + hh))
        p = out_dir / f"L4_tip{k + 1}.png"
        layer.save(p)
        tips.append({"file": p, "at": round(REVEAL_FIRST + k * REVEAL_STEP, 2)})
        y += hh + 18

    # 4) Knopf unten (wie die Musik-Shorts, damit der Kanal wiedererkennbar bleibt)
    cta = _layer(w, h)
    cd = ImageDraw.Draw(cta)
    fp = _fit_tracked(cd, pill_label, config.FONT_TITLE, shorts.LOW_MAX_W - 2 * 54 - 56, 42, 28, 0.10, "Bold")
    tp = fp.size * 0.10
    pb = cd.textbbox((0, 0), pill_label, font=fp)
    tri = int(fp.size * 0.78)
    pw = int(54 + tri + 26 + _tracked_width(cd, pill_label, fp, tp) + 54)
    ph = int(fp.size * 2.45)
    px0, py1 = (w - pw) // 2, shorts.SAFE_BOTTOM
    py0 = py1 - ph
    pill = (px0, py0, px0 + pw, py1)
    _soft_shadow(cta, lambda md: md.rounded_rectangle(pill, radius=ph // 2, fill=255), radius=22, alpha=150,
                 offset=(0, 8))
    cd = ImageDraw.Draw(cta)
    cd.rounded_rectangle(pill, radius=ph // 2, fill=config.CREAM + (255,))
    cy = (py0 + py1) // 2
    tx0 = px0 + 54
    cd.polygon([(tx0, cy - tri // 2), (tx0, cy + tri // 2), (tx0 + int(tri * 0.86), cy)], fill=INK + (255,))
    _draw_tracked(cd, (tx0 + tri + 26, cy - (pb[1] + pb[3]) / 2), pill_label, fp, INK + (255,), tp)
    cta.save(out_dir / "L5_cta.png")

    shorts._check_no_overlap(boxes + [pill])

    # Vorschau (alle Ebenen, ohne Zoom) – dient auch als Bild im Drive-Ordner
    off = ((zw - w) // 2, (zh - h) // 2)
    prev = bg.crop((off[0], off[1], off[0] + w, off[1] + h)).convert("RGBA")
    for lay in (shade, label, hook_l, *[Image.open(t["file"]) for t in tips], cta):
        prev.alpha_composite(lay)
    preview = out_dir / "frame.png"
    prev.convert("RGB").save(preview)
    layout = {"text": boxes, "cta": pill, "highlight": hl_word, "tip_times": [t["at"] for t in tips]}
    (out_dir / "layout.json").write_text(json.dumps(layout))
    return {"bg": out_dir / "L0_bg.png", "shade": out_dir / "L1_shade.png", "label": out_dir / "L2_label.png",
            "hook": out_dir / "L3_hook.png", "tips": tips, "cta": out_dir / "L5_cta.png", "preview": preview,
            "layout": layout}


def render_video(layers: dict, wav: Path, start: float, dur: float, out: Path, fps: int = 30) -> Path:
    """Video 1080×1920: langsamer Zoom ins Bild (1,00 → 1,08), Label/Hook/Knopf blenden schnell ein, die Tipp-Boxen
    nacheinander („Pop“ mit kurzer Einblendung); Musik mit kurzem Fade."""
    import subprocess
    out.parent.mkdir(parents=True, exist_ok=True)
    inputs = ["-loop", "1", "-framerate", str(fps), "-t", f"{dur:.2f}", "-i", str(layers["bg"])]
    # Label + Hook ab dem ersten Bild sichtbar (das erste Bild entscheidet übers Weiterwischen)
    # Tipp-Boxen „poppen“: gleiten in 0,22 s aus 46 px darunter hoch und blenden dabei ein
    stills = [(layers["shade"], 0.0, 0.0, False), (layers["label"], 0.0, 0.0, False), (layers["hook"], 0.0, 0.0, False),
              *[(t["file"], t["at"], 0.2, True) for t in layers["tips"]], (layers["cta"], CTA_AT, 0.3, True)]
    for p, *_ in stills:
        inputs += ["-loop", "1", "-framerate", str(fps), "-t", f"{dur:.2f}", "-i", str(p)]
    ai = len(stills) + 1
    inputs += ["-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", str(wav)]
    g = [f"[0:v]scale=w='trunc((1080+86*t/{dur:.2f})/2)*2':h=-2:eval=frame,crop=1080:1920,setsar=1,format=rgba[b0]"]
    prev = "b0"
    for i, (_, at, fade, slide) in enumerate(stills, 1):
        src = f"[{i}:v]format=rgba"
        if fade > 0:
            src += f",fade=t=in:st={at:.2f}:d={fade:.2f}:alpha=1"
        g.append(f"{src}[s{i}]")
        y = f"'if(lt(t,{at:.2f}),46,46*max(0,1-(t-{at:.2f})/0.22)^2)'" if slide else "0"
        g.append(f"[{prev}][s{i}]overlay=x=0:y={y}:eval=frame:format=auto[b{i}]")
        prev = f"b{i}"
    g.append(f"[{prev}]format=yuv420p[v]")
    g.append(f"[{ai}:a]afade=t=in:d=0.3,afade=t=out:st={dur - 1.5:.2f}:d=1.5[aout]")
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y", *inputs, "-filter_complex", ";".join(g),
           "-map", "[v]", "-map", "[aout]", "-t", f"{dur:.2f}", "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out
