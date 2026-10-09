# Konzept: Linie „Cozy Winter Cabin“ – Stand 09.10.2026 (v3, nach Rolfs zweiter Antwort)

Grundlage ist die Ibiza-Linie (Gedächtnis → Planer → Konzept → Lyria → Mastering → Upload öffentlich → Drive →
Gedächtnis → Bericht per E-Mail). Neu: bewegter **4K-Kaminfilm** statt Standbild, Mixe **≥ 120 Min**, **kein DistroKid**.

## 1. Rolfs Entscheidungen (09.10.2026)

| Thema | Entscheidung |
|---|---|
| DistroKid | **entfällt** für diese Linie → kein Album-Cover, keine Song-Cover, keine DistroKid-Angaben im Bericht |
| Thumbnail | „**COZY WINTER CABIN**“, darunter „**RELAXING FIREPLACE CHILLOUT**“, **4K-Logo**; darf anders aussehen als die bisherigen Mixe – Vorschläge siehe 3 |
| Video | **4K** (3840 × 2160) |
| Shorts | Genre als Titel, modern, viral – Vorschläge siehe 4 |
| Kaminknistern | ja, kostenlos (siehe 5) |
| Drive | nur die Dateien, die das Projekt braucht – **nicht** die langen Videos |
| Wochen-/Monats-Mix | jeweils **neues Bild + neues Kaminvideo** |
| Tage (v3, wegen Kosten) | **nur Freitag** ein Tages-Mix (≥ 120 Min), **alle 2 Wochen** ein 4-Std.-Mix (Zusammenschnitt der beiden Freitags-Mixe), **am 1.** der lange Monats-Mix (ca. 8 Std. aus allen Freitags-Mixen) – **alles echtes 4K** |
| Thumbnail (v3) | **Entwurf C**, Textblock **oben links** über den Fenstern, „4K UHD“-Etikett größer (Varianten 2/4/8 HOURS). Steht der Kamin im erzeugten Bild links, wird das Bild vor den Veo-Clips **gespiegelt** (Rolfs Idee, kostenlos) – Kamin immer rechts, Text immer links |
| Short (v3) | **S1 v2**: Frage-Haken + großes goldenes „4K UHD“-Etikett unten |
| Playlist (v3) | **Cozy Winter Cabin · Relaxing Fireplace Chillout 4K** |

## 2. Testlauf 09.10.2026 – Ergebnisse

- **Hauptbild** (Nano Banana Pro, 4K): 2 Varianten, Variante 1 gewählt (großer, heller Kamin, Panoramafenster mit
  Schneefall, Platz oben für Schrift).
- **4K-Video funktioniert**: Veo 3.1 Fast liefert echte 4K-Clips (3840 × 2160, 24 Bilder/s, 8 s) – Start- und Endbild
  = Hauptbild. Die Kamera steht absolut still, nur Feuer und Schnee bewegen sich.
  - **Ohne** Endbild-Vorgabe (Clip C) fährt Veo trotz Verbot langsam ins Bild und wird dunkler → Endbild-Vorgabe ist Pflicht.
  - Das große Veo-Modell (Clip D, doppelter Preis) ist messbar nur minimal ruhiger → wir nehmen **Veo Fast**.
- **Nahtlos (Rapport)**: Veo landet am Clip-Ende nur *fast* auf dem Startbild (Schneeflocken sitzen anders – ein harter
  Schnitt wäre ein Sprung 5-mal so stark wie ein normaler Bildwechsel). Lösung: Jede Naht wird über 0,5 s weich in den
  Anfang des nächsten Clips überblendet; zusätzlich eine Kodier-Einstellung (ohne „mbtree“), damit am Segmentanfang kein
  Schärfe-Ruck entsteht. **Gemessen: Die Nähte liegen jetzt im normalen Schwankungsbereich jedes gewöhnlichen
  Bildwechsels** (1,37 bei Nähten = 1,37 Maximum im normalen Bild).
- **Automatische Clip-Prüfung** (`pipeline/loopvideo.py: check_clip`): Kamera fest? Helligkeit stabil? Sprünge im
  Schnee? Stillstand am Anfang/Ende? → Clip C wurde korrekt abgelehnt, A/B/D bestanden. Eine KI-Sichtprüfung mit Gemini
  haben wir getestet und verworfen: Sie war widersprüchlich (mal „flüssig“, mal „Standbild“ beim selben Clip).
- **Rendern**: 11,5 Min 4K in ca. 3,5 Min (die Clips werden nur einmal kodiert, danach nur aneinandergehängt).
  Ein 2-Stunden-Mix braucht ca. 6–8 Min Renderzeit.
- **Größe/Upload**: ca. 15 Mbit/s → **ca. 13–14 GB je 2-Stunden-Video**. Upload gemessen mit 64 Mbit/s → ca. 30 Min bis
  YouTube. YouTube zeigt 4K erst nach einigen Stunden Verarbeitung (vorher HD) – normal.
- **Musik**: 4 Test-Songs mit deinem JSON-Prompt (Felt-Piano, 80er-Flächen, Besen, Kontrabass, Kamin, Wind), je ca. 3 Min,
  gemastert auf −16 LUFS (leiser, für den Hintergrund). Lyria hat einmal kurz blockiert und beim Neuversuch geliefert.
  Die Tempo-Messung liefert bei dieser ruhigen Musik keinen Wert → für diese Linie wird die Tempoprüfung abgeschaltet.

## 2b. Lange Dateien (4 Std. / 8 Std. in 4K) – Streaming-Upload (getestet 09.10.2026)

8 Std. in 4K sind ca. 55 GB, eine Sitzung hat aber nur ca. 27 GB frei. Lösung (`pipeline/streamupload.py`): Das Video wird
**nie komplett gespeichert**. ffmpeg hängt die fertigen Segmente und die Tonspur ohne Neuberechnung aneinander und
schreibt einen MKV-Strom, der in 64-MiB-Stücken direkt zu YouTube geht (Resumable Upload mit unbekannter Gesamtgröße,
automatisches Weitersenden nach Netzfehlern, Zugang wird zwischendurch erneuert). Auf der Festplatte liegen nur die
Segmente (ca. 15 MB je Clip-Paar) und die Tonspur als AAC (8 Std. ≈ 1,2 GB).

Echttest: 11,5-Min-4K-Kaminfilm privat gestreamt – 1,3 GB in 60 s (≈ 170 Mbit/s), YouTube hat ihn verarbeitet und als
**3840 × 2160, 24 Bilder/s, H.264, Länge 11:29** erkannt; danach gelöscht. Hochgerechnet: 4-Std.-Mix ≈ 27 GB ≈ 25 Min
Upload, 8-Std.-Mix ≈ 55 GB ≈ 45–90 Min Upload. YouTube erlaubt bis 12 Std. bzw. 256 GB je Video. Das Verfahren wird
für **alle** Cabin-Videos genutzt (auch 2 Std.).

## 3. Thumbnail-Vorschläge (4 Entwürfe im Drive-Testordner)

Recherche (Top-Videos der Nische, 14 Monate): Die erfolgreichsten Kamin-/Hütten-Videos verkaufen fast nur über das
**Bild** – warm-orange Kaminlicht gegen tiefblaue Schneenacht, viele Kerzen, große Fenster; Schrift wenn überhaupt elegant
(Serifenschrift + Schreibschrift). Unser Bild bekommt dafür einen eigenen Thumbnail-Look (Schatten aufgehellt, wärmer,
satter, leichtes Leuchten um Feuer und Kerzen, Vignette).

| Entwurf | Idee |
|---|---|
| **A – Kino** | große, edle Antiqua mittig über den Fenstern, Unterzeile gesperrt in Gold, 4K-Logo oben links, „2 HOURS“ unten rechts |
| **B – Milchglas** | modernes Milchglas-Feld mit fetter Schrift, „CABIN“ in Gold, 4K-Logo im Feld |
| **C – Streaming** | Netflix-Look: sehr große fette Schrift unten links, goldenes „4K UHD“-Etikett + „2 HOURS“ – auf dem Handy am besten lesbar |
| **D – Minimal** | Bild ist der Held, kleine edle Schrift oben, Unterzeile in Schreibschrift, 4K-Logo oben rechts |

**Empfehlung:** A als Standard. C als Gegenvariante: YouTube Studio kann bis zu 3 Thumbnails gegeneinander testen
(„Test & Compare“, nur von Hand in Studio – nicht per Schnittstelle).

## 4. Shorts-Vorschläge (3 Entwürfe + 1 fertiger Test-Short)

Recherche: Die viralen Shorts der Nische (61 Mio., 52 Mio., 34 Mio. Aufrufe) sind **8–11 Sekunden** kurze, endlos
laufende KI-Clips einer gemütlichen Hütte mit Schnee und Kamin – oft mit einer **Frage** als Haken („Would You Stay
Here?“). Kurze nahtlose Loops werden mehrfach angeschaut → der Algorithmus pusht sie. Genau das können wir: Unsere
Clips sind nahtlos.

| Entwurf | Idee |
|---|---|
| **S1 – Frage** | oben groß „COZY WINTER / CABIN“, darunter weiße Frage-Pille „Would you stay here tonight?“, unten klein „4K · RELAXING FIREPLACE CHILLOUT“ |
| **S2 – POV** | Titel in edler Antiqua, darunter TikTok-Untertitelstil „POV: it's -20° outside and you finally have nowhere to be“, unten „turn the sound on“ |
| **S3 – Glas** | Milchglas-Karte unten mit Titel + goldener Pille „save this for tonight“, oben „4K · 2 HOURS ON THE CHANNEL“ |

**Empfehlung:** S1 (bewährter Frage-Haken). Je Tages-Mix 2 Shorts à **15 s** als nahtlose Schleife (senkrechter 4K-
Ausschnitt mit Kamin + Fenster), Musik-Ausschnitt mit Knistern, wechselnde Fragen je Short (z. B. „Would you stay here
tonight?“, „Rate this cabin 1–10“, „Could you sleep here?“, „Where would you sit first?“). Titel: Genre + Frage +
Emojis, z. B. „Cozy Winter Cabin ❄️🔥 Would You Stay Here Tonight?“, Link zum langen Mix in der Beschreibung.

## 5. Kaminknistern (kostenlos, ohne YouTube-Audiomediathek)

Die YouTube-Audiomediathek hat keine Schnittstelle (nur von Hand in Studio). Stattdessen: zwei **gemeinfreie**
Aufnahmen aus dem Internet Archive – „Fire Favorite“ (CC0, 4:22 Min) und ein ruhiger Abschnitt einer Litauen-Aufnahme
(Public Domain Mark). Von Gemini angehört: keine Stimmen, Tiere oder Störgeräusche (10/10). Zusammengefügt zu einer
**nahtlosen 5:12-Min-Schleife** (`assets/ambience/fireplace_crackle_loop.m4a`), die durchgehend ca. 14 dB unter der
Musik liegt. Keine Namensnennung nötig, kein Content-ID-Risiko.

## 6. Playlist-Name – Vorschläge

Recherche: „Cozy Winter Cabin Ambience“ heißt bereits ein gutes Dutzend Playlists anderer Kanäle.

1. **Cozy Winter Cabin · Relaxing Fireplace Chillout 4K** – gleicher Wortlaut wie das Thumbnail (Wiedererkennung) + Suchbegriffe (Empfehlung)
2. Cozy Winter Cabin Ambience 4K – Fireplace & Snowfall – exakter Nischen-Suchbegriff
3. Winter Cabin Nights – Fireplace Chillout & Snow – eigener, markenartiger Name
4. Snowed In – Cozy Cabin Fireplace Music – emotional, kurz

## 7. Ablauf je Lauf (neu)

1. Planer: Konzept (Albumname, Songtitel, Variationen, Bildidee – Kern immer: Luxus-Blockhütte in Montana, Kamin, Panoramafenster, Schneenacht).
2. Lyria: ca. 40–45 Songs bis ≥ 120 Min (ohne Tempoprüfung), Mastering −16 LUFS, 1,5 s Überblendung.
3. Hauptbild 4K (Nano Banana Pro) → 16:9 → **3 Veo-Clips** (4K, Start = Ende = Hauptbild) → Prüfung je Clip, ein Neuversuch je durchgefallenem Clip.
4. Ton: Musik + Knister-Schleife. Video: Kaminfilm aus den 3 Clips in Zufallsfolge, 3 s Ein-/Ausblenden, AAC 320k.
5. Thumbnail (Entwurf nach Rolfs Wahl) mit „2 HOURS“ und 4K-Logo; 2 Shorts (Entwurf nach Wahl).
6. Upload öffentlich (Video + Shorts), Playlist, Kommentar, KI-Label.
7. Drive „AIX WALKER Mixe/<Datum> – <Album> (Cozy Winter Cabin)“: MP3s (für Wochen-/Monats-Zusammenschnitt), Hauptbild,
   3 Loop-Clips (je ca. 30 MB – daraus lässt sich das Video jederzeit neu bauen), Thumbnail, Metadaten, Shorts.
   **Nicht**: das 13-GB-Video.
8. Gedächtnis, Bericht per E-Mail (ohne DistroKid-Teil).

Wochen-Mix (So): Zusammenschnitt Fr + Sa (ca. 4 Std., ca. 27 GB in 4K, Upload ca. 1 Std.), neues Hauptbild + 3 neue
Clips. Monats-Mix (1.): wie gehabt aus den Tages-Mixen des Vormonats, neues Bild + Clips.

## 8. Kosten (4K, Zeitplan v3)

| Posten | Freitags-Mix (2 Std.) | 2-Wochen-Mix (4 Std.) | Monats-Mix (8 Std.) |
|---|---|---|---|
| Lyria ca. 45 Songs × 0,08 $ | 3,60 $ | – (Zusammenschnitt) | – (Zusammenschnitt) |
| Hauptbild 4K | 0,24 $ | 0,24 $ | 0,24 $ |
| 3 Veo-Clips 4K (8 s × 0,30 $) | 7,20 $ | 7,20 $ | 7,20 $ |
| Texte | ca. 0,30 $ | ca. 0,10 $ | ca. 0,10 $ |
| **Summe** | **ca. 11,30 $** | **ca. 7,50 $** | **ca. 7,50 $** |
| je Monat | × 4,3 = ca. 49 $ | × 2,2 = ca. 16 $ | ca. 7,50 $ |

**Gesamt ca. 73 $ ≈ 67 € im Monat** (+ ggf. 2,40 $ je neu erzeugtem Clip, wenn einer die Prüfung nicht besteht).

## 8b. Prognose: Holen wir die Kosten über die Monetarisierung wieder rein?

Kanalstand 09.10.2026: 2.960 Abos (Hürde 1.000 ✔), 131.611 Aufrufe, aber nur **384 öffentliche Wiedergabestunden in 12
Monaten** – fürs Partnerprogramm (YPP) braucht es **4.000** (oder alternativ 10 Mio. Shorts-Aufrufe in 90 Tagen).

**Warum diese Linie gute Chancen hat:** Lange Kaminvideos sind ideal für Wiedergabestunden (wer 1 Std. laufen lässt, bringt
1 Std.). In der Recherche erreichen kleine Kanäle (3.000–6.000 Abos) mit genau diesem Thema 0,8–4,3 Mio. Aufrufe pro
Video, und die Hochsaison (Nov.–Feb.) beginnt jetzt. Die viralen Kamin-Shorts der Nische (34–61 Mio.) zeigen, dass auch
der Shorts-Weg ins YPP möglich ist.

**Annahmen:** Einnahmen nach YPP ca. **1,50–3 $ je 1.000 Aufrufe** (Entspannungs-/Ambient-Musik, viel US-Publikum),
durchschnittlich ca. 20–25 Min Sehdauer je Aufruf. Shorts bringen kaum Geld (Cent-Beträge je 1.000), aber Reichweite.
Gewinnschwelle 73 $/Monat ≈ **25.000–50.000 Aufrufe im Monat** über alle Cabin-Videos.

| Szenario | Aufrufe je Video | YPP erreicht | Einnahmen in der Saison | Bilanz |
|---|---|---|---|---|
| Vorsichtig | 200–500 | frühestens nächster Winter | 0 $ bis dahin | reine Investition (ca. 70 $/Monat) → Abbruchregel nötig |
| Mittel | 2.000–5.000 (summiert sich, alte Videos laufen weiter) | ca. Dez./Jan. | ca. 50–200 $/Monat | übers Jahr etwa ±0, im Winter Plus, im Sommer Minus |
| Gut | ein Video „zündet“ (100.000+) | in wenigen Wochen | 500–3.000 $/Monat | Kosten nach 1–2 Monaten wieder drin |

**Ehrlich dazu:** Das sind Schätzungen, keine Zusage. Die meisten Kanäle bleiben im vorsichtigen Szenario; die Nische ist
aber nachweislich stark und saisonal günstig. Zwei Risiken: (1) YouTube prüft bei der YPP-Aufnahme auf „massenhaft
produzierte, sich wiederholende“ Inhalte – unsere eigene Musik je Video, wechselnde Szenen und kuratierte Titel sprechen
dagegen, eine Garantie gibt es nicht. (2) Saisonalität: Im Frühjahr/Sommer sinkt das Interesse an Winterhütten –
dann auf Varianten wechseln (Regen-Hütte, Herbst, Berg-Chalet), gleiche Technik.

**Vorschlag Abbruchregel:** Ende Januar prüfen – hat die Cabin-Linie bis dahin weniger als ca. 1.500 Wiedergabestunden
gebracht, Takt reduzieren (nur Monats-Mix) oder pausieren.

## 9. Was noch zu bauen ist (nach Rolfs Freigabe)

- Planer-Eintrag „Cozy Winter Cabin“ (Musikstil, BPM 58–64, Stimmungen, Bild-Varianten), Konfiguration (Playlist,
  −16 LUFS, ≥ 120 Min, Kostengrenze 15 $, keine Tempoprüfung, keine Cover).
- `run_mix.py`: Zweig für diese Linie (Kaminfilm statt atmendem Licht, Thumbnail-Entwurf, Loop-Shorts, Drive ohne Video).
- `pipeline/loopvideo.py` (steht schon: Veo-Clips, Prüfung, nahtloser Zusammenbau, Knistern).
- Wochen-Mix (`run_weekly_compilation.py`) und Monats-Mix (`monthly_mix.py`) für die Linie mit Kaminfilm.
- Bericht per E-Mail ohne DistroKid, Kosten mit Veo-Posten.
- Routinen: „Winter-Cabin-Mix (Fr/Sa)“ und „Winter-Cabin-Wochen-Mix (So)“; Monats-Mix nimmt die Linie automatisch mit.
- `pipeline/streamupload.py` (steht schon, getestet).
- Erster echter Lauf: Freitag, 16.10.2026.

## 10. Stand 09.10.2026 abends

- Erster Freitags-Mix „Cabin Embers“ läuft (heute). Routinen angelegt: Fr 08:45, So 09:45 (2-Wochen-Mix, nur wenn
  fällig – erster am 18.10.), am 1. um 07:45 (Monats-Mix, erster am 01.11.).
