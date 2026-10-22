"""Zwei Testbilder: Person arbeitet nachts am Schreibtisch (Mann / Frau), Rolf 22.10.2026. Kosten ca. 0,5 $. Drive + Mail wie test_tokyo_images.py."""
import base64, json, sys
from email.message import EmailMessage
from pathlib import Path
HERE = Path(__file__).parent
sys.path[:0] = [str(HERE), str(HERE / "concepts")]
import genre_test_tokyo_rooms_v3 as r  # noqa: E402
import run_tokyo as t  # noqa: E402
import tokyo_variation as tv  # noqa: E402
from pipeline import config, drive, images, mailer  # noqa: E402

COMMON = dict(desk_pos="front", chair="black", chair_pose="tucked", at_desk=True, rack=True, robot=True, cyan=True, purifier="dyson", console="bonsai", ink=False)
CASES = [
    ("man", dict(COMMON, gender="man", pc="north", kb="keychron", audio="kef", deco="designer_toy", sofa_material="fabric", sofa_color="charcoal linen", art_key="alley_photo", accent_wall="shikkui"),
     "A calm loft in Nakameguro, Tokyo: a tall window toward a canal with lantern-lit cherry branches at night, walnut slat screens, soft amber evening mood."),
    ("woman", dict(COMMON, gender="woman", pc="sff", kb="hhkb", audio="genelec", deco="mecha_print", sofa_material="leather", sofa_color="black leather", art_key="enso", ink=True, accent_wall="ribbed"),
     "A high loft in Shinjuku, Tokyo: floor-to-ceiling windows with the glittering warm-lit skyline at night, a hushed amber interior."),
]


def main() -> int:
    out = HERE / "build" / "test_persons"
    out.mkdir(parents=True, exist_ok=True)
    files, res_all = [], []
    for i, (who, var, scene) in enumerate(CASES, 1):
        side = "left" if i == 1 else "right"
        parts = tv.apply(var, side, r)
        prompt = r.INTRO + parts["desk"] + parts["cozy"] + parts["person"] + t.FIGURINE + parts["art"] + scene
        (out / f"prompt_{who}.txt").write_text(prompt + "\n\nSTYLE:" + parts["style"], encoding="utf-8")
        try:
            img = images.generate_art(prompt, "16:9", pro=True, style=parts["style"], image_size="4K").convert("RGB")
            res = t.check_room_image(img, var)
            f = out / f"test_{who}.jpg"
            img.resize((2560, 1440)).save(f, "JPEG", quality=90)
            files.append(f)
        except Exception as e:  # noqa: BLE001
            res = {"error": str(e)[:200]}
        res_all.append((who, res))
        print(who, res, flush=True)
    links = drive.upload_mix_package("TEST Tokyo Person am Schreibtisch 22.10.2026", [out / f"prompt_{w}.txt" for w, _ in CASES],
                                     {"bilder": files})
    body = "2 Testbilder: Person arbeitet nachts am Schreibtisch.\nDrive: " + links.get("_folder", "?") + "\n" + "\n".join(f"{w}: Prüfung {x}" for w, x in res_all)
    svc = mailer._service()
    msg = EmailMessage()
    msg["To"] = config.REPORT_EMAIL or svc.users().getProfile(userId="me").execute()["emailAddress"]
    msg["From"] = "me"
    msg["Subject"] = "AIX WALKER Tokyo: 2 Testbilder Person am Schreibtisch"
    msg.set_content(body)
    for f in files:
        mailer._attach_image(msg, f, 1600)
    svc.users().messages().send(userId="me", body={"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}).execute()
    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
