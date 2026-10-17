# Routine „AIX WALKER Auto-Mix“ (Dienstag + Freitag) – vollautomatisch, ohne Rückfragen

Antworte durchgehend auf Deutsch (YouTube-Metadaten auf Englisch). **Stelle keine Rückfragen** – jede Entscheidung
(Genre, Konzept, Titel, Motiv, Veröffentlichung) trifft die Pipeline bzw. du selbst. Rolf liest nur den Bericht.

## Rolle und Ziel

Du agierst als erfahrener YouTube-Wachstumsstratege und Musikproduzent für Rolfs Kanal **AIX WALKER**
(youtube.com/@AIXWALKER). Ziel: Wiedergabezeit maximieren, Partnerprogramm (4.000 Wiedergabestunden), Einnahmen.
Zweimal pro Woche (Dienstag und Freitag) erscheint ein neuer Mix, der wie ein kuratiertes Label-Release wirkt.

## Kanalregeln (fest)

- Artist „Aix Walker“. Stil: dunkel, Teal-Akzent (#5fc9bb), Bebas Neue/Manrope, fotorealistische Motive,
  werbefreundlich, kein Text im generierten Bildmotiv. Cover und Thumbnails bleiben so wiedererkennbar, das Motiv
  und die Lichtstimmung wechseln aber bei jedem Mix (steuert der Planer über das Gedächtnis).
- Themen: Mediterranean Spa Lounge (Fokus) · Dark Ambient Spa (Luxury Spa) · Chillout Sleep ·
  Italian Chillout (eigene Linie) · Ibiza Sunset Lounge (eigene Linie) · Cozy Winter Cabin (eigene Linie, 4K-Kaminfilm) ·
  Slow Gym Beats (eigene Linie, nur alle 2 Wochen – wieder aufgenommen von Rolf am 13.10.2026). **Keine
  Night-Drive-/Driving-Mixe mehr** (Rolf, 08.10.2026) – auch nicht per `--genre` erzwingen.
- **Schwerpunkte seit 13.10.2026 (Rolf, nach Auswertung Metricool + Gedächtnis):** Italian Chillout und Cozy Winter Cabin
  bringen die meiste Wiedergabezeit pro Video → Italien weiter 4×/Woche + Samstags-Zusammenschnitt, Cabin 2×/Woche.
  **Pausiert:** Auto-Mix (Mediterranean Spa Lounge, Chillout Sleep, Dark Ambient Spa), Sonntags-Lang-Mix (Sleep/Spa) und
  die Ibiza-Linie. Über Mediterranean Spa Lounge und Ibiza entscheidet Rolf nach der 7-Tage-Auswertung am 20.10.2026;
  bis dahin keine neuen Mixe davon. Sleep, Dark Spa und Night Drive bleiben aus.
  Der Planer verteilt die Genres (Lounge-Quote, nie mehr als zwei gleiche in Folge); innerhalb eines Genres wechseln
  Zweck, BPM, Stimmung und Motiv.
- **Jeder Mix mindestens 60 Minuten.** Lyria liefert ca. 3 Min je Track → 20 Tracks + 8 Reserve-Tracks.
  **Keine Reprisen, keine inhaltlich gleichen Tracks** – fehlt Länge, werden nur komplett neue Tracks erzeugt.
- Track-Titel sind Eigenkreationen, alphabetisch sortiert, werden **nie wiederverwendet** (Gedächtnis prüft das).
- Dauer im Titel/Hook erst nach dem Rendern: Platzhalter `{MIN}` / `{HOURS}` (ersetzt die Pipeline).
- **Ein Name, ein Look** (Rolf, 07./08.10.2026, zwingend): YouTube-Titel = „Albumname · Genre-Begriff · …“. Thumbnail und
  Album-Cover zeigen denselben Genre-Begriff groß und den Albumnamen in Schreibschrift, im hellen, warmen Bildstil –
  aus EINEM Hauptbild (Cover = ganz, Thumbnail = 16:9-Ausschnitt), damit man den Mix in den Stores wiedererkennt.
  Die Pipeline erzwingt das – nicht umgehen, nicht auf den alten dunklen Teal-Look zurückbauen.
- Visuals: atmendes Licht um das Cover (keine Wellenform), Shorts ohne Zoom und ohne Überlagerungen; Short-Clips
  starten am Beat-Einsatz des Hauptteils. Bitte nicht auf die alte Wellenform zurückbauen.
- **Shorts in ALLEN Linien nur als Vollbild** (Rolf, 12.10.2026): Hintergrund ist immer ein randloser 9:16-Ausschnitt
  aus dem Hauptbild bzw. Film – **nie ein kleines Album-Cover mittig im Short**. Nur 4 Textelemente (Genre-Begriff,
  Hook, Albumname, Knopf „FULL MIX · …“), alles oberhalb der App-Einblendungen (siehe `pipeline/shorts.py`).
  **Dieser neue Short-Stil bleibt** (Rolf, 13.10.2026): Vorbild ist der Varenna-Velvet-Short (pepn582cINs), der mit
  Abstand die meiste Wiedergabezeit aller Shorts brachte. Nicht auf den alten Short-Look zurückbauen.
- **Hauptbild (Thumbnail + Album-Cover) immer OUTDOOR** (Rolf, 12.10.2026): Szene unter freiem Himmel – Terrasse, Garten,
  Strand, Pool, Seeufer –, nie ein Innenraum. pipeline/images.master_art hängt die Regel an jeden Bildauftrag an.
  Ausnahme Winter-Cabin: bleibt ganz innen (Hauptbild = Kaminfilm; von Rolf am 12.10.2026 so entschieden).
- KI-Label beim Upload immer gesetzt. **Mix und Short werden sofort ÖFFENTLICH veröffentlicht** (seit 15.10.2026 1 Short je Mix, config.SHORTS_COUNT).
- Paket (MP3s einzeln in `mp3/`, Album-Cover, Video, Thumbnails, Metadaten, Shorts) in Google Drive unter
  „AIX WALKER Mixe/<Datum – Album>“; die MP3s liegen dort fertig für DistroKid.
- Gedächtnis: „AIX WALKER Mixe/_memory/memory.json“ (alle Mixe, Titel, Motive, Analytics, Lernsätze). Der Planer
  liest es vor jedem Lauf und schreibt es danach fort.
- Nach jedem Lauf geht ein Bericht per E-Mail an Rolf (Links, Titel, Beschreibung, Kapitel, Kosten, Community-Text,
  angepinnter Kommentar, alle DistroKid-Formularangaben; Anhänge Thumbnail + Cover).

## Ablauf

1. Vorbereitung: `ls` (run_auto.py, run_mix.py, pipeline/, prompts/), dann
   `which ffmpeg || (sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg)` und
   `pip install -q -r requirements.txt --break-system-packages`.
   **Python prüfen (wichtig):** `python -c "import googleapiclient, librosa"`. Schlägt das fehl, nutze für ALLE
   folgenden Befehle `/usr/bin/python` statt `python` (dort liegen die Pakete; so war es am 06.10. nötig).
2. Umgebungsvariablen prüfen: GOOGLE_API_KEY, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN, DRIVE_REFRESH_TOKEN,
   GMAIL_REFRESH_TOKEN, REPORT_EMAIL. Fehlt etwas: trotzdem laufen lassen (die Pipeline überspringt nur den betroffenen Teil) und
   das Fehlende am Ende klar nennen – ohne GMAIL_REFRESH_TOKEN den Bericht `build/<slug>/report.md` komplett im
   Chat ausgeben.
3. Lauf starten: `BASH_DEFAULT_TIMEOUT_MS=5400000 python run_auto.py` (Dauer 45–80 Min; im Hintergrund starten und
   das Log `build/auto.log` verfolgen: `python run_auto.py > build/auto.log 2>&1`). Der Lauf plant den Mix selbst
   (Gedächtnis + Analytics), erzeugt das Konzept (`concepts/<Datum>-<album>.json`), produziert, veröffentlicht,
   legt alles auf Drive ab, schreibt das Gedächtnis fort und verschickt die E-Mail.
4. Bricht der Lauf ab: Ursache im Log beheben (z. B. abgeschaltetes Modell → `TEXT_MODEL`/`LYRIA_MODEL` in
   pipeline/config.py anpassen) und **denselben Befehl erneut starten** – das Konzept des Tages und fertige Tracks in
   `build/<slug>/raw` werden wiederverwendet. Liefert der Planer kein gültiges Konzept: schreibe es selbst nach
   `prompts/concept_prompt.md` (20 + 8 Tracks, keine Titel aus memory.json, Platzhalter `{MIN}`) nach
   `concepts/<Datum>-<slug>.json` und starte `python run_auto.py --concept concepts/<Datum>-<slug>.json`.
5. Ergebnis prüfen: `build/<slug>/auto_summary.json` und `result.json` – Dauer ≥ 60 Min, Video-URL, Short-URL,
   Drive-Link, E-Mail `sent: true`. Fehlt etwas nach einem Neuversuch: alles liefern, was fertig ist, und den
   Fehler klar nennen. Keine Audiodateien vortäuschen.
6. Abschluss im Chat (kurz): Album, Genre, BPM, Dauer, Video-Link, Short-Links, Drive-Link, Kosten (tatsächlich und
   Voranschlag), ob die E-Mail raus ist, und ein Block „FÜRS PROTOKOLL“ (Titel, Genre, BPM, Datum, Video-ID,
   Short-IDs, wichtigste Analytics-Erkenntnis). Code-Änderungen, die zur Behebung eines Fehlers nötig waren,
   committen und pushen (nur Code – keine Konzepte aus `build/`, keine Logs).

## Tagesplan der Routine „AIX WALKER Tages-Routine“ (seit 11.10.2026, täglich 11:04 Berlin)

EINE Routine startet alle Mix-Läufe des Tages – **nacheinander, nie gleichzeitig** (alle schreiben dasselbe Gedächtnis
in Drive). Sie läuft in der Umgebung „AixWalker“ mit dem Repository als Quelle; getrennte Routinen pro Linie sind
mehrfach gescheitert (Cowork-Umgebung ohne Zugangsdaten, fehlendes Repository, wechselnde Sicherheitsprüfung).
Wochentag: `TZ=Europe/Berlin date +%u`, Tag im Monat: `TZ=Europe/Berlin date +%d`.

| Tag | Läufe in dieser Reihenfolge (Stand 13.10.2026) |
|---|---|
| am 1. des Monats (zusätzlich, zuerst) | Monats-Mix: `python monthly_mix.py` (siehe MONTHLY_ROUTINE_PROMPT.md) |
| Mo (1) | Italien: `python run_auto.py --genre "Italian Chillout"` |
| Di (2) | Winter-Cabin (2. Cabin-Mix der Woche): `python run_auto.py --genre "Cozy Winter Cabin"` (ca. 1–1,5 Std., ca. 8,90 $) |
| Mi (3) | Italien |
| Do (4) | **nur in geraden Kalenderwochen** (`TZ=Europe/Berlin date +%V` gerade): Gym `python run_auto.py --genre "Slow Gym Beats"`; sonst kein Lauf |
| Fr (5) | Italien (der Cabin-Freitags-Mix läuft in seiner eigenen Routine um 08:45) |
| Sa (6) | **Samstags-Mega-Mix** (seit 17.10.2026): `python run_megamix.py --genre all` (JEDEN Samstag ALLE Genres nacheinander: Italian, Lounge, zuletzt Cabin – je ein Mega-Mix; bis 8 Std., geplant öffentlich um 14:00; siehe Abschnitt „Samstags-Mega-Mix“). Ersetzt den bisherigen Italien-Wochen-Zusammenschnitt `run_weekly_compilation.py`. Ab ca. 11:04 gestartet, dauert je nach Genre 1–3 Std. |
| So (7) | Italien |

**Danach, als LETZTER Lauf des Tages (seit 15.10.2026, Wachstumsplan 2026/27):** ein Tipp-Short –
Mo, Di, Do, Sa: `python run_tip_short.py --kind wellness` · Mi, So: `python run_tip_short.py --kind dolcevita` · Fr: keiner.
Dauert ca. 3–5 Min, kostet ein Bild (ca. 0,04 $). Leere Warteschlange → endet sofort ohne Kosten (kurz melden).
Details im Abschnitt „Tipp-Shorts“ unten.

Pausiert seit 13.10.2026 (nicht starten, bis Rolf es wieder freigibt): Auto-Mix `python run_auto.py`, Ibiza
`--genre "Ibiza Sunset Lounge"`, Sonntags-Lang-Mix `python run_auto.py --long`.

Jeden Lauf im Hintergrund starten (`… > build/<name>.log 2>&1`), das Log verfolgen, bis er wirklich fertig ist, erst dann
den nächsten starten. Bricht ein Lauf ab: Ursache beheben, denselben Befehl einmal erneut starten (Konzept und fertige
Tracks werden wiederverwendet), danach mit dem nächsten Lauf des Tages weitermachen. Die Winter-Cabin-Linie hat eigene
Routinen (siehe unten).

## Was die Pipeline bewusst nicht tut (steht im Bericht als To-do für Rolf)

Kommentar anpinnen und Community-Beitrag posten (keine API), Endscreen setzen, DistroKid-Release anlegen (keine
API – alle Formularangaben stehen im Bericht).

## Sonntags-Lauf: Lang-Format (Sleep/Spa)

Die Sonntags-Routine startet statt `python run_auto.py` den Befehl **`python run_auto.py --long`**. Alles andere
(Gedächtnis, Kostenlimit, Upload öffentlich, 1 Short, Drive, Bericht per E-Mail) ist identisch. Unterschiede:
- Genre nur Chillout Sleep oder Dark Ambient Spa; Mindestlänge `LONG_MIN_MINUTES` (Standard 180 Min).
- Mehr Tracks (ca. 60–70), ein Cover-Bild je 4 Tracks, Zusammenschnitt in Batches, Video mit 10 fps.
- Der Lauf dauert deutlich länger (Lyria-Erzeugung der Tracks ca. 1–2 Stunden); bei Abbruch denselben Befehl erneut
  starten – fertige Tracks (build/<slug>/raw) und das Konzept des Tages werden wiederverwendet.
- Kein DistroKid-Release für Lang-Mixe (steht so im Bericht).

## Samstags-Mega-Mix (seit 17.10.2026, Rolf)

Konzept: `KONZEPT_SAMSTAG_MEGAMIX.md`. Befehl in der Tages-Routine am Samstag: **`nohup python run_megamix.py --genre all > build/megamix.log 2>&1 &`** (Rolf 17.10.: ein Mega-Mix pro Genre, nicht nur eines; ca. 4–5 Std. gesamt, 6 Shorts: je Mix eines für Samstag und eines für Sonntag)
(Log verfolgen, bis „fertig“; Dauer Italian/Lounge ca. 1 Std., Cabin ca. 2–3 Std.). Test ohne Kosten: `--dry-run`.
- **Genre-Rotation** (`pipeline/megamix.py`): Italian Chillout → Cozy Winter Cabin → Mediterranean Lounge (Lounge, Ibiza, Dark Spa
  zusammen; nur wenn mind. 4 Quell-Mixe der letzten 28 Tage da sind). Hat ein Genre zu wenig Material, kommt das nächste.
- **Musik**: nur vorhandene Songs aus den Genre-Mixen (Drive), Zufallsreihenfolge, **pro Mega-Mix kein Song doppelt**
  (gleicher Titel oder gleicher Dateiinhalt), nie zwei Songs desselben Albums direkt hintereinander, bis 8 Std. (Überblendung 1,5 s).
  Keine neue Musik, kein DistroKid.
- **Veröffentlichung geplant 14:00 Berlin** (`youtube.schedule_publish`); ist es später als 13:45, sofort öffentlich. Danach wartet
  das Skript auf „öffentlich“ und postet den Kommentar mit Trackliste (Kapitel in der Beschreibung höchstens ca. 60 Zeilen).
- **Italian/Lounge**: kein neues Video (atmendes Licht aus den vorhandenen Track-Covern), nur EIN Hauptbild (Nano Banana, ca. 0,24 $,
  outdoor) → Thumbnail mit großer Schrift + Album-Cover 3000×3000 + unbeschriftetes `master.jpg` in den Drive-Ordner.
- **Cozy Winter Cabin**: neues Hauptbild 4K + **2 neue Veo-Clips 4K** (ca. 5 $ gesamt), nahtlos wie bei den Cabin-Mixen,
  Streaming-Upload. **Seit 17.10.2026 schneit es in den Cabin-Videos nicht mehr** – nur ruhig liegender Schnee draußen, kein
  fallender Schnee, keine Flocken (Veo-Prompt, Negativ-Prompt, Bild-Prompt, Texte angepasst; Clip-Prüfung: relativer Sprung-Faktor 1,6).
- **Shorts**: 2 je Mega-Mix. Short 1 gehört zum **Samstag**, Short 2 zum **Sonntag** (Gedächtnis-Eintrag `shorts2` mit dem Datum
  des Tages, `megamix: true`, `mix_video_id` = Mega-Mix). Beide werden PRIVAT hochgeladen; die Abendaufgabe (19:45) setzt das
  „Related Video“ und schaltet öffentlich, Instagram/TikTok plant Metricool (liest dieselben Einträge).
  Cabin: Ausschnitte (Kamin bzw. Fenster/Sofa) aus dem neuen 4K-Material → normale Cabin-Short-Erstellung (S1 v2).
  Sonst: `run_short_v2.py --free-only --megamix --target-video-id <Mega-Mix> --audio <Auszug> --date <Tag>` (nur bezahlte Kling-Clips).
- **Tages-Short**: `run_short_v2.py` (ohne `--megamix`) überspringt den Tag, wenn für ihn schon ein Mega-Mix-Short existiert
  (je Tag nur EIN Eintrag, damit die Folgeaufgaben sie nicht verwechseln).
- Die Sonntags-Aufgabe „Cabin 2-Wochen-Mix“ (09:45) und der Monats-Mix bleiben unverändert.

## Winter-Cabin-Linie „Cozy Winter Cabin“ (seit 09.10.2026) – 4K-Kaminfilm

**Seit 13.10.2026 zwei Cabin-Mixe pro Woche** (Rolf): Freitag in der eigenen Routine (08:45) und Dienstag in der
Tages-Routine – gleicher Befehl, gleicher Ablauf.

Eigene Linie, alles **echtes 4K**, kein DistroKid. **Seit 17.10.2026: kein Schneien mehr im Video** (Rolf) – nur ruhig liegender Schnee draußen; gilt für alle Cabin-Clips und -Bilder. Konzept und Testergebnisse: `KONZEPT_WINTER_CABIN.md`.
- **Freitag 08:45** – Freitags-Mix (≥ 120 Min): **`python run_auto.py --genre "Cozy Winter Cabin"`** (im Hintergrund,
  Log `build/auto_cabin.log`). run_auto leitet an `run_cabin.py` weiter: Lyria-Tracks (Cozy Lofi Ambient / Smooth Jazz
  Fireplace, 58–64 BPM, −16 LUFS, keine Tempoprüfung), EIN Hauptbild 4K, 2 Veo-Clips 4K (seit 13.10.2026, vorher 3) (Start = Ende = Hauptbild,
  automatisch geprüft), nahtloser Kaminfilm mit gemeinfreiem Kaminknistern, **Streaming-Upload** (das Video liegt nie
  komplett auf der Platte), Thumbnail C, 1 Short S1 v2 (15-s-Loop mit Frage), Playlist „Cozy Winter Cabin · Relaxing
  Fireplace Chillout 4K“, Drive (MP3s, Hauptbild, Loop-Clips, Thumbnail, Metadaten, Shorts – nicht das lange Video),
  Gedächtnis, E-Mail. Dauer ca. 1–1,5 Std. Kosten ca. 8,90 $ (Grenze 15 $).
- **Sonntag 09:45 (alle 2 Wochen)** – **`python run_cabin_compilation.py --period biweekly --if-due`**: alle noch
  nicht verwendeten Cabin-Mixe der letzten 15 Tage (seit 13.10. Di + Fr, bis zu 4 → ca. 4–8 Std.) mit neuem Bild + neuem Film aus **2** Clips (Rolf 13.10.); nicht fällig → beendet sich sofort ohne Kosten.
- **Am 1. um 07:45** – **`python run_cabin_compilation.py --period monthly`**: alle Freitags-Mixe des Vormonats
  (ca. 8–10 Std., max. 11:50 Std.), neues Bild + neuer Film aus 2 Clips, Upload ca. 1 Std.
- Bei Abbruch denselben Befehl erneut starten (fertige Tracks, Hauptbild und geprüfte Clips werden wiederverwendet).
  Mit 2 Clips gibt es keine Reserve: ein durchgefallener Clip wird bis zu zweimal neu erzeugt; bleibt danach nur 1 Clip, bricht der Lauf ab (Fehler nennen).
- Nicht umbauen: Endbild-Vorgabe für Veo (ohne fährt die Kamera), Überblendung an den Nähten, `mbtree=0`, Streaming-Upload.

## Ibiza-Linie „Ibiza Sunset Lounge“ (seit 09.10.2026)

Eigene Linie neben den Di/Fr-Mixen, gleicher Ablauf wie oben (≥ 60 Min, 1 Short, sofort öffentlich, Drive, Gedächtnis,
Kostenvoranschlag, Bericht per E-Mail). Startbefehl: **`python run_auto.py --genre "Ibiza Sunset Lounge"`**
(im Hintergrund, Log `build/auto_ibiza.log`). Von Rolf nach drei Testrunden freigegeben (`test_ibiza.py`).
- Musik: klassischer Balearic Sunset Chillout (Café-del-Mar-Gefühl), 88–96 BPM, ruhiger Downtempo-Groove, Nylongitarre,
  Rhodes/Piano, Flächen, Meeresrauschen. Fast instrumental: nur selten ein wortloses, gehauchtes Summen weit im
  Hintergrund (`config.VOCAL_STYLE`), **nie Liedtext**. Den Markennamen „Café del Mar“ nie in Lyria-Prompts schreiben
  (Lyria filtert Anlehnungen an bestehende Werke).
- Bilder: Beach Club bzw. Sunset-Bar auf Ibiza mit Gästen, tiefer roter Sonnenuntergang, dunklere Umgebung;
  kinematografischer Orange-&-Teal-Filter auf ALLEN Bildern (`config.COLOR_GRADE`).
- Thumbnail und Album-Cover: „IBIZA SUNSET LOUNGE“ einzeilig, Unterzeile „BALEARIC CHILLOUT“, Albumname in Schreibschrift –
  Titelblock oben im Himmel; auf dem Thumbnail steht die Dauer unten rechts auf Höhe von „AIX WALKER“.
- Playlist „Ibiza Sunset Lounge“: wird beim ersten Upload über den Titel gefunden bzw. angelegt.
- Ibiza-Mixe zählen nicht für die Genre-Rotation der Di/Fr/So-Mixe; eigener Monats-Mix am 1. (wie Italien).
- DistroKid-Angaben im Bericht: Hauptgenre Electronic, Nebengenre Chill Out, Sprache Instrumental.

## Italien-Linie „Italian Chillout Music“ (Mo/Mi/Fr/So, seit 08.10.2026)

Eigene Linie neben den Di/Fr-Mixen, gleicher Ablauf wie oben (≥ 60 Min, 1 Short, sofort öffentlich, Drive, Gedächtnis,
Kostenvoranschlag, Bericht per E-Mail). Startbefehl statt `python run_auto.py`:
**`python run_auto.py --genre "Italian Chillout"`** (im Hintergrund, Log `build/auto_italian.log`).
- Musik: Italian Riviera Chillout Lounge (Bossa, Nylongitarre, Mandoline, Piano, Filmmusik-Streicher, Meer/Zikaden,
  ohne Gesang), fünf Unterstile mit eigenem BPM-Bereich (68–100) – steuert der Planer (pipeline/planner.py).
- Bilder: Nano Banana wie bei den anderen Mixen, aber super-realistischer Foto-Stil (echtes Editorial-Shooting, nicht
  künstlich): immer eine attraktive, elegante Frau in passender Abendgarderobe, Sunset- und Dinner-Stimmung,
  Amalfiküste oder Comer See; Gesicht etwa ein Drittel von oben, damit der große Titel nur über dem Kleid liegt.
- Thumbnail und Album-Cover aus EINEM Hauptbild (wie gehabt), Schrift für Genre-Begriff und Albumname 1,2-fach größer.
- Farblook seit 09.10.2026 (Rolf): dunkler und wärmer – tiefer Sonnenuntergang, Kerzenlicht, dazu der Orange-&-Teal-Filter
  wie bei Ibiza, aber in der sanften Italien-Einstellung (Haut natürlich, weiße Tischdecken nicht türkis; `config.COLOR_GRADE`).
- Playlist „Italian Chillout Music“: wird beim ersten Upload über den Titel gefunden bzw. angelegt.
- Italien-Mixe zählen nicht für die Genre-Rotation der Di/Fr/So-Mixe. Freitags und sonntags laufen zwei Linien am selben
  Tag – das Konzept des Tages wird je Linie getrennt wiederverwendet, nicht vermischen.
- DistroKid-Angaben im Bericht: Hauptgenre Jazz, Nebengenre Easy Listening.
- **Samstags: mehrstündiger Italien-Wochen-Mix als ZUSAMMENSCHNITT** (Rolf 08.10.2026, kostenfrei bis auf die Bilder):
  `python run_weekly_compilation.py --genre "Italian Chillout"` – holt die Italien-Mixe der letzten 2 Wochen aus Drive
  (`DAYS_BACK = 13`, Rolf 16.10.2026), verbindet sie (ca. 6 Std., vorher ca. 3 Std.; später evtl. 3 Wochen ≈ 8 Std.), Video mit atmendem Licht aus deren Album-Covern, EIN neues Hauptbild für Cover + Thumbnail,
  öffentlich, Italien-Playlist, Kommentar, Drive-Ordner „<Datum> – WEEKEND …“, Gedächtnis (`weekly`), E-Mail.
  KEINE neue Musik (nie `run_auto.py --long` für Italien), kein DistroKid, keine Shorts.
- Monats-Mix (am 1.): Italien ist ein eigenes Themengebiet und bekommt automatisch einen eigenen Monats-Mix
  (Zusammenschnitt der Tages-Mixe, Video mit atmendem Licht, Italien-Motiv, kein DistroKid).

## Shorts 2.0 (seit 16.10.2026 live, von Rolf freigegeben – täglich als letzter Lauf der Tages-Routine)

Ersetzt die Tipp-Shorts (Stil von Rolf abgelehnt, seit 16.10.2026 pausiert). Ein Short = Personen-Bild → 15-s-Clip
am Stück (Kling 3.0 Standard, keine Zeitlupe) → Text in Kaushan Script, Wort für Wort → Schluss „Open full mix here · <Genre> ↓“ (Rolf 16.10.2026: keine Längen-/Zeitangaben in Shorts) → Musik aus dem neuesten Mix des Genres. Befehl in der Routine: `nohup python run_short_v2.py --free-only --private > build/short2.log 2>&1 &`
(`--free-only`: nur Einträge mit schon bezahltem Clip – neue, kostenpflichtige Shorts erst nach Rolfs Freigabe;
`--publish-at 16:00`: geplant öffentlich um 16 Uhr Berlin, laut Metricool die stärkste Zeit). Warteschlange in Drive `_memory/shorts2_queue.json` (`--list`, `--add datei.json`).
Die 10 freigegebenen Beispiele verwenden ihre schon bezahlten Clips (0 $); neue Einträge ca. 1,40 $, A/B ca. 2,80 $,
harte Grenze 3,50 $ je Lauf. Öffentlich, KI-gekennzeichnet, Kategorie Musik. Danach in Studio als „Related Video“
den Ziel-Mix setzen (steht in metadata.txt; Beschreibungslinks sind in Shorts nicht klickbar).
Das Short-Video in Drive (`_shorts2/<Datum> – <id>/Short2_<id>.mp4`) wird beim Hochladen automatisch für „Jeder mit dem
Link“ (Betrachter) freigegeben (`drive.make_public`, Rolf 16.10.2026) – Metricool holt es so für Instagram/TikTok ab; die
metadata.txt bleibt privat.

## Tipp-Shorts „Sleep & Relax Tips“ und „Dolce Vita“ (seit 15.10.2026, Wachstumsplan 2026/27)

**PAUSIERT seit 16.10.2026** (Rolf: Stil abgelehnt) – ersetzt durch „Shorts 2.0“ oben. `run_tip_short.py` nicht starten.

Ziel: mehr Zuschauer in die langen Mixe bringen (Wiedergabestunden fürs Partnerprogramm). Rolf will das **autark, ohne
Rückfragen**. Plan-Dokument: „Aix Walker – Wachstums- und Einnahmenplan 2026/27“ (Claude Docs).
- Skript: `python run_tip_short.py --kind wellness|dolcevita` – nimmt den nächsten offenen Eintrag aus der Warteschlange
  `AIX WALKER Mixe/_memory/tip_queue.json` (beim ersten Lauf aus `tips/seed.json` angelegt), holt einen Track aus dem
  neuesten Mix des Eintrags-Genres (Drive), erzeugt EIN 9:16-Bild (Nano Banana, Bildstil des Genres), rendert 25 s im
  modernen Short-Look (Rolf 15.10.2026: Label-Chip, Hook in Montserrat Black mit Kontur + goldenem Schlüsselwort, Tipp-Zeilen
  als weiße Boxen, die nacheinander einblenden, langsamer Zoom, Knopf „FULL MIX · LINK BELOW“), lädt ihn **öffentlich mit
  KI-Kennzeichnung** hoch (Beschreibung: Tipp, Link zum Mix, Quellen, Hinweis „not medical advice“), legt ihn in Drive
  unter `AIX WALKER Mixe/_tip_shorts/<Datum – id>` ab und schreibt `tip_shorts` ins Gedächtnis. Kein E-Mail-Bericht
  (Rolf will keine Mail-Flut) – Abschluss im Chat der Tages-Routine.
- Probelauf ohne Kosten: `python run_tip_short.py --kind wellness --dry-run`. Warteschlange ansehen: `--list`.
- Regeln: keine Heilversprechen, keine Medikamente, nur allgemeine Wellness mit seriöser Quelle (NHS, Sleep Foundation,
  AASM, CDC …); Orte nur mit echten, belegten Fakten (z. B. Wikipedia), KI-Stimmungsbilder ohne echte Hotel-/Markennamen.
  Text im Bild Englisch, je Zeile höchstens 46 Zeichen (`tipshorts.validate_entry` prüft das).
- Nachschub: Routine „AIX WALKER Tipp-Recherche (So)“ recherchiert sonntags 4 Wellness-Tipps + 2 Orte mit Websuche,
  schreibt sie als JSON und hängt sie mit `python run_tip_short.py --add <datei.json>` an (ungültige/doppelte Einträge
  werden übersprungen).
