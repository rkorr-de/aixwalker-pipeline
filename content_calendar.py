#!/usr/bin/env python3
"""Content-Kalender AIX WALKER + Giggle Meadow als HTML – komplett autark (keine Netzwerk-/Drive-Zugriffe).

Der Plan steht in WEEK_AIX / WEEK_KIDS unten (Quelle: ROUTINE_PROMPT.md, KIDS_ROUTINE_PROMPT.md, Stand 14.10.2026).
Ändert Rolf den Plan, nur diese Tabellen anpassen.

  python content_calendar.py                 → vollständige HTML-Seite auf stdout
  python content_calendar.py --fragment      → nur der Block zum Einbetten (Morgenbriefing)
  python content_calendar.py --date 2026-10-19
"""
import argparse
import html
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")
DAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

# (Kurzname, Farbe-Klasse, Uhrzeit) je Wochentag 0=Mo … 6=So. Eintrag mit "even_week" läuft nur in geraden KW.
WEEK_AIX = {
    0: [("Italien-Mix", "it", "11:04")],
    1: [("Winter-Cabin-Mix", "cab", "11:04")],
    2: [("Italien-Mix", "it", "11:04")],
    3: [("Gym-Mix (nur gerade KW)", "gym", "11:04", "even_week")],
    4: [("Cabin-Mix", "cab", "08:45"), ("Italien-Mix", "it", "11:04")],
    5: [("Italien-Wochen-Mix (Zusammenschnitt)", "it", "11:04")],
    6: [("Italien-Mix", "it", "11:04"), ("Cabin-Zusammenschnitt (alle 2 Wo., wenn fällig)", "cab", "09:45")],
}
# Je Mix kommen 2 Shorts automatisch dazu (Zusammenschnitt/Cabin-Compilation: keine bzw. eigene).
SHORTS_AIX_NOTE = "je Mix 2 Shorts (nicht beim Samstags-Zusammenschnitt)"
WEEK_KIDS = {
    6: [("Kids-Short (Giggle Meadow)", "kid", "09:00"), ("Best of the Week 16:9", "kid2", "nach 09:00")],
}
SOCIAL_KIDS = "Instagram 10:00 · TikTok 11:00 (nur sonntags, Kids-Short)"


def monthly(d: date):
    """Zusätzliche Läufe am 1. des Monats."""
    if d.day != 1:
        return [], []
    return ([("Monats-Mix (zuerst)", "mon", "11:04"), ("Cabin-Monats-Zusammenschnitt", "cab", "07:45")],
            ([("Monthly Marathon 16:9", "kid2", "nach 09:00")] if d.weekday() == 6 else []))


def items(table, d: date):
    out = []
    for e in table.get(d.weekday(), []):
        if len(e) == 4 and e[3] == "even_week" and d.isocalendar()[1] % 2:
            out.append((e[0].split(" (")[0] + " – diese KW aus", "off", ""))
        else:
            out.append(e[:3])
    return out


CSS = """
.cc{--ink:#2E2C27;--soft:#6B6A63;--hair:#E4E3DC;--bg:#FCFCFB;--wash:#F9F9F7;--clay:#C6613F;
 font-family:-apple-system,"Segoe UI",sans-serif;color:var(--ink);max-width:860px;margin:0 auto}
.cc h2{font-size:15px;font-weight:600;margin:0 0 4px}
.cc .sub{color:var(--soft);font-size:12px;margin:0 0 14px}
.cc .grid{display:grid;grid-template-columns:70px repeat(7,1fr);gap:0;border-top:1px solid var(--hair)}
.cc .c{border-bottom:1px solid var(--hair);padding:8px 5px;min-height:34px;font-size:11.5px;line-height:1.3}
.cc .h{font-weight:600;text-align:center;color:var(--soft);padding:8px 2px}
.cc .h b{display:block;font-size:15px;color:var(--ink)}
.cc .lane{font-weight:600;font-size:12px;display:flex;align-items:center}
.cc .today{background:#FBEDE7;box-shadow:inset 3px 0 0 var(--clay),inset -3px 0 0 var(--clay)}
.cc .h.today{box-shadow:inset 3px 0 0 var(--clay),inset -3px 0 0 var(--clay),inset 0 3px 0 var(--clay)}
.cc .h.today b{color:var(--clay)}
.cc .p{display:block;margin:0 0 4px;padding:3px 5px;border-radius:4px;border-left:3px solid var(--soft);background:#fff}
.cc .p i{display:block;font-style:normal;color:var(--soft);font-size:10.5px}
.cc .it{border-color:#D9A441}.cc .cab{border-color:#5E8FA8}.cc .gym{border-color:#7A9E6B}
.cc .mon{border-color:#8A5FA8}.cc .kid{border-color:#E0699A}.cc .kid2{border-color:#F0A8C4}
.cc .off{color:#B4B3A8;border-color:#E4E3DC}
.cc .note{color:var(--soft);font-size:11.5px;margin:10px 0 0}
@media(max-width:640px){.cc .grid{grid-template-columns:1fr}.cc .lane{padding-top:14px}.cc .h{text-align:left}
 .cc .empty{display:none}}
"""


def cell(lst, today):
    body = "".join(
        f'<span class="p {html.escape(cls)}">{html.escape(name)}<i>{html.escape(t)}</i></span>' for name, cls, t in lst)
    return f'<div class="c{" today" if today else ""}{"" if lst else " empty"}">{body}</div>'


def build(today: date) -> str:
    monday = today - timedelta(days=today.weekday())
    week = [monday + timedelta(days=i) for i in range(7)]
    kw = today.isocalendar()[1]
    g = ['<div class="grid"><div class="c"></div>']
    for d in week:
        t = d == today
        g.append(f'<div class="c h{" today" if t else ""}">{DAYS_DE[d.weekday()]}<b>{d.day}</b></div>')
    for lane, table, idx in (("AIX WALKER", WEEK_AIX, 0), ("Giggle Meadow", WEEK_KIDS, 1)):
        g.append(f'<div class="c lane">{lane}</div>')
        for d in week:
            lst = items(table, d) + monthly(d)[idx]
            g.append(cell(lst, d == today))
    g.append("</div>")
    notes = (f"AIX WALKER: {SHORTS_AIX_NOTE}. Pausiert: Auto-Mix, Ibiza, Sonntags-Lang-Mix. "
             f"Giggle Meadow: {SOCIAL_KIDS}.")
    return (f'<style>{CSS}</style><section class="cc"><h2>Content-Kalender · KW {kw}</h2>'
            f'<p class="sub">Heute: {DAYS_DE[today.weekday()]} {today.strftime("%d.%m.%Y")} (markiert)</p>'
            f'{"".join(g)}<p class="note">{html.escape(notes)}</p></section>')


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--fragment", action="store_true")
    a = ap.parse_args()
    d = date.fromisoformat(a.date) if a.date else datetime.now(TZ).date()
    frag = build(d)
    print(frag if a.fragment else
          f'<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
          f'<title>Content-Kalender</title></head><body style="margin:0;background:#FCFCFB;padding:24px 16px">{frag}</body></html>')
