"""Gedächtnis des Planers: memory.json in Google Drive („AIX WALKER Mixe/_memory“), lokaler Spiegel in build/.

Enthält alle produzierten Mixe (Genre, BPM, Album, Titel, Track-Titel, Bildmotiv, Video-/Short-IDs, Kosten),
Analytics-Momentaufnahmen und Lernsätze. Der Planer liest es, um Genre, Stimmung, Motiv und Titel so zu wählen,
dass sich nichts wiederholt und die Kanalthemen trotzdem gleich bleiben.
"""
import json
import time
from datetime import date
from pathlib import Path

from . import config

LOCAL = config.ROOT / "build" / "memory.json"
NAME = "memory.json"

# Startwissen: alles, was der Kanal vor dem Planer schon veröffentlicht hat (keine Wiederholung dieser Konzepte)
SEED = {
    "version": 1,
    "mixes": [
        {"date": "2026-09-04", "album": "THE PUMP LIST", "genre": "Slow Gym Beats", "bpm": 80,
         "mood": "dark, heavy lifting", "yt_title": "THE PUMP LIST 🥵 1 Hour Slow Gym Beats (80 BPM) – Dark Workout Music for Heavy Lifting",
         "video_id": "byjXQyqhSlM", "duration_min": 60, "visual": {"motif_family": "athletic man", "motif": "lifter at the rack"},
         "purpose": "heavy lifting", "track_titles": []},
        {"date": "2026-09-11", "album": "NIGHT RIDE Vol. 1", "genre": "Night Drive Deep Bass", "bpm": 90,
         "mood": "dark ambient, deep bass", "yt_title": "NIGHT RIDE Vol. 1 🌌 35 Min Dark Ambient & Deep Bass – Late Night Driving Music",
         "video_id": "g2SaFb4PoGk", "duration_min": 35, "visual": {"motif_family": "car/road", "motif": "night highway"},
         "purpose": "late night driving", "track_titles": []},
        {"date": "2026-09-18", "album": "DARK SPA AMBIENT", "genre": "Dark Ambient Spa", "bpm": 55,
         "mood": "deep relaxing, no melody", "yt_title": "DARK SPA AMBIENT 🛁 1.5 Hours Deep Relaxing Music – Sleep, Massage & Wellness (No Melody)",
         "video_id": "PumcKWI9F5s", "duration_min": 90, "visual": {"motif_family": "spa scene", "motif": "candles and stones"},
         "purpose": "massage & wellness", "track_titles": []},
        {"date": "2026-10-02", "slug": "deep-sleep-drift", "album": "Deep Sleep Drift", "genre": "Chillout Sleep", "bpm": 50,
         "mood": "warm, soft, weightless, deeply calming",
         "yt_title": "Sleep Music · 1 Hour · Fall Asleep Fast (50 BPM) – Deep Sleep Drift",
         "video_id": "_qa_DONWkqo", "short_ids": ["b7kQlFwxv0c", "7itmUSIfbjQ"], "duration_min": 61, "cost_usd": 4.33,
         "visual": {"motif_family": "empty bed", "motif": "bed by starry window, floor mist", "light": "moonlight + teal glow"},
         "purpose": "fall asleep fast",
         "track_titles": ["Amber Hush", "Barely Awake", "Cloud Ledger", "Dim Lantern", "Evening Tide", "Faded Horizon",
                          "Gentle Descent", "Hollow Moon", "Idle Waters", "Jasmine Dusk", "Kindled Dark", "Low Tide Lullaby",
                          "Midnight Linen", "Night Vessel", "Quiet Harbor", "Soft Static", "Velvet Hours", "Yawning Stars",
                          "Zen Pillow", "Zephyr Calm", "Zero Gravity Rest", "Zodiac Hush"]},
    ],
    "reserved_names": ["Iron Focus", "Hot Stone Ritual"],   # Album-Namen aus Beispiel-/Altkonzepten: nicht verwenden
    "analytics": [],
    "learnings": [
        "Lyria liefert ca. 3 Minuten je Track: 20 Tracks + 8 Reserve planen, nie Reprisen oder inhaltlich gleiche Tracks.",
        "Spa/Sleep-Mixe bringen die meisten Aufrufe und Wiedergabeminuten; Gym-Mixe halten die Zuschauer anteilig am längsten.",
        "35-Minuten-Mixe laufen schlecht – jeder Mix mindestens 60 Minuten, Dauer im Titel erst nach dem Rendern eintragen.",
    ],
}


def _svc():
    from . import drive
    return drive.service()


def load(use_drive: bool = True) -> dict:
    """Drive zuerst, sonst lokaler Spiegel, sonst Startwissen."""
    if use_drive:
        try:
            from . import drive
            svc = _svc()
            fid = drive.find_file(svc, NAME, drive.memory_folder(svc))
            if fid:
                mem = json.loads(drive.read_text(svc, fid))
                _save_local(mem)
                return mem
            print("[memory] noch kein memory.json in Drive – Startwissen wird verwendet")
        except Exception as e:  # noqa: BLE001
            print(f"[memory] Drive nicht lesbar ({e}) – lokaler Spiegel/Startwissen")
    if LOCAL.exists():
        try:
            return json.loads(LOCAL.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return json.loads(json.dumps(SEED))


def _save_local(mem: dict) -> None:
    LOCAL.parent.mkdir(parents=True, exist_ok=True)
    LOCAL.write_text(json.dumps(mem, indent=2, ensure_ascii=False), encoding="utf-8")


def save(mem: dict, use_drive: bool = True, extra_files: dict[str, str] | None = None) -> str | None:
    """Schreibt memory.json lokal und in Drive; `extra_files` {name: text} landen daneben (Konzept, Bericht)."""
    mem["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save_local(mem)
    if not use_drive:
        return None
    from . import drive
    svc = _svc()
    folder = drive.memory_folder(svc)
    fid = drive.write_text(svc, NAME, json.dumps(mem, indent=2, ensure_ascii=False), folder)
    for name, text in (extra_files or {}).items():
        mime = "application/json" if name.endswith(".json") else "text/plain"
        drive.write_text(svc, name, text, folder, mime)
    return f"https://drive.google.com/drive/folders/{folder}"


def record_mix(mem: dict, concept: dict, result: dict) -> dict:
    entry = {
        "date": date.today().isoformat(), "slug": concept["slug"], "album": concept["album"],
        "genre": concept["genre"], "bpm": int(concept["bpm"]), "mood": concept.get("mood", ""),
        "purpose": concept.get("purpose", ""), "sound_design": concept.get("sound_design", ""),
        "yt_title": result.get("title"), "video_id": result.get("video_id"),
        "short_ids": [s.get("video_id") for s in result.get("shorts", []) if s.get("video_id")],
        "duration_min": result.get("duration_min"), "tracks": result.get("tracks"),
        "track_titles": [ln.split(" ", 1)[1] for ln in (result.get("chapters") or "").splitlines() if " " in ln],
        "visual": concept.get("visual", {}), "cost_usd": result.get("cost_usd"),
        "drive": (result.get("drive") or {}).get("_folder"),
    }
    mem.setdefault("mixes", []).append(entry)
    return entry


def record_analytics(mem: dict, watch_hours: float | None, rows: list[dict]) -> None:
    mem.setdefault("analytics", []).append({"date": date.today().isoformat(), "watch_hours_365": watch_hours,
                                            "videos": rows[:20]})
    mem["analytics"] = mem["analytics"][-30:]


def add_learning(mem: dict, text: str) -> None:
    if text and text not in mem.setdefault("learnings", []):
        mem["learnings"].append(text)


def used_track_titles(mem: dict) -> set[str]:
    return {t.strip().lower() for m in mem.get("mixes", []) for t in m.get("track_titles", [])}


def used_albums(mem: dict) -> set[str]:
    names = {m["album"].strip().lower() for m in mem.get("mixes", [])}
    names |= {n.strip().lower() for n in mem.get("reserved_names", [])}
    return names


def summary_for_prompt(mem: dict, last_n: int = 12) -> str:
    """Kompakte Vorgeschichte für den Konzept-Prompt."""
    lines = []
    for m in mem.get("mixes", [])[-last_n:]:
        v = m.get("visual") or {}
        lines.append(f"- {m.get('date')}: „{m['album']}“ – {m['genre']}, {m['bpm']} BPM, {m.get('mood', '')}; "
                     f"purpose: {m.get('purpose', '-')}; visual: {v.get('motif_family', '-')} / {v.get('motif', '-')}"
                     f"{' / ' + v['light'] if v.get('light') else ''}; title: {m.get('yt_title', '-')}")
    return "\n".join(lines) or "- (noch keine Mixe)"


if __name__ == "__main__":
    mem = load()
    print(f"{len(mem.get('mixes', []))} Mixe im Gedächtnis, Stand {mem.get('updated', '-')}")
    print(summary_for_prompt(mem))
    print("Lernsätze:", *mem.get("learnings", []), sep="\n  ")
