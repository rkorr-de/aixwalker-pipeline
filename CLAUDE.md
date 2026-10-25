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
  Das Skript erzeugt das Bild in 4K (0,24 $), prüft es automatisch (Schreibtisch mit zwei Monitoren sichtbar, Bürostuhl (Cognac oder schwarz), kein Text, Person nur unscharf von hinten, kein Tageslicht/Blaustich,
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
- **Tokyo-Mixe: Raum-Variationen automatisch** (Rolf 22.10.2026, ab dem Mix vom 23.10.): `concepts/tokyo_variation.py` wählt pro neuem Raum selbst (aus Gedächtnis „tokyo“, nie dreimal hintereinander dasselbe)
  und baut es ins Bild-Prompt ein: **Schreibtisch** vorne oder im hinteren Teil der Wohnung (nur sichtbar muss er sein), **Bürostuhl** Cognac-Leder oder schwarz, wechselnde Stellung (abgewandt, zur Kamera, herangeschoben, schräg, zum Fenster),
  **Sofa** mal Stoff, mal Leder (mit Farbe), **Wandkunst**: etwa jeder dritte Raum bekommt im Wohnbereich ein großes japanisches abstraktes Tuschebild in strikt Schwarz-Weiß (sumi-e, kein Text), jedes Mal ein anderes aus 16 Varianten; sonst andere Kunst (Holzschnitte usw.).
  Der Szenentext darf Sofa, Schreibtisch, Stuhl und Wandbild NICHT festlegen (das Skript streicht solche Sätze). Überschreiben: `--desk-pos`, `--chair`, `--sofa`, `--art`. Die Wahl steht in `neuer_raum.json`, `result.json` und im Gedächtnis („variation“).
  Die Raumprüfung passt sich an (hinterer Schreibtisch, schwarzer Stuhl; tastatur/Maus dürfen klein sein).
- **Tokyo-Mixe: weitere Raum-Variationen** (Rolf 22.10.2026, im selben Baustein `concepts/tokyo_variation.py`, automatisch gewählt): **Stuhl** Eames (Cognac-Leder) ODER Herman Miller Aeron Onyx Black (`--chair eames|aeron`);
  **Tastatur** HHKB Studio oder Keychron Q Pro (Lubed Switches); **Audio** KEF LSX II oder Genelec RAW (Recycling-Aluminium) auf Tischstativen plus Sennheiser HD 800 S an Schiit-Verstärker (statt Headset);
  **Deko weit weg von der Kamera**: Designer-Toy-Figur, gerahmter Mecha-Artprint oder Vinyl-Figur – bewusst Originaldesigns, KEINE geschützten Figuren (kein echtes KAWS/Bearbrick/Evangelion), analog zur Lain-Regel;
  **Homelab-Rack** (UniFi-Stil, matte Glasfront, weiß/cyan) im Flur (~70 %), **Luftreiniger** (Dyson- oder Balmuda-Stil), **versenkte Roboter-Dockingstation** in der Küche (~60 %), dezente Cyan-Lichtkanten unter schwebenden Möbeln (~70 %);
  **Raumhülle** „Tokyo Brutalism meets Japandi“: überwiegend Schalungsbeton mit Ankerlöchern, Mikrozementboden, Walnuss/geräucherte Eiche, Shou-Sugi-Ban-Fronten, Akzentwand (Shikkui / gerillte Betonpaneele / Holzlamellen), Bonsai oder Schiefer-Skulptur, Licht ca. 2000 K mit Lichtvouten; Deckenlicht nur dezent (wenige winzige, gedimmte Downlights), KEINE Kugel-/Ballleuchten, keine Papierlaternen (Rolf 22.10.2026).
  Die Bildprüfung erlaubt kleine Cyan-Akzente. Testbilder: `python test_tokyo_images.py` (4 Bilder, ca. 1 $, Drive + Mail).
- **Tokyo-Short: Dauerzeile oben** (Rolf 20.10.2026, ab dem nächsten Short): Im oberen Drittel steht über die GANZE Länge des Shorts (ohne Ein-/Ausblenden, nahtlose Schleife) der Text
  „Slow Jazz / for Deep Work & Coding“ (`SHORT_TOP_TEXT`, `short_top_layer()` in run_tokyo.py; Cinzel, Gold + Cremeweiß, weicher dunkler Verlauf, Mitte bei ca. 21 % der Höhe). Der Spruch bleibt in der Bildmitte.

- **Winter-Cabin: Kostengrenze 9 €** (Rolf 21.10.2026): Der Lauf 21.10. (Winterwood Hideaway) kostete 39,60 $ statt 8,88 $ Voranschlag, fast nur durch
  Veo-Clips (15 statt 2, je 2,40 $): drei Versuche je Clip, dazu Neustarts, bei denen abgelehnte Clips neu bezahlt wurden. Jetzt:
  `config.RUN_BUDGET_EUR = 9.0` (inkl. Neustarts), `costs.guard()` vor jedem bezahlten Aufruf, abgelehnte Clips zählen bei Neustarts mit
  (höchstens 3 Versuche je Clip). Bei Abbruch (Exit-Code 4) liegen ALLE abgelehnten Clips in Drive, die Mail enthält einen Link je Clip,
  den Prüfgrund und die Kosten; NICHT neu starten. Die normale Mail zeigt die Kosten aufgeschlüsselt (Tracks, Bilder, Veo-Clips).
  Mit 9 € ist neben den 2 Clips praktisch kein Ersatz-Clip drin (Tracks 3,36 $ + Bild 0,24 $ + 3 Clips 7,20 $ = 10,80 $ ≈ 9,94 €).

  **Clip selbst erzeugen (Rolf 21.10.2026):** Bei Abbruch läuft die Musik fertig (die Grenze sperrt nur den zu teuren Clip, nicht die Tracks). Auf Drive im
  Abbruch-Ordner liegen: abgelehnte Clips, Hauptbild (`frame_4k.png`, `master.jpg`), alle Tracks (`tracks/`), Konzept und `veo_prompt.txt`; die Mail enthält das EXAKTE Video-Prompt
  (`loopvideo.LOOP_PROMPT`) mit Anleitung. Rolf erzeugt den Clip mit seinem Gemini-Pro-Konto und lädt ihn im Chat hoch. Dann: `python restore_cabin_abort.py <slug> <Drive-Ordner-ID>`
  (holt Konzept, Tracks, Hauptbild), danach `python run_auto.py --concept concepts/<slug>.json --clip <Clip.mp4>` (Clip wird auf 4K/24 fps gebracht, 1 Clip = A+B; keine Veo-Kosten, keine neuen Tracks).
- **Tokyo-Bildprompt: IMMER Nachtszene, kein Tageslicht** (Rolf 22.10.2026): Der Prompt endet mit einem Nacht-Satz (tiefschwarzer Nachthimmel hinter allen Fenstern, kein Tageslicht, keine Dämmerung/blaue Stunde); `run_tokyo.py` bricht ab, wenn der Szenentext Tag-/Dämmerungswörter nennt (daylight, sunrise, sunset, dusk, morning …); die Bildprüfung wertet auch Dämmerung und hellen/blauen Himmel als Fehler (`daylight`).
- **Tokyo-Bildprompt: PC-Gehäuse als Variation** (Rolf 22.10.2026, `PCS` in `tokyo_variation.py`, Feld `pc` in der Variation): Fractal-North-Stil (Charcoal, Walnuss-Front, getöntes Glas, dezentes Warmweiß/Amber, auf Schreibtisch oder Sideboard) ODER kompakter SFF-Alu-PC (Fractal Terra / FormD T1, sandgestrahltes Graphit, neben den Monitoren) ODER dunkles gebürstetes Alu-Gehäuse (InWin 905 / Lian Li). Nie RGB-Beleuchtung, kein Markenschriftzug.
- **Tokyo-Bildprompt: Person arbeitet am Schreibtisch** (Rolf 22.10.2026, `PERSON_AT_DESK` in `tokyo_variation.py`, Variation `at_desk`, ca. 40 %, nie dreimal hintereinander; `--person-place auto|window|desk`): cineastische, fotorealistische Nachtaufnahme über die Schulter von schräg hinten, Gesicht nicht sichtbar. Frau: japanisch, Anfang 30, lockerer Dutt, Off-Shoulder-Strickjacke über grünem Seiden-Camisole, weite Leinenhose, Füße auf dem Sitz. Mann: japanisch, Mitte 30, Two-Block-Frisur, runde Acetat-Brille (nur Bügel sichtbar), schwarzer Strickpullover, Canvas-Hose, Filzpantoffeln, Utility-Watch. Bewusst ohne „provocative/revealing“-Formulierungen und ohne sichtbaren Bauch (YouTube-tauglich). Stil-Zusatz beginnt jetzt mit „Cinematic, photorealistic“. Tests: `python test_tokyo_persons.py`.
- **Tokyo-Bildprompt: Boden IMMER dunkel** (Rolf 22.10.2026): nahtloser, seidenmatter Anthrazitbeton (Mikrozement), nie hellgrau, nie Holz (`SHELL` und Stil-Zusatz in `tokyo_variation.py`).
- **Tokyo-Bildprompt: genau EINE Person, vier Varianten** (Rolf 22.10.2026): Frau oder Mann (`--person auto|woman|man`, automatisch wechselnd, nie dreimal dasselbe) und entweder sitzt sie/er arbeitend am Schreibtisch (Blick über die Schulter) ODER steht am Fenster und schaut hinaus (`--person-place auto|desk|window`, je ca. 50 %, nie dreimal hintereinander gleich). Im Tagesauftrag `--person auto` verwenden.
- **Tokyo-Beschreibung: Amazon-Partnerlinks** (Rolf 22.10.2026): `concepts/tokyo_shop.py` hängt zwischen Einleitung und Kapiteln einen Block mit Verkaufssatz (4 wechselnde Sätze) und den Amazon.de-Links
  der im Raum gewählten Geräte an (Tastatur, KEF, HD 800 S, PC-Gehäuse North XL/Terra, Dyson, UniFi), danach EINE Zeile „Ad · Affiliate links – As an Amazon Associate I earn from qualifying purchases.“ (englisch auf Rolfs Wunsch 22.10.2026, so knapp wie möglich).
  Partner-ID `gigglemeadow2-21`. Ohne Link bleibt die Zeile weg (Genelec, Lian Li/InWin-PC, Balmuda, Stuhl, Schiit). Neue Links: in `PRODUCTS` eintragen. Alte Räume ohne Variation: kein Block.
- **Tokyo-Mix mit Rolfs eigenem Hauptbild** (Rolf 22.10.2026, ab 23.10.): KEINE Bild-Erzeugung mehr durch Claude (spart 0,24–0,72 $ je Mix; ein Mix kostet nur die Musik: 22 Lyria-Tracks ≈ 1,76 $ ≈ 1,62 €).
  **Phase A** (täglich 06:00): `python run_tokyo.py --prompt-only --new-room --room <kennung> --scene-file ... --desk-side ... --person auto --quote-text ... --description-file ...`
  baut Variation + komplettes Bildprompt, legt `plan_<Datum>.json` und `bildprompt_<Datum>.txt` in Drive „AIX WALKER Mixe/Tokyo Hauptbild“ ab und mailt Rolf Prompt + Anleitung (`tokyo_inbox.send_prompt_mail`; Gemini → Bild → Upload in diesen Ordner).
  **Phase B** (stündlich 9:30, 10:30, 11:30, 12:30, 13:30, oder sofort, wenn Rolf im Chat „Tokyo Bild fertig“ schreibt → `fire_trigger`): `python run_tokyo.py --from-inbox --upload --drive` holt Plan und das NEUESTE Bild aus dem Ordner (nach dem Plan hochgeladen), baut Mix + Short wie sonst.
  Exit-Codes: 4 kein Plan, 5 noch kein Bild (still beenden), 6 läuft schon (<3 h) oder fertig. Plan-Status in Drive: „wartet auf Bild“ → „gestartet“ → „fertig“. Mix wird nach Fertigstellung sofort öffentlich (nicht mehr 9:00). Variation, Quote und Beschreibung kommen aus dem Plan (Amazon-Links passen so zum Bild).
  Geplante Aufgaben: Phase A = `trig_017pBk9j8iKk9uz21feTAi55` (täglich 6:07 Berlin), Phase B = `trig_01P4g9YW6NdJ7uVHsNrtnd8f` (9:33–13:33 stündlich). Schreibt Rolf im Chat „Tokyo Bild fertig“: `fire_trigger` auf Phase B (frühestens ab 9:30 Uhr, davor Rolf auf 9:30 verweisen).
- **Tokyo-Bildprompt: Anatomie-Zusatz für die Person** (Rolf 23.10.2026, ab Phase A am 24.10.): `ANATOMY` in run_tokyo.py hängt hinter die Personenbeschreibung (Frau/Mann, Schreibtisch/Fenster):
  „Use for the person always perfect anatomy, detailed hands, correct fingers, accurate human anatomy, beautifully detailed feet, flawless hands, highly detailed hands.“ Das Prompt vom 23.10. war schon erzeugt, ohne den Zusatz.
- **Tokyo: Phase B läuft seit 24.10.2026 in der Phase-A-Aufgabe** (Rolf 24.10.2026): Die separate Phase-B-Aufgabe `trig_01P4g9YW6NdJ7uVHsNrtnd8f` wurde am 23.10. aus einer Chat-Sitzung ohne Zugangsdaten angelegt und lief deshalb nie (YT_*/DRIVE_*/GMAIL_*-Variablen fehlen dort); sie ist ABGESCHALTET. Nur die Umgebung „AixWalker“ hat die Zugangsdaten.
  Jetzt macht `trig_017pBk9j8iKk9uz21feTAi55` beides: täglich 6:07 Phase A (kein Plan → Bildprompt + Mail) und 10:07, 11:07, 12:07, 13:07 Phase B (Plan „wartet auf Bild“ → Mix bauen), sonst still. „Tokyo Bild fertig“ im Chat → `fire_trigger` auf diese Aufgabe mit Zusatztext. NIE neue Tokyo-Aufgaben aus einer normalen Chat-Sitzung anlegen, sondern vorhandene Aufgaben ändern (`update_trigger`).
- **Mega-Mix: Community-Text + beschriftetes Album-Cover in der Bestätigungsmail** (Rolf 24.10.2026): `run_megamix.py` baut je Mega-Mix einen kurzen, romantischen englischen Community-Text MIT Video-Link
  (`community_text()`, Platzhalter `{URL}`, ohne Zeit-/Längenangaben); `send_mail` ersetzt den Link und hängt Thumbnail + beschriftetes `album_3000` an (das Cover war schon angehängt, der Text war vorher deutsch und ohne Link).
- **Tokyo-Mega-Mix** (Rolf 24.10.2026): `python run_tokyo_megamix.py` baut aus den vorhandenen Tokyo-Mixen (Drive, Ordner „Tokyo Work Lounge“, Genre „Slow Jazz“) einen bis zu 8 Std. langen Mix
  (Zufallsreihenfolge, kein Song doppelt, keine neue Musik, kein neues Bild: `master.jpg` des neuesten Tokyo-Mixes). Läuft SOFORT, lädt PRIVAT hoch (kein Warten, keine Planung), dazu 1 Short (privat, Eintrag in „shorts2“),
  beschriftetes `album_3000.png`, Thumbnail, `metadata.txt`, Drive-Ordner „<Datum> – MEGAMIX Tokyo Work Lounge – Tokyo Work Lounge (<n> Min)“, Community-Text, Mail (`run_megamix.send_mail`). Gedächtnis: Liste „tokyo_megamix“
  (die Samstags-Rotation bleibt unberührt). Spruch für den Short per `--quote-text`, sonst Standard (pro Lauf neu wählen!). Test ohne Kosten: `--dry-run`.
- **Tokyo-Sonntags-Mega-Mix, neues Konzept** (Rolf 24.10.2026, ersetzt den Eintrag „Tokyo-Mega-Mix“): `run_tokyo_megamix.py` läuft AUTARK. Claude denkt sich pro Lauf NEU aus: Raum (Kennung + Szenentext wie bei den Tokyo-Mixen),
  Spruch, Beschreibungstext, Community-Text (`{URL}`, `{HOURS}`) und ruft auf: `python run_tokyo_megamix.py --room <kennung> --scene-file ... --desk-side left|right --person auto --quote-text "..." --description-file ... --community-file ...`
  (Beispiel-Dateien: `megamix_inputs/2026-10-24/`). Das Skript erzeugt das NEUE Bild selbst (Variation, Prüfung, Easter-Egg), mischt bis zu 8 Std. aus allen vorhandenen Tokyo-Mixen (kein Song doppelt, keine neue Musik),
  baut das Video wie die normalen Tokyo-Mixe (Spruch-Intro, Blenden), Beschreibung mit Amazon-Links, lädt SOFORT ÖFFENTLICH hoch, postet die Tracklisten-Kommentare, macht 1 Short (öffentlich), Cover, Thumbnail, Drive-Paket
  und sendet EINE Mail (Community-Text, Cover, Infos). Gedächtnis „tokyo_megamix“. Fehler/zu wenig Material: Mail an Rolf (Exit 2/3), Exit 6 = heute schon gelaufen.
  Ursache der 1 Std. am 24.10.: Alle Tokyo-Mixe benutzen dieselben 22 Songtitel, der Titelvergleich hat sie als „doppelt“ gelöscht → jetzt zählen nur identische Audiodateien (`by_title=False`).
- **Tokyo: Claude erzeugt die Bilder wieder selbst** (Rolf 24.10.2026, ersetzt „Tokyo-Mix mit Rolfs eigenem Hauptbild“): Rolf liefert KEIN Bild mehr. Die Aufgabe `trig_017pBk9j8iKk9uz21feTAi55` läuft täglich 6:07 (Tagesmix, Cron `6,8`) und sonntags 8:07 (Mega-Mix):
  `python run_tokyo.py --new-room --room <kennung> --scene-file ... --desk-side ... --person auto --quote-text ... --description-file ... --upload --public --drive` (Bild 4K mit Prüfung, 22 Tracks, Mix sofort öffentlich, Short privat), danach `send_tokyo_mail.py`.
  Phase A/B (`--prompt-only`, `--from-inbox`, Drive „Tokyo Hauptbild“) ist abgeschafft, bleibt nur im Code.
- **Tokyo: Vol.-Nummer wird immer geprüft** (Rolf 25.10.2026, nach doppeltem „Vol. 8“): `next_vol()` nimmt das Maximum aus Gedächtnis „tokyo“ (Feld vol), den „Vol. N“-Titeln der Tokyo-Videos auf YouTube (`youtube_vols()`, auch von Hand korrigierte) und `VOL_FLOOR − 1` (Untergrenze, ab 25.10. = 9) und zählt 1 hoch; im Log steht „Titelnummer: Vol. N (Gedächtnis max …, YouTube max …)“.
  Nach dem Lauf im Bericht an Rolf die Nummer nennen. Ist weder Gedächtnis noch YouTube lesbar, bricht der Lauf ab. Rolf korrigiert Titel manchmal auf YouTube von Hand – diese Nummer gilt dann.
