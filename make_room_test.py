"""Testbild für einen neuen Tokyo-Raum (Cloud mit API-Keys): python make_room_test.py <kennung> <szene-datei> <left|right> <woman|man>"""
import sys
from pathlib import Path
sys.path.insert(0, "concepts")
import run_tokyo as t
from pipeline import costs

slug, scene, side, person = sys.argv[1:5]
out = Path("build") / f"roomtest-{slug}"
(out / "img").mkdir(parents=True, exist_ok=True)
costs.start(out / "costs.json")
art, dx = t.make_new_room(slug, scene, side, person, out)
print("ERGEBNIS", "bestanden" if art is not None else "NICHT bestanden", "desk_x", dx)
raise SystemExit(0 if art is not None else 3)
