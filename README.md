# AIX WALKER Pipeline

Automatische Produktion wöchentlicher Musik-Mixe für den YouTube-Kanal **AIX WALKER**
(Lyria 3.5 → QC → Mastering → Cover → MP3/MP4 → Thumbnail → Metadaten → Upload privat).

## Voraussetzungen (Umgebungsvariablen)

| Variable | Zweck |
|---|---|
| `GOOGLE_API_KEY` | Gemini-API (Lyria 3.5 für Musik, Nano Banana für Bilder) |
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET` | OAuth-Desktop-Client aus Google Cloud |
| `YT_REFRESH_TOKEN` | einmalig mit `auth_youtube.py` erzeugt |

Systemwerkzeuge: `ffmpeg`, `ffprobe`, Python 3.11+. Abhängigkeiten: `pip install -r requirements.txt`.

## Ablauf pro Mix

```bash
which ffmpeg || (sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg)
pip install -q -r requirements.txt --break-system-packages
python run_mix.py concepts/<slug>.json --out build/<slug> --upload
```

Ergebnis in `build/<slug>/`: `mp3/` (Tracks mit Cover + ID3), `covers/` (1400² je Track, `album_3000.png`),
`video/<slug>.mp4` (1920×1080, AAC 192k), `thumbnail/thumb_A|B|C.jpg`, `metadata.txt`, `result.json`
und `build/<slug>.zip` zum Versand (MP3s, Cover, Thumbnails, Metadaten – ohne Video, das liegt auf YouTube).

Optionen:
- `--dry-run` – synthetisches Audio und prozedurale Bilder, keine API-Kosten (Funktionstest)
- `--upload` – lädt das Video **privat** hoch, setzt Thumbnail A, fügt zur Playlist hinzu, setzt KI-Label
- `--publish-at 2026-10-02T16:00:00Z` – stattdessen geplante Veröffentlichung (UTC)

## Konzeptdatei

Siehe `concepts/example.json`. Der Freitags-Lauf schreibt pro Mix eine neue Datei `concepts/<slug>.json`
mit allen Texten (Titel, Hook, Tags, Track-Titel alphabetisch, Variationen je Track, Bild-Prompts, A/B-Varianten,
Shorts-Vorschläge). Track-Titel sind Eigenkreationen, alphabetisch sortiert.

## Analytics

`python -m pipeline.youtube` zeigt Kanal, Wiedergabestunden (365 Tage) und die Kennzahlen der letzten Uploads.
Der Freitags-Lauf nutzt das, um die 10 Vorschläge datenbasiert zu gewichten.

## Qualitätsregeln

- Jeder Track: 90–300 s, < 15 % Stille, Tempo passend (halb/doppelt erlaubt), sonst Neuversuch
- Mastering EBU R128 auf −14 LUFS, True Peak −1 dB, Stille am Anfang/Ende getrimmt
- Crossfade 1,5 s zwischen Tracks; Kapitel aus den realen Startzeiten, über 60 Min als `01:02:13`
- Thumbnail: max. 3 Wörter, Motiv werbefreundlich
- KI-Label (`containsSyntheticMedia`) wird beim Upload immer gesetzt

## Regel: Paket immer komplett und richtig (ohne Eingriff von Rolf)

Nach der Produktion sind Laufzeit und Kapitelzeiten die Wahrheit. `metadata.sync_concept` gleicht deshalb automatisch an:
alle Minutenangaben („45 Min“, „45 minutes“, „45 Minuten“) in Titel, Hook, Thumbnail-Text, A/B-Varianten und Community-Text,
sowie die Shorts-Zeitmarken. Shorts werden bevorzugt als `{"track": "<Titel>", "offset": 10, "length": 40, ...}` angegeben,
dann berechnet die Pipeline Start/Ende aus den realen Track-Startzeiten. Feste Zeiten außerhalb der Laufzeit brechen den Lauf ab.
Bei Abweichungen wird nichts dem Nutzer überlassen: Metadaten, Thumbnail, Beschreibung und ZIP werden selbst korrigiert;
ein bereits hochgeladenes Video wird mit `--update-video <ID>` (Titel, Beschreibung, Tags, Thumbnail) aktualisiert.
Nach jedem Lauf prüfen: Titel/Beschreibung/Thumbnail/Shorts passen zur echten Dauer, ZIP und metadata.txt sind aktuell.
Minutenangaben werden **abgerundet** (45:43 → „45 Min“), damit nie mehr versprochen wird als geliefert.
