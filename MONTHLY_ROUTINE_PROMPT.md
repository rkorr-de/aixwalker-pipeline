# Routine „AIX WALKER Monats-Mix“ (am 1. jedes Monats, 05:03 Berlin) – Anweisungen

Antworte auf Deutsch (YouTube-Metadaten sind Englisch). Du arbeitest komplett ohne Rolf – keine Rückfragen.

## Ablauf
1. Arbeitsverzeichnis ist das Repo `aixwalker-pipeline` (prüfe `ls monthly_mix.py`).
2. `which ffmpeg || (sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg)` und
   `pip install -q -r requirements.txt --break-system-packages`.
   **Python prüfen (wichtig):** `python -c "import googleapiclient, librosa"`. Schlägt das fehl, nutze für ALLE
   folgenden Befehle `/usr/bin/python` statt `python` (dort liegen die Pakete; so war es am 06.10. nötig).
3. Prüfe, dass `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`, `DRIVE_REFRESH_TOKEN`, `GMAIL_REFRESH_TOKEN`
   gesetzt sind. Fehlt etwas: nichts starten, kurz melden, was fehlt.
4. `python monthly_mix.py` ausführen (Vormonat, öffentlich, kann > 30 Minuten dauern – Timeout großzügig, im Hintergrund
   laufen lassen und auf das Ende warten). Das Skript erledigt alles selbst: Mixe des Vormonats aus Drive holen, je Genre
   (≥ 2 Wochen-Mixe, ≥ 100 Min) zu einem 2–4-h-Mix verbinden, Monats-Thumbnail, Upload öffentlich, Playlist, Kommentar,
   Drive-Ordner „<Monat>-01 – MONTHLY …“, Gedächtnis (memory.json → `monthly`), Bericht per E-Mail.
5. Bricht es mit Fehler ab: einmal denselben Befehl wiederholen (bereits erledigte Genres stehen im Gedächtnis und
   werden übersprungen). Hilft das nicht, kurz die Fehlerzeile nennen – die Mail meldet Fehler ebenfalls.
6. Optional, nur falls ein Metricool-Tool mit YouTube-Community-Beiträgen verfügbar ist: den Community-Text aus
   `build/monthly-<Monat>/summary.json` (`texts.community_de`) dort veröffentlichen. Sonst überspringen – die API kann das nicht,
   der Text steht in der Mail.
7. Abschluss: 2–3 Sätze auf Deutsch (Genres, Links, Dauer, Probleme).

## Regeln
- Kosten: 1 Motivbild je Monats-Mix (ca. 0,13 $), keine Lyria-Kosten. Kein DistroKid-Release für Monats-Mixe.
- Video mit atmendem Licht aus den Album-Covern der Tages-Mixe (wie die normalen Mixe); nur bei Fehler Standbild.
- Eigene Linien (Italian Chillout) haben Vorrang und fallen nie wegen der Obergrenze von 4 Monats-Mixen weg.
- Nichts löschen, keine Quell-Mixe verändern.
