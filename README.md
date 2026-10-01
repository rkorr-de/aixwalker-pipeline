# AIX WALKER Pipeline

Automatische Produktion wöchentlicher Musik-Mixe für den YouTube-Kanal **AIX WALKER**
(Lyria 3.5 → QC → Mastering → Cover → MP3/MP4 → Thumbnail → 2 Shorts → Metadaten → Upload privat → Google Drive).

Die Anweisungen der geplanten Routine stehen in `ROUTINE_PROMPT.md` (die Routine liest diese Datei).

## Voraussetzungen (Umgebungsvariablen)

| Variable | Zweck |
|---|---|
| `GOOGLE_API_KEY` | Gemini-API (Lyria 3.5 für Musik, Nano Banana für Bilder) |
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET` | OAuth-Desktop-Client aus Google Cloud |
| `YT_REFRESH_TOKEN` | einmalig mit `auth_youtube.py` erzeugt (Scopes: YouTube Upload/Verwaltung, Analytics, Drive `drive.file`) |

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
- `--upload` – lädt das Video **privat** hoch, setzt Thumbnail A, fügt zur Playlist hinzu, setzt KI-Label
- `--publish-at 2026-10-02T16:00:00Z` – stattdessen geplante Veröffentlichung (UTC)
- `--drive` – legt ZIP, Album-Cover, Thumbnail, Metadaten und Shorts in Google Drive unter
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

- `min_minutes` (Standard 60): Reichen die geplanten Tracks nicht, werden `extra_tracks` und danach Reprisen
  erzeugt, bis der Mix die Länge erreicht. `minutes_per_track` (Standard 5) ist die Wunschlänge je Lyria-Track.
- Shorts: Energie- und Helligkeitsanalyse des Mixes (1-s-Raster), Hook-Score = Energie + Anstieg (Build-up → Drop)
  + Helligkeit; 2 Passagen à 45 s aus verschiedenen Tracks, 9:16 mit Hook-Text (`short_overlays`), Cover und
  Verweis auf den vollen Mix; Upload privat mit „#Shorts“ im Titel und Link zum Mix in der Beschreibung.

## Qualitätsregeln

- Jeder Track: 90–480 s, < 15 % Stille, Tempo passend (halb/doppelt erlaubt), sonst Neuversuch
- Mastering EBU R128 auf −14 LUFS, True Peak −1 dB, Stille am Anfang/Ende getrimmt
- Crossfade 1,5 s zwischen Tracks; Kapitel aus den realen Startzeiten, über 60 Min als `01:02:13`
- Thumbnail: max. 3 Wörter, Motiv werbefreundlich
- KI-Label (`containsSyntheticMedia`) wird beim Upload immer gesetzt
