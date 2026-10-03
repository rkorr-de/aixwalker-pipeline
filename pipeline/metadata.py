"""Kapitel, YouTube-Beschreibung, Tags, Community-Text, Checkliste."""
from pathlib import Path

from . import config


def fmt_ts(sec: float) -> str:
    s = int(round(sec))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def hours_wording(total_min: int) -> str:
    if total_min < 85:
        return "1 Hour"
    if total_min < 110:
        return "1.5 Hours"
    return f"{total_min / 60:.1f} Hours".replace(".0 ", " ")


def fill_duration(text: str, total_min: int) -> str:
    """Ersetzt die Platzhalter {MIN} und {HOURS} – die echte Dauer ist erst nach dem Rendern bekannt."""
    return text.replace("{MIN}", str(total_min)).replace("{HOURS}", hours_wording(total_min))


def fill_concept(concept: dict, total_min: int) -> dict:
    for k in ("yt_title", "hook", "intro", "use_line", "thumbnail_sub", "title_de", "teaser_de"):
        if isinstance(concept.get(k), str):
            concept[k] = fill_duration(concept[k], total_min)
    for k in ("ab_titles", "short_titles"):
        if isinstance(concept.get(k), list):
            concept[k] = [fill_duration(t, total_min) for t in concept[k]]
    return concept


def chapters(titles: list[str], starts: list[float]) -> str:
    lines = []
    for i, (t, s) in enumerate(zip(titles, starts)):
        lines.append(f"{'00:00' if i == 0 else fmt_ts(s)} {t}")
    return "\n".join(lines)


def description(concept: dict, chapter_text: str, playlist_id: str, total_min: int) -> str:
    c = concept
    return f"""🎧 {c['hook']}

{c['intro']}

⏱️ CHAPTERS
{chapter_text}

{c['use_line']}
🔊 {c['bpm']} BPM · no vocals · no interruptions · {'mastered for headphones and gym speakers' if c.get('playlist') == 'gym' else 'mastered for headphones and speakers'}

🎵 All tracks produced by {config.ARTIST} (AI-assisted, original music)
▶️ Full playlist: https://www.youtube.com/playlist?list={playlist_id}
🔔 New mixes every Tuesday and Friday – subscribe and hit the bell!

👇 {c['cta_question']}

{' '.join(c['hashtags'][:5])}
"""


def community_post(concept: dict, video_url: str) -> str:
    return f"""Neuer Mix ist online: {concept['title_de']} 🎧
{concept['teaser_de']}
Hier anhören: {video_url}"""


def checklist(concept: dict, public: bool = False) -> str:
    state = ("Mix und Shorts sind ÖFFENTLICH – nur noch die Punkte unten, die die API nicht kann" if public else
             "Video ist als PRIVAT hochgeladen – kurz reinhören (Anfang, Mitte, Übergang), dann auf ÖFFENTLICH stellen")
    return f"""UPLOAD-CHECKLISTE
[ ] {state}
[ ] Thumbnail gesetzt (automatisch) – bei Bedarf Variante B/C aus thumbnail/ tauschen
[ ] Playlist: {concept.get('playlist', 'gym')} (automatisch)
[ ] KI-Label gesetzt (automatisch, containsSyntheticMedia)
[ ] Endscreen: letzten 20 s → Playlist + „Abonnieren“ (in Studio → Editor)
[ ] Pinned Comment: „{concept['pinned_comment']}“
[ ] Community-Beitrag posten (Text in metadata.txt)
[ ] {'2 Shorts sind ÖFFENTLICH' if public else '2 Shorts sind PRIVAT hochgeladen – kurz prüfen, dann öffentlich stellen'}
[ ] Drive-Ordner „AIX WALKER Mixe/<Datum – Album>“ enthält MP3s, Cover, Video, Thumbnails, Metadaten, Shorts
[ ] DistroKid-Release anlegen (Angaben im Bericht report.md / E-Mail)
"""


def write_metadata(out: Path, concept: dict, yt_title: str, desc: str, tags: list[str], chapter_text: str,
                   ab_titles: list[str], ab_thumbs: list[str], shorts: list[dict], video_url: str,
                   shorts_produced: str = "(keine)", public: bool = False) -> Path:
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

=== SHORTS (automatisch produziert & {'öffentlich' if public else 'privat'} hochgeladen) ===
{shorts_produced}

=== WEITERE SHORTS-IDEEN ===
""" + "\n".join(f"{i + 1}. {s['start']}–{s['end']}  Overlay: „{s['overlay']}“  ({s['why']})" for i, s in enumerate(shorts)) + f"""

=== COMMUNITY-BEITRAG ===
{community_post(concept, video_url)}

=== PINNED COMMENT ===
{concept.get('pinned_comment', '')}

=== {checklist(concept, public)}
"""
    out.write_text(txt, encoding="utf-8")
    return out
