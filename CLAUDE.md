# Hinweise für Claude

- **Mit Rolf immer auf Deutsch sprechen** – in jeder Antwort, jeder Rückfrage und jedem Bericht, auch wenn er
  selbst kurz auf Englisch antwortet. Ausnahme: YouTube-Metadaten (Titel, Beschreibung, Tags) bleiben Englisch.
- Anweisungen an Rolf in Anfänger-Sprache: jeden Klick benennen, kein Fachjargon.
- **Keywords und Tags immer mit Komma getrennt** schreiben (z. B. `ibiza chillout, balearic chillout, sleep music`) – in
  Antworten an Rolf und in `channel/keywords.txt`; nie leerzeichengetrennt mit Anführungszeichen.

- **Tokyo-Mixe: Pin-Kommentar und Community-Post** schreibe ich bei jedem Mix neu (englisch, passend zum Mix). Den Kommentar
  schreibe ich nach „Tokyo freigeben“ selbst unter den Mix (eingebauter Browser, Studio); Rolf pinnt ihn danach. Den
  Community-Post postet Rolf. Beide Texte stehen immer in der Mail (`send_tokyo_mail.py --pin ... --community ...`).
  Den Titel nehme ich aus `run_tokyo.TITLE`.
- **Tokyo-Mixe: Drive-Paket immer komplett** (Rolf 18.10.2026): `run_tokyo.py --drive` legt den Ordner
  `<Datum> – Tokyo Work Lounge – <Raum>[ v2] (Slow Jazz, 70 BPM)` an (muss auf „(Genre, BPM)“ enden), darin `album_3000.png`,
  `thumb.jpg`, `master.jpg`, `metadata.txt`, `mp3/` (22 MP3s `NN - Aix Walker - Titel.mp3`, bei `--reuse-music` serverseitig aus dem
  Quell-Mix kopiert) und `short/`. Eigenes Cover mit `--album-cover <Datei>`. Vor der Meldung an Rolf den Drive-Ordner prüfen.
