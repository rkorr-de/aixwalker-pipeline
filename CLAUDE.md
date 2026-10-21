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
- **Tokyo-Mixe: Beschreibungstext bei JEDEM Mix neu** (Rolf 19.10.2026): Claude schreibt pro Mix einen frischen englischen Einleitungstext (2–4 Absätze,
  250–1200 Zeichen, passend zu Raum, Spruch und Stimmung, keine Zeit-/Längenangaben, nicht die alten Standardsätze) in eine Datei und übergibt sie mit
  `run_tokyo.py --description-file <Datei>`. Kapitel, Musik-/KI-Hinweis und Hashtags hängt das Skript automatisch an.
- **Tokyo-Mixe: Titel mit laufender Nummer** (Rolf 19.10.2026): `🎧 Tokyo Work Lounge | Slow Jazz for Deep Work & Coding - Vol. N🎷`. Der Mix vom 19.10.2026 ist
  Vol. 2; `run_tokyo.py` zählt automatisch hoch (Gedächtnis „tokyo“, Feld `vol`), `--vol N` überschreibt. Der echte Titel steht in `result.json` („title“).
- **Tokyo-Mixe: Album-Cover 1:1 aus dem Hauptbild** (Rolf 19.10.2026, gilt ab dem nächsten Mix): volle Bildhöhe des Originalbilds, der Ausschnitt wird waagerecht
  so gelegt, dass der Schreibtisch immer zu sehen ist (`DESK_X` je Raum, oder `--cover-desk-x 0.0–1.0` = Schreibtischmitte von links), Text wie im Thumbnail;
  als `album_3000.png` im Drive-Ordner und als `tokyo_album_cover.jpg` an der Bestätigungsmail (`send_tokyo_mail.py` hängt `img/album_3000.png` automatisch an).
  Ist der Schreibtisch im fertigen Cover nicht klar zu sehen, `--cover-desk-x` anpassen und neu bauen. `--album-cover <Datei>` überschreibt weiter.
- **Tokyo-Mail: kompletter DistroKid-Name** (Rolf 19.10.2026): Die Mail nennt immer den vollen Release-Namen, z. B. `Tokyo Work Lounge (Slow Jazz for Deep Work & Coding), Vol. 2`
  (der erste Mix hieß ohne Nummer). `send_tokyo_mail.py` baut ihn aus `result.json` („vol“).
- **Tokyo-Mixe: JEDES MAL NEUER RAUM + NEUES BILD** (Rolf 19.10.2026, gilt ab dem Mix nach Vol. 3, keine Freigabe nötig, wenn alle Kriterien erfüllt sind): Claude erfindet pro Mix
  einen neuen Ort (neue Kennung, z. B. `daikanyama-garden-loft`; nicht in Gedächtnis „tokyo“ Feld `room` und nicht in `r.ROOMS` verwendet) und schreibt einen englischen Szenentext
  (80–900 Zeichen: Fenster/Ausblick, Materialien, Stimmung; abends/nachts, warmes Licht, dunkle gerade Decke) in eine Datei. Aufruf:
  `run_tokyo.py --new-room --room <kennung> --scene-file <datei> --desk-side left|right --person woman|man ...` (Seite und Person gegenüber dem letzten Mix wechseln).
  Das Skript erzeugt das Bild in 4K (0,24 $), prüft es automatisch (Schreibtisch mit zwei Monitoren sichtbar, Cognac-Ledersessel, kein Text, Person nur unscharf von hinten, kein Tageslicht/Blaustich,
  keine Fehler), misst die Schreibtischmitte selbst für den Album-Cover-Ausschnitt und legt das Bild in Drive `bilder/<kennung>.png` ab. Bis zu 3 Versuche; scheitern alle, bricht der Lauf VOR der Musik
  mit Exit-Code 3 ab → dann mit einem vorhandenen Raum neu starten und das Rolf im Bericht sagen. Bildkosten (bis 0,72 $ bei 3 Versuchen) in die Kostenmeldung aufnehmen.
  Ergänzung Rolf 19.10.2026: Der Ort liegt IMMER in Tokyo (Szenentext nennt Stadtteil + „Tokyo“, alles passt zum Thema Tokyo). Der Arbeitsplatz ist ein echter Computerarbeitsplatz mit zwei Monitoren,
  Tastatur UND Maus, im Raum sichtbar (muss nicht direkt vorne im Bild sein); die Prüfung verlangt `keyboard_mouse`.
  Easter-Egg (Rolf 19.10.2026): In JEDEM neuen Raum steht irgendwo (Schreibtisch, Regal, Tisch, Sideboard; Ort wechselt) EINE kleine weibliche Manga-Figur, höchstens 15 cm hoch
  (`FIGURINE` in run_tokyo.py: silber-lavendelfarbener Pferdeschwanz, große weiße Kopfhörer, mintgrüner Hoodie). Eine geschützte Figur (z. B. Lain Iwakura) wird NICHT gezeichnet. Die Prüfung verlangt `figurine`.
- **Tokyo-Short: Kameraschwenk mit Schreibtisch UND Person** (Rolf 19.10.2026): Der 9:16-Ausschnitt des Shorts muss auf dem gesamten Schwenk den Schreibtisch (Monitor, Tastatur, Maus)
  und die Person (zumindest zum Teil, auch unscharf im Hintergrund) zeigen, sonst passen Text und Bild nicht zusammen. `make_short` zentriert den Schwenk auf `desk_x`;
  liegen Person und Schreibtisch auseinander, `--short-desk-x 0.0–1.0` (Mitte des Ausschnitts, von links) zwischen beide legen. Vorher den Ausschnitt (Anfang/Mitte/Ende des Schwenks) ansehen und prüfen.
  Nur Short neu: `run_tokyo.py --short-only --room <kennung> --mix-video-id <id> --quote-text "..." --short-desk-x <x>`.
- **Tokyo-Sprüche und Beschreibungen: Home-Office-Thema** (Rolf 19.10.2026, ab dem nächsten Mix): Mehr Bezug auf Arbeiten im Home Office, die kleine Pause zwischendurch und Coding
  (z. B. Tee holen, Fenster/Garten ansehen, Schultern lockern, ein Bug, ein Commit, der nächste Fokus-Block). Weiter: Englisch, ruhig, letzte Zeile „my tracks / my music“, noch nie verwendet.
  Automatisch (Rolf 19.10.2026 „automatisiere das“): Die Raumprüfung misst `person_x` und verlangt eine sichtbare Person; `short_center()` legt den Schwenk zwischen Person und Schreibtisch;
  `make_short_checked()` zieht Standbilder (Anfang/Mitte/Ende) und lässt sie prüfen (Schreibtisch + Person in ALLEN drei), bei Misserfolg verschiebt es den Ausschnitt und baut bis zu 3× neu (nur ffmpeg, kostenlos).
  Ergebnis steht in `short_check.json` und `result.json` („short_check“). Ist `ok` am Ende nicht `true`, im Bericht an Rolf sagen. Rolfs eigene Bilder (`--main-image`) werden ebenfalls vermessen.
- **Tokyo-Short: Dauerzeile oben** (Rolf 20.10.2026, ab dem nächsten Short): Im oberen Drittel steht über die GANZE Länge des Shorts (ohne Ein-/Ausblenden, nahtlose Schleife) der Text
  „Slow Jazz / for Deep Work & Coding“ (`SHORT_TOP_TEXT`, `short_top_layer()` in run_tokyo.py; Cinzel, Gold + Cremeweiß, weicher dunkler Verlauf, Mitte bei ca. 21 % der Höhe). Der Spruch bleibt in der Bildmitte.

- **Winter-Cabin: Kostengrenze 9 €** (Rolf 21.10.2026): Der Lauf 21.10. (Winterwood Hideaway) kostete 39,60 $ statt 8,88 $ Voranschlag, fast nur durch
  Veo-Clips (15 statt 2, je 2,40 $): drei Versuche je Clip, dazu Neustarts, bei denen abgelehnte Clips neu bezahlt wurden. Jetzt:
  `config.RUN_BUDGET_EUR = 9.0` (inkl. Neustarts), `costs.guard()` vor jedem bezahlten Aufruf, abgelehnte Clips zählen bei Neustarts mit
  (höchstens 3 Versuche je Clip). Bei Abbruch (Exit-Code 4) liegen ALLE abgelehnten Clips in Drive, die Mail enthält einen Link je Clip,
  den Prüfgrund und die Kosten; NICHT neu starten. Die normale Mail zeigt die Kosten aufgeschlüsselt (Tracks, Bilder, Veo-Clips).
  Mit 9 € ist neben den 2 Clips praktisch kein Ersatz-Clip drin (Tracks 3,36 $ + Bild 0,24 $ + 3 Clips 7,20 $ = 10,80 $ ≈ 9,94 €).
