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
- **Tokyo-Mixe: Spruch am Videoanfang bei JEDEM Mix neu** (Rolf 19.10.2026): Claude denkt sich pro Mix einen neuen Spruch aus und übergibt
  ihn mit `run_tokyo.py --quote-text "Zeile 1|Zeile 2|Zeile 3"`. Kriterien: Englisch, 2–3 Zeilen, je Zeile höchstens 42 Zeichen, ruhig,
  Arbeit/Fokus, die letzte Zeile bezieht sich auf „my tracks / my music“, keine Zeit-/Längenangaben, noch nie verwendet (das Skript prüft
  gegen die feste Liste und das Gedächtnis „tokyo“ und bricht sonst ab). Der Short übernimmt denselben Spruch automatisch.
- **Tokyo-Mail: genau EINE Mail pro Mix** mit neuem Spruch, neuem Pin-Kommentar, neuem Community-Text (zum Einkopieren) und den Handgriffen
  (`send_tokyo_mail.py ... --quote "<Spruch>" --pin ... --community ...`). Keine zweite „was du noch tun musst“-Mail.
