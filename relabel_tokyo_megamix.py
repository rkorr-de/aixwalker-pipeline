"""Einmalig (Rolf 24.10.2026): Songtitel im bereits veröffentlichten Tokyo-Mega-Mix mit dem Raum beschriften
(„Soft Compile · Kichijoji“), damit gleiche Titel aus verschiedenen Mixen unterscheidbar sind. Audio/Video bleiben unverändert.
Ablauf: Reihenfolge des Laufs nachrechnen (gleiche Quellen, gleicher Seed), gegen die Kapitel in der Beschreibung prüfen (Abbruch bei
Abweichung), dann Beschreibung und Tracklisten-Kommentar des Videos umschreiben. Zeiten bleiben exakt wie veröffentlicht.
  python relabel_tokyo_megamix.py --video-id _9lCa5dsc_Y --date 2026-10-24 [--dry-run]"""
import argparse
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pipeline import config, megamix  # noqa: E402
import run_megamix as rm  # noqa: E402
import run_tokyo_megamix as tm  # noqa: E402

LINE = re.compile(r"^((?:\d{1,2}:)?\d{2}:\d{2}) (.+)$")


def label(album: str, title: str) -> str:
    m = re.search(r"Tokyo Work Lounge\s*[–-]\s*([a-z]+)", album or "")
    return f"{title} · {m.group(1).capitalize()}" if m else title


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    for v in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN", "DRIVE_REFRESH_TOKEN"):
        config.require(v)
    from pipeline import drive, youtube
    d = date.fromisoformat(a.date)
    svc = drive.service()
    sources = tm.tokyo_sources(svc)
    print("Quellen:", [f["name"] for f in sources])
    pairs = rm.fetch_all(svc, sources, HERE / "build" / "relabel_src")
    order = rm.build_order(pairs, seed=d.toordinal() * 31 + 7, max_hours=megamix.MAX_HOURS, by_title=False)
    titles = [t["title"] for t in order]
    new = [label(t["album"], t["title"]) for t in order]

    desc = youtube.get_description(a.video_id)
    lines = desc.split("\n")
    chap_idx = [i for i, l in enumerate(lines) if LINE.match(l)]
    k = max(1, -(-len(titles) // 60))
    if len(chap_idx) != len(range(0, len(titles), k)):
        print(f"ABBRUCH: {len(chap_idx)} Kapitelzeilen, erwartet {len(range(0, len(titles), k))}")
        return 2
    bad = [(n, LINE.match(lines[i]).group(2), titles[n * k]) for n, i in enumerate(chap_idx) if LINE.match(lines[i]).group(2) != titles[n * k]]
    if bad:
        print("ABBRUCH: Reihenfolge weicht von der Veröffentlichung ab:", bad[:5])
        return 3
    for n, i in enumerate(chap_idx):
        m = LINE.match(lines[i])
        lines[i] = f"{m.group(1)} {new[n * k]}"
    new_desc = "\n".join(lines)

    yt = youtube.service()
    threads = yt.commentThreads().list(part="snippet", videoId=a.video_id, maxResults=50, order="time", textFormat="plainText").execute()
    updates, pos = [], 0
    for th in sorted(threads.get("items", []), key=lambda t: t["snippet"]["topLevelComment"]["snippet"]["publishedAt"]):
        c = th["snippet"]["topLevelComment"]
        text = c["snippet"]["textOriginal"]
        if "Full tracklist" not in text and "Tracklist (continued)" not in text:
            continue
        out = []
        for l in text.split("\n"):
            m = LINE.match(l)
            if m:
                if pos >= len(titles) or m.group(2) != titles[pos]:
                    print(f"ABBRUCH Kommentar: Zeile {pos}: „{m.group(2)}“ ≠ „{titles[pos] if pos < len(titles) else '-'}“")
                    return 4
                l = f"{m.group(1)} {new[pos]}"
                pos += 1
            out.append(l)
        updates.append((c["id"], "\n".join(out)))
    print(f"Beschreibung: {len(chap_idx)} Kapitel · Kommentare: {len(updates)} ({pos} Songs von {len(titles)})")
    if pos != len(titles):
        print("ABBRUCH: Kommentar enthält nicht alle Songs")
        return 5
    print("Beispiel:\n" + "\n".join(new_desc.split("\n")[chap_idx[0]:chap_idx[0] + 5]))
    if a.dry_run:
        return 0
    youtube.set_description(a.video_id, new_desc)
    for cid, text in updates:
        yt.comments().update(part="snippet", body={"id": cid, "snippet": {"textOriginal": text}}).execute()
    print("Beschreibung und Kommentar aktualisiert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
