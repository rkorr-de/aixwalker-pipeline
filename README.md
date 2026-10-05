# AIX WALKER Pipeline

Vollautomatische Produktion von zwei Musik-Mixen pro Woche (Dienstag + Freitag) für den YouTube-Kanal **AIX WALKER**
(Gedächtnis → Planer → Konzept (Gemini) → Lyria 3.5 → QC → Mastering → Cover → MP3/MP4 → Thumbnail → 2 Shorts →
Metadaten → Upload öffentlich → Google Drive → Gedächtnis → Bericht per E-Mail).

Die Anweisungen der geplanten Routine stehen in `ROUTINE_PROMPT.md` (die Routine liest diese Datei).

## Vollautomatischer Lauf

```bash
python run_auto.py              # plant, produziert, veröffentlicht, archiviert, berichtet – ohne Rückfragen
python run_auto.py --dry-run    # Funktionstest ohne Kosten, ohne Upload
python run_auto.py --private    # Uploads privat (z. B. zum Prüfen)
python run_auto.py --genre "Dark Ambient Spa"   # Genre erzwingen
python run_auto.py --concept concepts/x.json    # fertiges Konzept statt Planer
```

- **Planer** (`pipeline/planner.py`): wählt Genre (nie zweimal hintereinander dasselbe; lange nicht bediente Themen
  und laut Analytics starke Themen bevorzugt), BPM, Zweck, Stimmung, Bildmotiv-Familie und Lichtstimmung – jeweils
  anders als bei den letzten Mixen – und lässt daraus mit `prompts/concept_prompt.md` das komplette Konzept
  erzeugen (20 Tracks + 8 Reserve, alphabetisch, Titel nie wiederverwendet, Prompts, Metadaten, Shorts-Hooks).
  Das Konzept wird geprüft und bei Mängeln neu angefordert.
- **Gedächtnis** (`pipeline/memory.py`): `AIX WALKER Mixe/_memory/memory.json` in Drive (lokaler Spiegel
  `build/memory.json`) mit allen Mixen, Track-Titeln, Motiven, Analytics-Momentaufnahmen und Lernsätzen; daneben
  je Mix Konzept und Bericht. `python -m pipeline.memory` zeigt den Stand.
- **Bericht** (`pipeline/mailer.py`): E-Mail über die Gmail-API (Scope gmail.send, eigenes Token
  `GMAIL_REFRESH_TOKEN`; Empfänger `REPORT_EMAIL` oder das Gmail-Konto der Freigabe) mit Links, Titel,
  Beschreibung, Kapiteln, Kosten, Community-Text, angepinntem Kommentar und allen DistroKid-Formularangaben
  (`DISTROKID_SONGWRITER` = Klarname für die Songwriter-Felder); Anhänge Thumbnail + Cover. Ohne Token nur
  `build/<slug>/report.md`.
- **Kostenbremse**: `BUDGET_MAX_USD` (Standard 9 $) – darüber startet der automatische Lauf nicht.
- Platzhalter `{MIN}`/`{HOURS}` in Titel/Hook werden nach dem Rendern durch die echte Dauer ersetzt.

## Voraussetzungen (Umgebungsvariablen)

| Variable | Zweck |
|---|---|
| `GOOGLE_API_KEY` | Gemini-API (Lyria 3.5 für Musik, Nano Banana für Bilder) |
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET` | OAuth-Desktop-Client aus Google Cloud |
| `YT_REFRESH_TOKEN` | einmalig mit `auth_youtube.py url` / `token` erzeugt (YouTube Upload/Verwaltung, Analytics) |
| `DRIVE_REFRESH_TOKEN` | einmalig mit `auth_youtube.py url drive` / `token drive` erzeugt (Drive `drive.file`, getrennte Freigabe) |
| `GMAIL_REFRESH_TOKEN` | einmalig mit `auth_youtube.py url gmail` / `token gmail` erzeugt (Bericht per E-Mail) |
| `REPORT_EMAIL` | Empfänger des Berichts (nötig, da gmail.send das eigene Profil nicht lesen darf) |
| `DISTROKID_SONGWRITER`, `BUDGET_MAX_USD`, `TEXT_MODEL` | optional (siehe oben) |

Systemwerkzeuge: `ffmpeg`, `ffprobe`, Python 3.11+. Abhängigkeiten: `pip install -r requirements.txt`.

## Ablauf pro Mix

```bash
which ffmpeg || (sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg)
pip install -q -r requirements.txt --break-system-packages
python run_mix.py concepts/<slug>.json --out build/<slug> --upload --drive
```

Ergebnis in `build/<slug>/`: `mp3/` (Tracks mit Cover + ID3), `covers/` (1400² je Track, `album_3000.png`),
`video/<slug>.mp4` (1920×1080, AAC 192k), `thumbnail/thumb_A|B|C.jpg`, `shorts/short_1|2.mp4` (1080×1920, 45 s),
`metadata.txt`, `result.json`
und `build/<slug>.zip` zum Versand (MP3s, Cover, Thumbnails, Metadaten – ohne Video, das liegt auf YouTube).

Optionen:
- `--dry-run` – synthetisches Audio und prozedurale Bilder, keine API-Kosten (Funktionstest)
- `--upload` – lädt das Video hoch (privat), setzt Thumbnail A, fügt zur Playlist hinzu, setzt KI-Label
- `--public` – Mix und Shorts sofort öffentlich; postet zusätzlich den Kommentar aus `pinned_comment`
  (anpinnen geht nur in Studio; braucht Scope youtube.force-ssl → YouTube-Freigabe einmal erneuern)
- `--publish-at 2026-10-02T16:00:00Z` – stattdessen geplante Veröffentlichung (UTC)
- `--drive` – legt die MP3s einzeln (Unterordner `mp3/`), Album-Cover, Video, alle Thumbnails, Metadaten und Shorts (`shorts/`) in Google Drive unter
  `AIX WALKER Mixe/<Datum – Album (Genre, BPM)>` ab (je Mix ein neuer Ordner)
- `--no-shorts` – keine Shorts

## Konzeptdatei

Siehe `concepts/example.json`. Der Freitags-Lauf schreibt pro Mix eine neue Datei `concepts/<slug>.json`
mit allen Texten (Titel, Hook, Tags, Track-Titel alphabetisch, Variationen je Track, Bild-Prompts, A/B-Varianten,
Shorts-Vorschläge). Track-Titel sind Eigenkreationen, alphabetisch sortiert.

## Analytics

`python -m pipeline.youtube` zeigt Kanal, Wiedergabestunden (365 Tage) und die Kennzahlen der letzten Uploads.
Der Freitags-Lauf nutzt das, um die 10 Vorschläge datenbasiert zu gewichten.

## Mindestlänge und Shorts

- `min_minutes` (Standard 60): Reichen die geplanten Tracks nicht, werden `extra_tracks` und danach weitere
  komplett neue Tracks erzeugt, bis der Mix die Länge erreicht – nie Reprisen oder Wiederholungen. `minutes_per_track` (Standard 5) ist die Wunschlänge je Lyria-Track.
- Shorts: Energie- und Helligkeitsanalyse des Mixes (1-s-Raster), Hook-Score = Energie + Anstieg (Build-up → Drop)
  + Helligkeit; 2 Passagen à 45 s aus verschiedenen Tracks, 9:16 mit Hook-Text (`short_overlays`), Cover und
  Verweis auf den vollen Mix; Upload privat mit „#Shorts“ im Titel und Link zum Mix in der Beschreibung.

## Kosten

`python -m pipeline.costs concepts/<slug>.json` zeigt den Voranschlag (Lyria 0,08 $/Track, Nano Banana 0,039 $/Bild,
Nano Banana Pro 0,134 $/Bild; Preise in `pipeline/config.py`). Während des Laufs zählt `build/<slug>/costs.json`
jeden echten API-Aufruf; `result.json` enthält `cost_usd`, `cost_eur` und `cost_report`. Google bietet keinen
Kontostand für die Gemini-API – der reale Monatsstand steht in Cloud Billing (`BILLING_URL`). `BUDGET_WARN_USD`
(Standard 5 $) setzt die Warnschwelle je Lauf.

## Qualitätsregeln

- Jeder Track: 90–480 s, < 15 % Stille, Tempo passend (halb/doppelt erlaubt), sonst Neuversuch
- Mastering EBU R128 auf −14 LUFS, True Peak −1 dB, Stille am Anfang/Ende getrimmt
- Crossfade 1,5 s zwischen Tracks; Kapitel aus den realen Startzeiten, über 60 Min als `01:02:13`
- Thumbnail: max. 3 Wörter, Motiv werbefreundlich
- KI-Label (`containsSyntheticMedia`) wird beim Upload immer gesetzt

## Kids-Shorts (täglich 16:00, eigener Kids-Kanal)

Tägliche 15-Sekunden-Shorts im Pixar-/Disney-Look ohne Sprache (Story → Nano Banana → Veo 3.1 → ffmpeg →
Upload „für Kinder“ → E-Mail). Einrichtung: `KIDS_SHORTS_PLAN.md`; tägliche Routine: `KIDS_ROUTINE_PROMPT.md`.

```bash
python run_kids_short.py --dry-run                  # Funktionstest ohne Kosten
python run_kids_short.py --upload --private         # Testlauf, privat
python run_kids_short.py --publish-local 16:00      # Produktion: heute 16:00 Uhr Berlin öffentlich
python run_kids_compilation.py --upload             # danach: 16:9-Zusammenschnitt (Intro + Shorts), sofort öffentlich
python run_kids_compilation.py --dry-run            # Zusammenschnitt-Funktionstest ohne Drive/Upload
python run_kids_compilation.py --vertical --if-due --upload --publish-tomorrow 09:00   # langer Short (Mo/Mi/Fr → Di/Do/Sa 09:00)
```

| Variable | Zweck |
|---|---|
| `KIDS_YT_REFRESH_TOKEN` | OAuth-Token des Kids-Kanals (`python auth_youtube.py url kids` / `token kids`) |
| `KIDS_BUDGET_USD` | harte Kostengrenze je Lauf (Standard 10) |
| `KIDS_VEO_MODELS` | Komma-Liste der Veo-Modelle, Standard zuerst |
| `GMAIL_REFRESH_TOKEN` | optional: Report-Mail ohne Gmail-Connector (`auth_youtube.py url gmail`) |
| `KIDS_CHANNEL_NAME` | Anzeigename des Kids-Kanals (nur für Texte) |
| `KIDS_LONGSHORT_BUILD_DAYS` | Wochentage (0 = Mo … 6 = So), an denen der lange Short gebaut wird; Standard `0,2,4` |
| `KIDS_LONGSHORT_COUNT` | Stories je langem Short (Standard 4, max. ≈ 10 wegen 3-Minuten-Grenze) |
| `KIDS_FLAGSHIP_EVERY_N_DAYS` | Alle wie viele Tage die wiederkehrende Flaggschiff-Figur (`kids/config.py: FLAGSHIP_CHARACTERS`) statt eines neuen Tieres auftritt (Standard 4) – für Wiedererkennung/Merch-Chancen |
| `KIDS_AFFILIATE_LINE` | Fertige Zeile inkl. Link für die Videobeschreibung (z. B. Amazon-Partnerprogramm); nicht gesetzt = eingebauter Standard (`kids/config.py: DEFAULT_AFFILIATE_LINE`), leer gesetzt = kein Zusatztext |
| `METRICOOL_TOKEN` | optional – Instagram Reel (17:00) + TikTok (18:00) je Short über Metricool (`kids/social.py`, Plan: `KIDS_SOCIAL_PLAN.md`); nur nötig im bezahlten Metricool-Tarif (Advanced/Custom). Ohne Token schreibt das Skript stattdessen `social_plan.json`, und die Tages-Sitzung postet kostenlos über den verbundenen Metricool-MCP-Connector (Routine-Schritt 4d). Der lange Short (Mo/Mi/Fr) geht zusätzlich eigenständig auf TikTok (Routine-Schritt 4c) – TikToks Creator Rewards Program zahlt nur für Videos über 1 Minute. `KIDS_SOCIAL_NETWORKS`, `KIDS_SOCIAL_TIMES`, `KIDS_SOCIAL_DRAFT=1` (nur mit Token) für Tests |
| `DRIVE_REFRESH_TOKEN` | vorhandene Drive-Freigabe; Ablage je Short unter `Giggle Meadow Shorts/<Datum – Titel>` (`KIDS_DRIVE_ROOT` ändert den Ordnernamen) |
