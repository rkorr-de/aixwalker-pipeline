# Wochen-Routine AIX WALKER (Stand 2026-10-01)

Diese Datei enthält die aktuellen Regeln für den geplanten Lauf. Im geplanten Task (Prompt) ersetzen/ergänzen:

## Geänderte Regeln
- **Länge:** Jeder Mix ist rund **60 Minuten** lang (55–65). Konzept: `"target_minutes": 60`,
  `"minutes_per_track": 4`, **15–16 Tracks** (Lyria liefert ca. 94 % der angefragten Länge:
  4 Min angefragt ≈ 3:45 real; 16 × 3:45 ≈ 60 Min). Track-QC bleibt 90–300 s.
  Der Titel nennt die echte Dauer (`60 Min`). `run_mix.py` bricht vor dem Upload ab, wenn Dauer
  >5 Min vom Ziel oder >1,5 Min vom Titel abweicht – dann Tracks ergänzen/kürzen bzw. Titel anpassen
  und denselben Befehl erneut starten (fertige Tracks in `raw/` werden wiederverwendet).
- **Konzeptvorschläge:** Dauer 60 Min statt 30–45 Min.
- **Drive-Ablage:** Das MP3-Paket landet immer in Google Drive, in einem **neuen Ordner pro Mix**:
  `AIX WALKER / Mixe / <YYYY-MM-DD> – <Album>` (z. B. `2026-10-01 – Hot Stone Ritual`).
  Inhalt: ZIP(s) mit MP3s (max. 30 MB je Datei beim Chat-Versand, auf Drive ist die Gesamt-ZIP
  `build/<slug>.zip` ok), `covers/album_3000.png`, Thumbnails, `metadata.txt`.
  Ordner jeweils neu anlegen (nie wiederverwenden), dann Datei(en) hochladen und den Drive-Link melden.
  Voraussetzung: Google-Drive-Konnektor im geplanten Task aktiviert.
  Fehlt der Konnektor: melden und die Dateien wie bisher per SendUserFile in Teilen (<30 MB) senden.

## Prompt-Anpassungen (Textbausteine)
- Schritt 4: „… Dauer **60 Min** …“
- Schritt 7: „12–14 Tracks“ → „**15–16 Tracks**, `minutes_per_track` 4, `target_minutes` 60; yt_title nennt `60 Min`“
- Schritt 9: „Video-Dauer 30–45 Min“ → „**55–65 Min**“
- Schritt 10: „build/<slug>.zip … per SendUserFile senden“ → „**build/<slug>.zip in einen neuen
  Google-Drive-Ordner `AIX WALKER/Mixe/<Datum> – <Album>` hochladen** (zusammen mit Cover/Thumbnails/metadata.txt)
  und den Drive-Link per Nachricht senden; Cover/Thumbnails zusätzlich direkt senden“
