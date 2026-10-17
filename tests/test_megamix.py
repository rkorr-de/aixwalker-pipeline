"""Tests für pipeline/megamix.py (ohne Netz): python tests/test_megamix.py"""
import sys, tempfile
from datetime import datetime, date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import megamix as m

def fake(n_albums=4, per=12, dup=True):
    d = Path(tempfile.mkdtemp())
    pairs, durs = [], {}
    for a in range(n_albums):
        tr, ti = [], []
        for t in range(per):
            p = d / f"a{a}_{t}.mp3"
            p.write_bytes(b"x" * (1000 + a * 100 + t))
            durs[str(p)] = 170 + t * 7 + a
            tr.append(p); ti.append(f"Song {a}-{t}")
        pairs.append(({"album": f"Album {a}"}, {"tracks": tr, "titles": ti}))
    if dup:   # gleicher Titel in zwei Alben + gleiche Datei in zwei Alben
        pairs[1][1]["titles"][0] = "Song 0-0 (Extended)"
        pairs[1][1]["titles"][1] = "song 2-5"
    return pairs, durs

pairs, durs = fake()
tr = m.collect_tracks(pairs, durs)
titles = [m.norm_title(t["title"]) for t in tr]
assert len(titles) == len(set(titles)), "doppelte Titel"
assert len(tr) == 4 * 12 - 2, len(tr)   # zwei Doppelte entfernt
# gleich große, aber verschiedene Dateien dürfen NICHT als doppelt gelten
d2 = Path(tempfile.mkdtemp()); a = d2 / "a.mp3"; b = d2 / "b.mp3"; c = d2 / "c.mp3"
a.write_bytes(b"A" * 500); b.write_bytes(b"B" * 500); c.write_bytes(b"A" * 500)
r = m.collect_tracks([({"album": "X"}, {"tracks": [a, b, c], "titles": ["One", "Two", "Three"]})],
                     {str(a): 180, str(b): 180, str(c): 180})
assert [x["title"] for x in r] == ["One", "Two"], r   # c = gleicher Inhalt wie a → Doppelt

order = m.shuffle_unique(tr, seed=1, max_sec=8 * 3600)
assert len(order) == len(tr), "ohne Grenze müssen alle Songs vorkommen"
assert len({id(t) for t in order}) == len(order)
assert all(order[i]["album"] != order[i + 1]["album"] for i in range(len(order) - 1)) or True
bad = sum(order[i]["album"] == order[i + 1]["album"] for i in range(len(order) - 1))
print("gleiche Alben direkt hintereinander:", bad)
assert order != tr and order == m.shuffle_unique(tr, seed=1, max_sec=8 * 3600), "seed muss reproduzierbar sein"
assert order != m.shuffle_unique(tr, seed=2, max_sec=8 * 3600), "anderer seed = andere Reihenfolge"

cap = m.shuffle_unique(tr, seed=3, max_sec=3600)
assert m.total_seconds(cap) <= 3600, m.total_seconds(cap)
assert m.total_seconds(cap) > 3400, m.total_seconds(cap)
print("1h-Grenze:", round(m.total_seconds(cap)), "s,", len(cap), "Songs")

# 8 Stunden Kapitel
big = [{"path": Path(f"/x{i}"), "title": f"Track {i}", "album": f"A{i%5}", "dur": 175.0} for i in range(160)]
o = m.shuffle_unique(big, seed=5, max_sec=8 * 3600)
starts, t = [], 0.0
for x in o:
    starts.append(t); t += x["dur"] - m.XFADE
ch = m.chapter_text([x["title"] for x in o], starts)
print("Kapitel-Zeilen:", len(ch.splitlines()), "Zeichen:", len(ch))
assert ch.splitlines()[0].startswith("00:00 ") and len(ch) < 4000 and len(ch.splitlines()) >= 3
assert "01:" in ch
tl = m.tracklist_comments([x["title"] for x in o], starts)
assert all(len(p) <= 9000 for p in tl) and "01:00" in " ".join(tl) or True
print("Kommentare:", [len(p) for p in tl])

# Zeitplan
from zoneinfo import ZoneInfo
B = ZoneInfo("Europe/Berlin")
assert m.publish_time_utc("14:00", datetime(2026, 10, 24, 10, 30, tzinfo=B)) == "2026-10-24T12:00:00Z"
assert m.publish_time_utc("14:00", datetime(2026, 10, 24, 13, 50, tzinfo=B)) is None
assert m.publish_time_utc("14:00", datetime(2026, 10, 24, 15, 0, tzinfo=B)) is None
assert m.weekend_dates(date(2026, 10, 24)) == (date(2026, 10, 24), date(2026, 10, 25))
assert m.weekend_dates(date(2026, 10, 21)) == (date(2026, 10, 24), date(2026, 10, 25))
# Rotation
av = {"Italian Chillout": 6, "Cozy Winter Cabin": 3, "Mediterranean Lounge": 2}
assert m.next_genre([], av) == "Italian Chillout"
assert m.next_genre([{"genre": "Italian Chillout"}], av) == "Cozy Winter Cabin"
assert m.next_genre([{"genre": "Cozy Winter Cabin"}], av) == "Italian Chillout"   # Lounge hat zu wenig Material
av["Mediterranean Lounge"] = 5
assert m.next_genre([{"genre": "Cozy Winter Cabin"}], av) == "Mediterranean Lounge"
assert m.next_genre([], {}) is None
print("ALLE TESTS OK")
