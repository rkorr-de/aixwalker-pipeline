"""Vier Testbilder für die neuen Tokyo-Raum-Variationen (Rolf 22.10.2026). Kosten ca. 0,24 $ je Bild (4K). Kein Mix, nichts veröffentlicht.
Aufruf: python test_tokyo_images.py   → Bilder in Drive „TEST Tokyo Raum-Variationen“ + eine Mail mit Vorschau und Prüfergebnis."""
import base64
import json
import sys
from email.message import EmailMessage
from pathlib import Path

HERE = Path(__file__).parent
sys.path[:0] = [str(HERE), str(HERE / "concepts")]
import genre_test_tokyo_rooms_v3 as r  # noqa: E402
import run_tokyo as t  # noqa: E402
import tokyo_variation as tv  # noqa: E402
from pipeline import config, drive, images, mailer  # noqa: E402

SCENES = [
    "A calm loft in Daikanyama, Tokyo: a tall window toward a small lantern-lit garden with maple trees at night, walnut slat screens, soft amber evening mood.",
    "A quiet loft in Kagurazaka, Tokyo: a long window over a stone lane with paper lanterns, rain on the glass, deep amber evening glow.",
    "A high loft in Shibuya, Tokyo: floor-to-ceiling windows with the glittering warm-lit skyline at night, a calm amber interior.",
    "A loft in Yanaka, Tokyo: a wide window toward old wooden houses and a temple roof lit by warm lamps at night, hushed amber mood.",
]
# vier bewusst verschiedene Kombinationen (Schreibtisch vorn/hinten, Stuhl, Tastatur, Audio, Deko, Sofa, Tuschebild)
BASE = [
    dict(desk_pos="front", chair="cognac", chair_pose="away", kb="hhkb", audio="kef", deco="designer_toy", sofa_material="leather", sofa_color="black leather",
         art_key="enso", ink=True, accent_wall="shikkui", console="bonsai", purifier="dyson", rack=True, robot=True, cyan=True),
    dict(desk_pos="back", chair="black", chair_pose="window", kb="keychron", audio="genelec", deco="mecha_print", sofa_material="fabric", sofa_color="warm sand wool",
         art_key="woodblock", ink=False, accent_wall="ribbed", console="slate", purifier="balmuda", rack=True, robot=False, cyan=True),
    dict(desk_pos="back", chair="cognac", chair_pose="toward_camera", kb="keychron", audio="kef", deco="vinyl_figure", sofa_material="leather", sofa_color="cognac-brown leather",
         art_key="mist_peak", ink=True, accent_wall="slats", console="bonsai", purifier="dyson", rack=False, robot=True, cyan=False),
    dict(desk_pos="front", chair="black", chair_pose="tucked", kb="hhkb", audio="genelec", deco="designer_toy", sofa_material="fabric", sofa_color="charcoal linen",
         art_key="alley_photo", ink=False, accent_wall="shikkui", console="slate", purifier="balmuda", rack=True, robot=True, cyan=True),
]


def main() -> int:
    out = HERE / "build" / "test_variation"
    out.mkdir(parents=True, exist_ok=True)
    results, files = [], []
    for i, (var, scene) in enumerate(zip(BASE, SCENES), 1):
        side = "left" if i % 2 else "right"
        parts = tv.apply(var, side, r)
        prompt = r.INTRO + parts["desk"] + parts["cozy"] + r.PERSON["woman" if i % 2 else "man"] + t.FIGURINE + parts["art"] + scene
        res = None
        try:
            img = images.generate_art(prompt, "16:9", pro=True, style=parts["style"], image_size="4K").convert("RGB")
            res = t.check_room_image(img, var)
            f = out / f"test_{i}.jpg"
            img.resize((2560, 1440)).save(f, "JPEG", quality=90)
            files.append(f)
        except Exception as e:  # noqa: BLE001
            res = {"error": str(e)[:200]}
        results.append({"nr": i, "variation": var, "check": res})
        print(i, res, flush=True)
    (out / "ergebnis.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    links = drive.upload_mix_package("TEST Tokyo Raum-Variationen 22.10.2026", [out / "ergebnis.json"], {"bilder": files})
    body = "4 Testbilder zu den neuen Tokyo-Raum-Variationen.\nDrive-Ordner: " + links.get("_folder", "?") + "\n\n"
    for x in results:
        v = x["variation"]
        body += (f"Bild {x['nr']}: Schreibtisch {v['desk_pos']}, Stuhl {'Eames' if v['chair']=='cognac' else 'Aeron'}, Tastatur {v['kb']}, Audio {v['audio']}, "
                 f"Deko {v['deco']}, Sofa {v['sofa_color']}, Wand {v['art_key']} – Prüfung: {x['check']}\n")
    svc = mailer._service()
    msg = EmailMessage()
    msg["To"] = config.REPORT_EMAIL or svc.users().getProfile(userId="me").execute()["emailAddress"]
    msg["From"] = "me"
    msg["Subject"] = "AIX WALKER Tokyo: 4 Testbilder Raum-Variationen"
    msg.set_content(body)
    for f in files:
        mailer._attach_image(msg, f, 1600)
    svc.users().messages().send(userId="me", body={"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}).execute()
    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
