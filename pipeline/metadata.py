"""Kapitel, YouTube-Beschreibung, Tags, Community-Text, Checkliste."""
import re
from pathlib import Path

from . import config


def fmt_ts(sec: float) -> str:
    s = int(round(sec))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def chapters(titles: list[str], starts: list[float]) -> str:
    lines = []
    for i, (t, s) in enumerate(zip(titles, starts)):
        lines.append(f"{'00:00' if i == 0 else fmt_ts(s)} {t}")
    return "\n".join(lines)


_DUR = re.compile(r"\b\d+(?:[.,]\d+)?(\s*)(Min(?:utes|uten)?|MIN(?:UTES|UTEN)?|min(?:utes|uten)?)\b")
_DUR_FIELDS = ("yt_title", "hook", "intro", "title_de", "teaser_de", "pinned_comment", "thumbnail_sub", "thumbnail_headline")


def sync_concept(concept: dict, total_sec: float, titles: list[str], starts: list[float]) -> dict:
    """Gleicht alle Zeitangaben im Konzept mit der echten Mix-Länge und den echten Kapitelzeiten ab.

    - Minutenangaben („45 Min“, „45 minutes“, „45 Minuten“) in Titeln/Texten/A-B-Varianten → echte Minuten
    - Shorts mit {"track", "offset", "length"} → Start/Ende aus den realen Track-Startzeiten
    - Shorts mit festen Zeiten müssen innerhalb der Laufzeit liegen, sonst Abbruch
    """
    c = dict(concept)
    minutes = int(round(total_sec / 60))
    sub = lambda txt: _DUR.sub(lambda m: f"{minutes}{m.group(1)}{m.group(2)}", txt)
    for k in _DUR_FIELDS:
        if isinstance(c.get(k), str):
            c[k] = sub(c[k])
    for k in ("ab_titles", "ab_thumbs"):
        if k in c:
            c[k] = [sub(x) for x in c[k]]
    shorts = []
    for sh in c.get("shorts", []):
        sh = dict(sh)
        if "track" in sh:
            start = starts[titles.index(sh["track"])] + float(sh.get("offset", 0))
            sh["start"], sh["end"] = fmt_ts(start), fmt_ts(start + float(sh.get("length", 40)))
        else:
            def sec(ts):
                p = [int(x) for x in ts.split(":")]
                return sum(v * 60 ** i for i, v in enumerate(reversed(p)))
            if sec(sh["end"]) > total_sec:
                raise ValueError(f"Short {sh['start']}–{sh['end']} liegt außerhalb der Laufzeit {fmt_ts(total_sec)}")
        shorts.append(sh)
    if shorts:
        c["shorts"] = shorts
    return c


def description(concept: dict, chapter_text: str, playlist_id: str, total_min: int) -> str:
    c = concept
    return f"""🎧 {c['hook']}

{c['intro']}

⏱️ CHAPTERS
{chapter_text}

{c['use_line']}
🔊 {c['bpm']} BPM · no vocals · no interruptions · mastered for headphones and gym speakers

🎵 All tracks produced by {config.ARTIST} (AI-assisted, original music)
▶️ Full playlist: https://www.youtube.com/playlist?list={playlist_id}
🔔 New mix every Friday – subscribe and hit the bell!

👇 {c['cta_question']}

{' '.join(c['hashtags'][:5])}
"""


def community_post(concept: dict, video_url: str) -> str:
    return f"""Neuer Mix ist online: {concept['title_de']} 🎧
{concept['teaser_de']}
Hier anhören: {video_url}"""


def checklist(concept: dict) -> str:
    return f"""UPLOAD-CHECKLISTE
[ ] Video ist als PRIVAT hochgeladen – kurz reinhören (Anfang, Mitte, Übergang), dann auf ÖFFENTLICH stellen
[ ] Beste Zeit zum Veröffentlichen: Freitag 17–19 Uhr (Europa Feierabend, USA Mittag)
[ ] Thumbnail gesetzt (automatisch) – bei Bedarf Variante B/C aus thumbnail/ tauschen
[ ] Playlist: {concept.get('playlist', 'gym')} (automatisch)
[ ] KI-Label gesetzt (automatisch, containsSyntheticMedia)
[ ] Endscreen: letzten 20 s → Playlist + „Abonnieren“ (in Studio → Editor)
[ ] Pinned Comment: „{concept['pinned_comment']}“
[ ] Community-Beitrag posten (Text in metadata.txt)
[ ] 2 Shorts schneiden (Zeitmarken in metadata.txt), Link zum Mix in der Beschreibung
"""


def write_metadata(out: Path, concept: dict, yt_title: str, desc: str, tags: list[str], chapter_text: str,
                   ab_titles: list[str], ab_thumbs: list[str], shorts: list[dict], video_url: str) -> Path:
    txt = f"""=== YOUTUBE TITEL ===
{yt_title}

=== BESCHREIBUNG ===
{desc}
=== TAGS ===
{', '.join(tags)}

=== KAPITEL ===
{chapter_text}

=== A/B TITEL-VARIANTEN ===
""" + "\n".join(f"{i + 1}. {t}" for i, t in enumerate(ab_titles)) + f"""

=== A/B THUMBNAIL-TEXT ===
""" + "\n".join(f"{i + 1}. {t}" for i, t in enumerate(ab_thumbs)) + f"""

=== SHORTS-VORSCHLÄGE ===
""" + "\n".join(f"{i + 1}. {s['start']}–{s['end']}  Overlay: „{s['overlay']}“  ({s['why']})" for i, s in enumerate(shorts)) + f"""

=== COMMUNITY-BEITRAG ===
{community_post(concept, video_url)}

=== {checklist(concept)}
"""
    out.write_text(txt, encoding="utf-8")
    return out
