"""Neue, nie benutzte Songtitel für die Tokyo-Mixe (Rolf 26.10.2026: kein Songname wird mehrmals benutzt).
Titel entstehen aus ruhigen Wortpaaren/-tripeln (Arbeit, Coding, Tokyo, Jazz, Abend). Bereits benutzte Titel stehen im Gedächtnis
(„tokyo“ Feld track_titles) und in den alten festen Listen; zusätzlich wird gegen die Tracktitel in „tokyo_megamix“ geprüft."""
import random

ADJ = """Amber Quiet Slow Soft Warm Late Low Gentle Velvet Hushed Paper Cedar Silent Midnight Dim Lantern Idle Calm Still Tender Faded
Distant Mellow Pale Sleepy Woven Smoky Linen Copper Hazy Mossy Rainy Misty Cozy Brushed Muted Rounded Drifting Lingering Careful
Patient Wandering Evening Twilight Satin Honeyed Candlelit Frosted Cobalt Indigo Silver Jade Ivory Charcoal Walnut Tatami Shoji Ginkgo
Maple Bamboo Plum Camellia Wisteria Harbor Canal Rooftop Alley Station Temple Garden Window Corner Platform Courtyard""".split()
NOUN = """Hours Circuit Neon Window Tab Compile Steam Commit Glow Bandwidth Syntax Desk Cache Glass Shelf Deploy Standby Cursor Terminal
Loop Refactor Light Merge Train Floor Release Thread Mode Dashboard Lamp Keys Pause Breath Thought Branch Build Stack Pixel Signal
Tea Kettle Steps Lanes Lights Rain Mist Moon Notes Chords Brush Smoke Paper Ink Scroll Bridge River Canal Platform Crossing Garden
Balcony Terrace Doorway Staircase Corridor Skyline Reflections Shadows Echoes Margins Drafts Patches Sessions Intermission Interlude
Hush Drift Stillness Warmth Evening Midnight Dawnless Overtime Standup Sprint Backlog Prompt Console Shell Daemon Kernel Packet Cron
Cooldown Warmup Breakpoint Checkpoint Rollback Hotfix Merge Linter Compiler Sandbox Pipeline Webhook Bytes Syntax""".split()
LEGACY = ["Lantern Hours", "Quiet Circuit", "Slow Neon", "Paper Window", "Midnight Tab", "Soft Compile", "Tea Steam", "Late Commit", "Shoji Glow",
          "Low Bandwidth", "Evening Syntax", "Still Desk", "Warm Cache", "Rain on Glass", "Cedar Shelf", "Gentle Deploy", "Amber Standby", "Idle Cursor",
          "Velvet Terminal", "Nightshift Loop", "Calm Refactor", "Tatami Light", "Quiet Merge", "Last Train Home", "Open Floor", "Slow Release",
          "Warm Thread", "Hush Mode", "Dim Dashboard", "Lamp and Rain"]
FORMS = ("{a} {n}", "{a} {n}", "{a} {n}", "{a} {n}", "{n} and {n2}")


def used_titles(mem: dict) -> set[str]:
    used = {t.lower() for t in LEGACY}
    for e in mem.get("tokyo", []):
        used |= {str(t).lower() for t in (e.get("track_titles") or [])}
    for e in mem.get("tokyo_megamix", []):
        used |= {str(t).lower() for t in (e.get("track_titles") or [])}
    return used


def new_titles(n: int, mem: dict, seed: str = "") -> list[str]:
    """n neue Titel, untereinander und gegen alles Bisherige verschieden."""
    rng = random.Random(f"{seed}|{len(mem.get('tokyo', []))}")
    used = used_titles(mem)
    out: list[str] = []
    guard = 0
    while len(out) < n:
        guard += 1
        if guard > 50000:
            raise RuntimeError("Keine neuen Songtitel mehr verfügbar – Wortlisten in concepts/song_names.py erweitern")
        t = rng.choice(FORMS).format(a=rng.choice(ADJ), n=rng.choice(NOUN), n2=rng.choice(NOUN)).strip()
        words = t.split()
        if len(set(w.lower() for w in words)) != len(words) or len(t) > 32:
            continue
        if t.lower() in used:
            continue
        used.add(t.lower())
        out.append(t)
    return out
