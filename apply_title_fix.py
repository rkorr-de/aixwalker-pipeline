"""Einmalige Korrektur (Rolf 27.10.2026): Vol. 9 (25.10.) und Vol. 10 (26.10.) bekommen neue, einmalige Songtitel.
YouTube-Kapitel und Drive-MP3-Namen sind schon geändert (Chrome/Drive); dieses Skript zieht Gedächtnis (memory.json) und
metadata.txt im Drive-Ordner nach und prüft die YouTube-Beschreibung. Läuft nur in der Umgebung „AixWalker“. Idempotent.
Aufruf: python apply_title_fix.py [--dry-run]"""
import json, re, sys, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from pipeline import drive, memory, youtube

ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true"); a = ap.parse_args()
T = json.loads((Path(__file__).parent / "titlefix" / "vol9_vol10_titles.json").read_text(encoding="utf-8"))
JOBS = [("2026-10-25", 9, "6CYKtRAj_dE", T["vol9"]), ("2026-10-26", 10, "YlqjDo8VAT0", T["vol10"])]
TS = re.compile(r"^(\s*(?:\d+:)?\d{1,2}:\d{2})\s+(.+)$")

def swap_chapters(text, titles):
    out, on, k = [], False, 0
    for line in text.splitlines():
        if re.match(r"^\s*chapters\s*$", line, re.I): on = True; out.append(line); continue
        m = on and TS.match(line)
        if m and k < len(titles): out.append(f"{m.group(1)} {titles[k]}"); k += 1
        else: out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else ""), k

mem = memory.load(); svc = drive.service(); yt = youtube.service()
for day, vol, vid, titles in JOBS:
    print(f"== Vol. {vol} ({day}, {vid})")
    ent = [e for e in mem.get("tokyo", []) if e.get("date") == day and (e.get("video_id") == vid or not e.get("video_id"))]
    if ent:
        e = ent[-1]; e["vol"] = vol; e["video_id"] = vid; e["track_titles"] = titles; e["titles_fixed"] = "2026-10-27"
        print("  Gedächtnis: Eintrag aktualisiert")
    else:
        print("  Gedächtnis: KEIN Eintrag für dieses Datum gefunden – nicht angelegt")
    fl = svc.files().list(q=f"name contains '{day}' and name contains 'Tokyo Work Lounge' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                          fields="files(id,name)").execute()["files"]
    for f in fl:
        mid = drive.find_file(svc, "metadata.txt", f["id"])
        if not mid: print("  metadata.txt fehlt in", f["name"]); continue
        txt = drive.read_text(svc, mid); new, n = swap_chapters(txt, titles)
        print(f"  metadata.txt: {n} Kapitel ersetzt in {f['name'][:50]}")
        if n == len(titles) and not a.dry_run: drive.write_text(svc, "metadata.txt", new, f["id"], "text/plain")
    d = yt.videos().list(part="snippet", id=vid).execute()["items"][0]["snippet"]
    ch = [m.group(2) for l in d["description"].splitlines() if (m := TS.match(l))]
    print("  YouTube-Kapitel stimmen:", ch == titles, "| Titel:", d["title"])
if not a.dry_run:
    memory.save(mem); print("Gedächtnis gespeichert")
