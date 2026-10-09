# Konzept: neue Linie „Cozy Winter Cabin Ambience“ (Stand 09.10.2026, zur Durchsicht für Rolf)

Grundlage ist die Ibiza-Linie (gleiche Pipeline: Gedächtnis → Planer → Konzept → Lyria → Mastering → Upload öffentlich →
Google Drive → Gedächtnis → Bericht per E-Mail). Neu sind vor allem **das Video** (bewegter Kaminfilm statt Standbild
mit atmendem Licht) und **die Länge** (mindestens 120 Minuten).

---

## 1. Auf einen Blick

| | Ibiza-Linie (heute) | Winter-Cabin-Linie (neu) |
|---|---|---|
| Tage | Di / Do / Sa | **Fr + Sa** (Tages-Mix), **So** (Wochen-Mix), **1. des Monats** (Monats-Mix) |
| Länge Tages-Mix | ≥ 60 Min | **≥ 120 Min** (ca. 40–45 Songs) |
| Musik | Balearic Chillout, 88–96 BPM | **Cozy Lofi Ambient / Smooth Jazz Fireplace**, ca. 58–64 BPM (dein JSON-Prompt) |
| Bilder | Hauptbild + je Song ein eigenes Cover | **ein** Hauptbild je Mix – keine Song-Cover mehr |
| Video | Standbild-Cover mit atmendem Licht, Logo | **Kaminfilm**: kurzer Video-Loop (Feuer, Kerzen, Schnee) nahtlos aneinandergereiht, **ohne Text, ohne Logo** |
| Thumbnail / Album-Cover | aus dem Hauptbild, mit Schrift | genauso – aus dem Hauptbild, mit Schrift |
| MP3s | mit Song-Cover | mit **Album-Cover** eingebettet (für DistroKid) |
| DistroKid, E-Mail, Drive, Gedächtnis | ja | ja, wie gehabt |

---

## 2. Das Video – der wichtigste Teil

### 2.1 Wie heißt das?
Bei einer Tapete heißt es Rapport – beim Video heißt es **„Seamless Loop“** (nahtlose Schleife, auch „Perfect Loop“).
Wenn das Bild fast ganz stillsteht und sich nur einzelne Stellen bewegen (Feuer, Kerzen, Schnee), nennt man das
zusätzlich **„Cinemagraph“**. Genau das bauen wir.

### 2.2 Ablauf je Mix
1. **Hauptbild erzeugen** (Nano Banana Pro, 4K, 16:9) mit deinem Bildprompt. Kleine Ergänzungen von mir:
   *keine Menschen, keine Tiere, keine lesbare Schrift auf den Zeitschriften* (KI malt sonst Buchstabensalat),
   *Feuer, Kerzen und Fenster gut sichtbar*, *statische Komposition*. Die Bildidee wechselt von Mix zu Mix leicht
   (Sofa, Decken, Blick auf Wald / Berge / zugefrorenen See, Tasse, Kerzen) – der Kern (Luxus-Blockhütte in Montana,
   Kamin, Panoramafenster, Schneenacht) bleibt immer gleich. Das steuert der Planer über das Gedächtnis.
2. **Aus dem Bild drei kurze Videos erzeugen** (Veo 3.1 Fast, je 8 Sekunden, 1080p, 16:9 – Veo läuft bei den
   Kids-Shorts schon in der Pipeline). Der Trick: Wir geben Veo **dasselbe Hauptbild als erstes UND als letztes Bild**
   vor. Dadurch beginnt und endet jedes Video exakt auf dem Hauptbild.
3. **Nahtlos-Sicherung** (kostenlos, ffmpeg): Damit es zu 100 % funktioniert, verlassen wir uns nicht nur auf Veo:
   - Das doppelte Bild an der Nahtstelle wird entfernt (sonst „stockt“ es kurz).
   - Die letzten ca. 0,5 s jedes Clips werden weich in das Hauptbild überblendet – so ist die Nahtstelle immer
     pixelgenau gleich, auch wenn Veo am Ende minimal abweicht.
   - Optional (Cinemagraph-Maske): Alles, was sich nicht bewegen soll (Balken, Sofa, Tisch, Wände), wird fest aus
     dem Hauptbild genommen; nur Kamin, Kerzen und Fensterflächen kommen aus dem Video. Dann kann sich außerhalb
     dieser Bereiche gar nichts verschieben.
4. **Automatische Prüfung jedes Clips**, bevor er verwendet wird:
   - Vergleich erstes Bild ↔ letztes Bild ↔ Hauptbild (Messwert, muss praktisch identisch sein).
   - Prüfung, dass die Kamera stillsteht (keine Verschiebung, kein Zoom, kein Helligkeitssprung).
   - KI-Sichtprüfung (wie bei den Kids-Shorts): Morphing, wandernde Gegenstände, Flackern im ganzen Bild?
   - Fällt ein Clip durch → einmal neu erzeugen. Fällt er wieder durch → nur die gültigen Clips verwenden.
5. **Hauptvideo zusammensetzen**: Die drei Clips werden in zufälliger Reihenfolge immer wieder hintereinandergelegt
   (A C B A B C …), bis die Musiklänge erreicht ist. Weil alle drei Clips auf demselben Bild beginnen und enden,
   gibt es nie einen sichtbaren Übergang – und weil es drei verschiedene sind, wiederholt sich das Feuer nicht alle
   8 Sekunden gleich (das würde ein aufmerksamer Zuschauer sonst nach ein paar Minuten bemerken).
   Technisch: Die Clips werden nur einmal sauber kodiert und dann ohne Neuberechnung aneinandergehängt →
   ein 2-Stunden-Video ist in wenigen Minuten fertig (heute dauert das Rendern ca. 7 Min je Stunde).
   Am Anfang und Ende je 3 Sekunden sanftes Ein-/Ausblenden aus Schwarz.

### 2.3 Video-Prompt (Entwurf, Englisch wie alle KI-Prompts)
> Static locked-off tripod shot of exactly this image, absolutely no camera movement, no zoom, no pan, no tilt.
> The room stays exactly as it is. Only three things move: the fire in the stone fireplace burns and flickers
> naturally, its warm golden light gently pulsing on the nearby stone and wood; the small candle flames on the coffee
> table flicker softly; outside the panoramic windows heavy snow falls continuously and steadily at a constant speed
> in front of the dark pine forest. Everything else is completely still: no people, no animals, no objects moving, no
> change of light or time of day, no new objects appearing. Calm, cozy, cinematic, photorealistic. The video starts and
> ends on exactly the same frame so it can loop seamlessly.
>
> Negativ: camera movement, zoom, pan, shake, people, hands, animals, text, letters, logo, morphing, flicker of the
> whole image, light change, objects moving or appearing.

### 2.4 Was im Video NICHT mehr vorkommt
Kein Titel, keine Schrift, kein Kanal-Logo, kein Fortschrittsstrich, kein atmendes Licht. Nur der Kaminfilm mit unserer
Musik. Die Song-Liste steht wie gewohnt als Kapitel in der Beschreibung.

---

## 3. Thumbnail und Album-Cover

- **Thumbnail** (16:9) = das Hauptbild + Schrift im bewährten Stil: groß „**COZY WINTER CABIN**“ (einzeilig), Unterzeile
  „**FIREPLACE & SMOOTH JAZZ**“, darunter der Albumname in Schreibschrift, Dauer („2 HOURS“) unten rechts,
  „AIX WALKER“ unten links. Titelblock oben (über den dunklen Holzbalken der Decke).
- **Album-Cover** (3000 × 3000) = **dasselbe Bild**, quadratisch. Weil das Hauptbild 16:9 ist und ein einfacher
  Ausschnitt Kamin oder Fenster abschneiden würde, lasse ich das Bild von Nano Banana oben (Deckenbalken) und unten
  (Teppich/Holzboden) **erweitern** – es bleibt dieselbe Szene, nur höher. Gleiche Schrift wie beim Thumbnail.
- Farblook: warmes Bernstein innen, kaltes Blau draußen (das liefert schon dein Prompt). Ich würde einen leichten
  Warm-/Kalt-Filter wie bei Ibiza einstellen, aber vorsichtig – das Bild darf nicht ins Künstliche kippen.

---

## 4. Musik

- Lyria 3.5 mit deinem JSON-Prompt, umgesetzt in die Pipeline-Felder:
  - Genre-Angabe: „Cozy Lofi Ambient, Smooth Jazz, Fireplace Ambience“
  - Klangidentität (für alle Songs gleich): gedämpftes Felt-Piano mit Tastengeräuschen, warme 80er-Analog-Flächen,
    Besen-Snare, träge Lofi-Kick, Kontrabass, Kaminknistern und gedämpfter Schneesturm, Tape-Sättigung, leichtes
    Vinylknistern, langer Hall wie unter einem hohen Holzdach. Instrumental, kein Gesang.
  - Je Song eine eigene Variation (andere Akkordfolge, mal mehr Piano, mal nur Flächen + Feuer, mal Bass-Solo …).
  - Den Aufbau aus deinem JSON (Intro nur Feuer + Fläche → Piano → breite Flächen → Bridge ohne Schlagzeug →
    Ausklang) gebe ich jedem Song als Bauplan mit. Lyria hält sich nicht immer exakt daran – die Stimmung trifft es.
- **Tempo** 58–64 BPM (je Mix leicht anders). Die bisherige Tempo-Prüfung ist für Ambient zu streng (bei kaum
  Schlagzeug misst sie oft Unsinn) → für diese Linie lockere ich sie, sonst gibt es unnötig viele Neuversuche.
- **Länge**: Lyria liefert ca. 3 Min je Song → 40 Songs + 8 Reserve, bis ≥ 120 Min erreicht sind. Die heutige
  Obergrenze von 40 Songs je Tages-Mix hebe ich für diese Linie an.
- **Lautstärke**: Dein Prompt sagt „leise, für den Hintergrund“. Ich empfehle −16 LUFS statt −14 LUFS
  (YouTube macht leise Videos nicht lauter – der Mix bleibt angenehm ruhig, wie bei den großen Kaminkanälen).
- Übergänge: wie gehabt 1,5 s Überblendung zwischen den Songs.

---

## 5. Zeitplan und Formate

| Tag | Was | Wie |
|---|---|---|
| **Freitag** | Tages-Mix ≥ 120 Min | neue Musik, neues Bild, neue Loops, öffentlich, Drive, DistroKid-Angaben, E-Mail |
| **Samstag** | Tages-Mix ≥ 120 Min | wie Freitag |
| **Sonntag** | Wochen-Mix ca. 4 Std. | **Zusammenschnitt** von Fr + Sa (keine neue Musik, wie der Italien-Wochen-Mix), neues Bild + neue Loops, kein DistroKid |
| **1. des Monats** | Monats-Mix 2–4 Std. | Zusammenschnitt aus den Tages-Mixen des Vormonats (läuft im bestehenden Monats-Mix mit), neues Bild + neue Loops, kein DistroKid |

- Uhrzeit-Vorschlag: Fr und Sa Start ca. 08:45 Uhr (Berlin), damit sich die Lyria-Erzeugung nicht mit Italien
  (11:04) und Ibiza (12:52) in die Quere kommt; Sonntag ca. 09:45 Uhr.
- Die Linie bekommt eine **eigene Playlist** „Cozy Winter Cabin Ambience“ (wird beim ersten Upload angelegt) und
  zählt – wie Italien und Ibiza – nicht in die normale Genre-Rotation.
- Timing ist gut: Winter-Kamin-Videos haben ihre stärkste Zeit von November bis Februar – wir starten genau davor.

---

## 6. Was ich einrichte (Technik)

1. **Genre-Eintrag** „Cozy Winter Cabin“ im Planer (`pipeline/planner.py`): Musikstil, BPM, Stimmungen, Bildmotiv-
   Varianten, Bildregeln; Eintrag in Konfiguration (`pipeline/config.py`): Thumbnail-Text, Unterzeile, Bildstil,
   Playlist, −16 LUFS, Mindestlänge 120 Min, Songs ohne eigenes Cover.
2. **Neues Modul `pipeline/loopvideo.py`**: Hauptbild → 3 Veo-Clips (erstes = letztes Bild) → Nahtlos-Sicherung →
   automatische Prüfung → Hauptvideo in beliebiger Länge. Nutzt den vorhandenen Veo-Baustein der Kids-Shorts.
3. **`run_mix.py`**: für diese Linie keine Song-Cover, MP3s mit Album-Cover, Video aus `loopvideo` statt atmendem
   Licht, Album-Cover per Bilderweiterung.
4. **Wochen-Mix** (`run_weekly_compilation.py`) und **Monats-Mix** (`monthly_mix.py`): Linie ergänzen; Video dort
   ebenfalls als Kaminfilm-Loop statt atmendem Licht.
5. **Kosten** (`pipeline/costs.py`): Veo-Preise ergänzen; Kostenobergrenze für diese Linie 12 $ statt 9 $.
6. **E-Mail-Bericht**: DistroKid-Angaben für diese Linie (siehe Frage 6), Hinweis „Video = Kaminfilm-Loop“.
7. **Routinen** (geplante Läufe): neu „Winter-Cabin-Mix (Fr/Sa)“ und „Winter-Cabin-Wochen-Mix (So)“; der Monats-Mix
   nimmt die Linie automatisch mit. Anleitung dazu in `ROUTINE_PROMPT.md`.
8. **Testlauf zuerst** (`test_cabin.py`, wie damals `test_ibiza.py`): 1 Hauptbild, Thumbnail, Album-Cover,
   3 Loop-Clips und ein ca. 10-minütiges Probevideo mit 3–4 Songs – **nicht öffentlich**, nur in Drive unter
   „_TEST Cozy Winter Cabin“. Du schaust es dir an, erst nach deiner Freigabe geht die Linie live.

---

## 7. Kosten (Schätzung je Lauf)

| Posten | Tages-Mix (Fr / Sa) | Wochen-Mix (So) | Monats-Mix |
|---|---|---|---|
| Musik: Lyria ca. 45 Songs × 0,08 $ | 3,60 $ | – | – |
| Hauptbild 4K + Album-Cover-Erweiterung | 0,48 $ | 0,48 $ | 0,48 $ |
| Video: 3 Veo-Clips × 8 s × 0,12 $ (+ ggf. 1 Neuversuch) | 2,88 $ (bis 3,84 $) | 2,88 $ | 2,88 $ |
| Texte (Planer, Prüfung) | ca. 0,30 $ | ca. 0,10 $ | ca. 0,10 $ |
| **Summe** | **ca. 7,30 $ (bis 8,30 $)** | **ca. 3,50 $** | **ca. 3,50 $** |

Gespart wird bei den Song-Covern (heute ca. 1,60 $ je 40 Songs). Pro Monat (ca. 9 Tages-Mixe, 4 Wochen-Mixe,
1 Monats-Mix) etwa **85 $ ≈ 78 €**. Testlauf vorab: ca. 4 $.

---

## 8. Risiken und wie ich sie abfange

| Risiko | Gegenmaßnahme |
|---|---|
| Veo bewegt doch die Kamera oder lässt Dinge „wandern“ | Prompt + Negativ-Prompt, automatische Prüfung, Neuversuch, Cinemagraph-Maske |
| Sichtbarer Sprung an der Nahtstelle | erstes = letztes Bild, doppeltes Bild entfernt, weiche Überblendung ins Hauptbild – pixelgenau |
| Feuer wirkt nach Minuten „wiederholt“ | 3 verschiedene Clips in Zufallsreihenfolge |
| Veo macht am Anfang/Ende eine kurze „Zeitlupe“ | wird in der Prüfung erkannt (Bewegungsmessung über den Clip); dann Clip neu oder nur Mittelteil + Überblendung |
| Riesige Videodatei (2 Std. Feuer + Schnee ≈ 4–5 GB) | Bitrate sinnvoll begrenzen; Ablage in Drive siehe Frage 3 |
| Lyria trifft 60 BPM nicht genau | Tempoprüfung für Ambient gelockert |
| Kauderwelsch-Schrift auf Zeitschriften im Bild | im Bildprompt ausgeschlossen („no readable text“) |

---

## 9. Offene Fragen an Rolf

1. **Shorts**: Sollen wie bisher 2 Shorts je Tages-Mix erscheinen? Vorschlag: ja, als senkrechter Ausschnitt aus dem
   Kaminfilm (Kamin + Fenster) mit 45 s Musik, nur mit dem Albumnamen klein unten (oder ganz ohne Text?).
2. **Durchgehendes Kaminknistern**: Lyria baut das Knistern in jeden Song ein, aber zwischen den Songs kann es kurz
   wechseln. Soll ich zusätzlich eine leise, durchgehende Kamin-Tonspur unter den ganzen Mix legen (wirkt mehr wie ein
   echter Kaminfilm)? Kosten einmalig ca. 0,20 $ (KI-Geräusch) oder kostenlos aus einer freien Aufnahme.
3. **Drive-Ablage des Videos**: Ein 2-Stunden-Kaminfilm hat ca. 4–5 GB. Vorschlag: in Drive nur die kleinen
   Loop-Clips + MP3s + Bilder ablegen (das Video lässt sich daraus jederzeit in Minuten neu bauen); das fertige Video
   liegt ja auf YouTube. Oder soll das große Video trotzdem jedes Mal in Drive?
4. **Wochen-/Monats-Mix-Bild**: Vorschlag: jeweils eine neue Hütten-Szene mit neuen Loops (ca. 3,40 $). Alternative
   kostenlos: das Kaminvideo vom Freitag weiterverwenden.
5. **Uhrzeit** der Veröffentlichung Fr/Sa/So – passt „vormittags“ (Start ca. 08:45, online ca. 10:30–11:00)?
6. **DistroKid-Genre**: Vorschlag Hauptgenre **Jazz**, Nebengenre **Easy Listening**, Sprache Instrumental
   (Alternative: Elektronisch / Chill Out wie die anderen Mixe). Mit 40–45 Songs je Album ist der DistroKid-Upload
   deutlich länger als bisher – ist das okay, oder lieber nur eine Auswahl (z. B. die 20 besten Songs) als Album?
7. **Thumbnail-Text**: „COZY WINTER CABIN“ + Unterzeile „FIREPLACE & SMOOTH JAZZ“ – einverstanden, oder lieber
   „COZY CABIN AMBIENCE“ / „WINTER FIREPLACE“?
