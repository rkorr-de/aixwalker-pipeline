#!/usr/bin/env python3
"""Kanalbanner-Entwürfe (Rolf, 08.10.2026): 3 Motive mit Nano Banana (Gemini-Bild-API), Text nur im sicheren Bereich
(1546×423 in der Mitte von 2560×1440 – auf Handy, PC und TV sichtbar). Ablage in Drive, Vorschau per E-Mail.
Kosten: 3 Hauptbilder (Pro, 4K) ≈ 0,72 $.

  python make_banners.py            # erzeugen, Drive, E-Mail
  python make_banners.py --dry-run  # Ersatzbilder, nur lokal (Layout prüfen)
"""
import argparse
import base64
import sys
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from PIL import Image, ImageDraw

from pipeline import config, images

W, H = 2560, 1440
SAFE = (W - 1546) // 2, (H - 423) // 2, (W + 1546) // 2, (H + 423) // 2

TITLE = "AIX WALKER"
TAGLINE = "ITALIAN CHILLOUT  ·  SPA LOUNGE  ·  SLEEP MUSIC"
SCRIPT = "music for slow evenings"

_FRAME = (" Ultra-wide panoramic banner composition: the CENTRAL horizontal band (middle third of the height, middle 60 % of "
          "the width) must be calm and uncluttered – open sky, sea or lake – because large text is placed there. "
          "Interesting details only towards the left and right edges.")
SCENES = [
    ("Amalfi Sunset Dinner",
     "Professional editorial travel photograph, wide panorama of the Amalfi Coast at golden-hour sunset: pastel cliffside "
     "village of Positano on the left, calm glittering sea and soft orange-pink sky in the middle, on the right a candlelit "
     "dinner terrace with white linen, lemons and wine glasses and an elegant woman in a red silk evening gown looking at "
     "the sunset (small in the frame, at the right edge).", "Italian Chillout"),
    ("Mediterranean Spa Lounge",
     "Professional luxury resort photograph, wide panorama of an infinity pool lounge high above the Mediterranean at "
     "sunset: white daybeds and lanterns on the left, still turquoise pool edge melting into a calm golden sea and pink sky "
     "in the middle, bougainvillea and a white villa terrace on the right. No people.", "Mediterranean Spa Lounge"),
    ("Lake Como Blue Hour",
     "Professional editorial travel photograph, wide panorama of Lake Como at blue hour: a villa terrace with a stone "
     "balustrade, candles and two glasses of red wine on the left, the calm mirror-like lake with soft mountain silhouettes "
     "and a few warm village lights in the middle, cypress trees and a classic wooden motorboat on the right. Deep blue sky "
     "with a last warm glow on the horizon, serene and dreamy.", "Chillout Sleep"),
]


def _text(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    x0, y0, x1, y1 = SAFE
    sw, sh = x1 - x0, y1 - y0
    d = ImageDraw.Draw(img)
    ft = images._fit_tracked(d, TITLE, config.FONT_HEAD, int(sw * 0.86), int(sh * 0.50), 60, 0.08, "Bold")
    fg = images._fit_tracked(d, TAGLINE, config.FONT_TITLE, int(sw * 0.80), int(sh * 0.10), 18, 0.25, "SemiBold")
    fs = images._fit_text(d, SCRIPT, config.FONT_SCRIPT, int(sw * 0.7), int(sh * 0.27), 30)
    tw = images._tracked_width(d, TITLE, ft, ft.size * 0.08)
    gw = images._tracked_width(d, TAGLINE, fg, fg.size * 0.25)
    sb = d.textbbox((0, 0), SCRIPT, font=fs)
    gap = int(sh * 0.05)
    th = ft.size
    total = th + gap + (sb[3] - sb[1]) + gap + fg.size
    top = y0 + (sh - total) // 2
    pos_t = ((W - tw) / 2, top - d.textbbox((0, 0), TITLE, font=ft)[1])
    pos_s = ((W - (sb[2] - sb[0])) / 2 - sb[0], top + th + gap - sb[1])
    pos_g = ((W - gw) / 2, top + th + gap + (sb[3] - sb[1]) + gap)

    def paint(md):
        images._draw_tracked(md, pos_t, TITLE, ft, 255, ft.size * 0.08)
        md.text(pos_s, SCRIPT, font=fs, fill=255)
        images._draw_tracked(md, pos_g, TAGLINE, fg, 255, fg.size * 0.25)
    images._soft_shadow(img, paint, radius=max(8, ft.size * 0.35), alpha=140)
    images._soft_shadow(img, paint, radius=4, alpha=170, offset=(4, 5))
    d = ImageDraw.Draw(img)
    images._draw_tracked(d, pos_t, TITLE, ft, config.WHITE, ft.size * 0.08)
    d.text(pos_s, SCRIPT, font=fs, fill=config.CREAM)
    images._draw_tracked(d, pos_g, TAGLINE, fg, config.WHITE, fg.size * 0.25)
    return img


def _fit(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    sc = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * sc) + 1, int(img.height * sc) + 1), Image.LANCZOS)
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    out = config.ROOT / "build" / "banner"
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for i, (name, prompt, genre) in enumerate(SCENES, 1):
        if args.dry_run:
            art = images.procedural_art("16:9", seed=i)
        else:
            art = images.generate_art(prompt + _FRAME, "16:9", pro=True, style=images.style_for(genre), image_size="4K")
        b = _text(_fit(art))
        p = out / f"banner_{i}_{name.lower().replace(' ', '_')}.jpg"
        b.save(p, "JPEG", quality=90)
        if p.stat().st_size > 5_800_000:
            b.save(p, "JPEG", quality=80)
        files.append(p)
        print(f"[banner] {p.name} {p.stat().st_size // 1024} KB")
    if args.dry_run:
        return 0
    from pipeline import drive, mailer
    links = drive.upload_mix_package(f"{date.today().isoformat()} – KANALBANNER Entwürfe", files)
    svc = mailer._service()
    to = config.REPORT_EMAIL or svc.users().getProfile(userId="me").execute()["emailAddress"]
    msg = EmailMessage()
    msg["To"], msg["From"] = to, "me"
    msg["Subject"] = "AIX WALKER Kanalbanner: 3 Entwürfe zur Auswahl"
    msg.set_content("3 Banner-Entwürfe (2560×1440, Text im sicheren Bereich):\n\n" +
                    "\n".join(f"{i}. {n}" for i, (n, _, _) in enumerate(SCENES, 1)) +
                    f"\n\nDrive-Ordner: {links.get('_folder')}\n\nAntworte im Chat mit der Nummer deines Favoriten.")
    for p in files:
        prev = p.with_name(p.stem + "_preview.jpg")
        Image.open(p).resize((1280, 720), Image.LANCZOS).save(prev, "JPEG", quality=85)
        mailer._attach_image(msg, prev)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    print(f"[banner] Drive: {links.get('_folder')} · Mail an {to}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
