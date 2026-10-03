# Einrichtungsplan „Kids-Shorts täglich 16:00“ (für die Sitzung in der AixWalker-Umgebung)

Rolf startet in der Umgebung **AixWalker** einen neuen Chat mit: **„Los geht's mit dem Kids-Shorts-Plan“**.
Claude liest dann diese Datei und arbeitet die Schritte der Reihe nach ab. Antworten auf Deutsch, **alle
Anweisungen an Rolf in Anfänger-Sprache** (jeder Klick benannt, kein Fachjargon, nichts voraussetzen).

Vereinbart mit Rolf am 03.10.2026:
- eigener **Kids-Kanal** im selben Google-Konto (Aix Walker bleibt Gym-Musik)
- Budget **10 $ pro Tag** (Veo 3.1 Standard, 1 Neuversuch), harte Grenze im Skript
- Metadaten **nur Englisch**, Look wie das Referenz-Short „Dancing baby duck“ (Pixar-3D, Pastell, Bokeh)
- täglich **16:00 Uhr Berlin öffentlich**, danach **E-Mail an rolf.korr@gmail.com**
- erst alles testen (inkl. Test-Upload), Tests wieder löschen, dann die tägliche Aufgabe anlegen

## Schritt 0 – Umgebung prüfen (ohne Rolf)

```bash
cd aixwalker-pipeline && git pull
which ffmpeg || (sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg)
pip install -q -r requirements.txt --break-system-packages
env | grep -E '^(GOOGLE_API_KEY|YT_CLIENT_ID|YT_CLIENT_SECRET|YT_REFRESH_TOKEN|DRIVE_REFRESH_TOKEN|KIDS_YT_REFRESH_TOKEN|GMAIL_REFRESH_TOKEN)=' | sed 's/=.*/=gesetzt/'
python run_kids_short.py --dry-run --out build/kids/dry
```
Der Trockenlauf muss `Short fertig … (15.00 s)` melden (keine API-Kosten).

## Schritt 1 – Veo prüfen (ohne Rolf, ca. 3,30 $)

Erzeuge **einen** Testclip, um Modellfreischaltung und API-Form zu prüfen:
```bash
python - <<'EOF'
from pathlib import Path
from PIL import Image
from kids import costs, veo, gemini, story, config
import json
costs.start(Path("build/kids/veotest/costs.json"))
st = json.loads(Path("kids/example_story.json").read_text())
kf = gemini.image(story.keyframe_prompt(st, 0), aspect="9:16", out=Path("build/kids/veotest/kf1.png"))
veo.generate_clip(story.veo_prompt(st, 0), Path("build/kids/veotest/clip.mp4"), first_frame=kf)
print("Modell:", veo.current_model(), costs.report())
EOF
```
- Schlägt es mit 404/403 fehl: Veo ist im Projekt nicht freigeschaltet → Rolf in Anfängersprache anleiten
  (Google AI Studio öffnen, Projekt „Bodydashboard“, Veo-Modelle sind im bezahlten Tarif automatisch aktiv; sonst
  Cloud-Console → „Vertex AI API“ aktivieren). Danach erneut.
- Schlägt es mit 400 fehl: Anfrageformat anpassen (`kids/veo.py` `_start`; Doku ai.google.dev/gemini-api/docs/video
  per WebFetch lesen), bis ein Clip kommt. Modellnamen ggf. über `KIDS_VEO_MODELS` setzen.
- Preise prüfen: ai.google.dev/gemini-api/docs/pricing per WebFetch; weichen sie von `kids/config.py PRICES_USD` ab,
  dort anpassen und committen.
- Clip mit `Read` auf `build/kids/veotest/clip.mp4`-Frames (`python -c "from kids import render; from pathlib import Path; render.contact_sheet(Path('build/kids/veotest/clip.mp4'), Path('build/kids/veotest/cs.jpg'))"`) sichten: Look passend? Sonst `STYLE_BIBLE` in `kids/config.py` nachschärfen.

## Schritt 2 – Kids-Kanal anlegen und freigeben (mit Rolf, ca. 5 Minuten)

Erkläre Rolf Schritt für Schritt (Anfänger):
1. Im Browser **youtube.com** öffnen, oben rechts auf das runde Profilbild klicken → „Konto wechseln“ →
   „Alle Kanäle anzeigen oder neuen Kanal erstellen“ → „Kanal erstellen“.
2. Kanalname eingeben (Vorschlag: **Tiny Tales** – oder ein eigener Name; Claude schlägt 3 Namen vor, Rolf wählt)
   → „Erstellen“. Danach einmal auf den neuen Kanal wechseln, damit er aktiv ist.
3. Claude führt `python auth_youtube.py url kids` aus und schickt Rolf den Link mit dem Hinweis: Link öffnen,
   **im Google-Dialog den neuen Kids-Kanal auswählen** (nicht AIX WALKER), bei „Google hat diese App nicht
   überprüft“ auf „Erweitert“ und dann „Zu AixWalker Uploader (unsicher)“ klicken, alle Häkchen setzen,
   „Weiter“. Es erscheint eine Fehlerseite „Seite nicht erreichbar“ – das ist richtig. Rolf kopiert die komplette
   Adresse aus der Adressleiste (beginnt mit `http://localhost:1/?...`) und schickt sie Claude.
4. Claude führt `python auth_youtube.py token kids "<Adresse>"` aus → Zeile `KIDS_YT_REFRESH_TOKEN=...`.
   Rolf trägt sie als Umgebungsvariable der **AixWalker-Umgebung** ein (Anleitung: in Claude links die Umgebung
   AixWalker öffnen → Einstellungen/Umgebungsvariablen → „Hinzufügen“ → Name `KIDS_YT_REFRESH_TOKEN`, Wert einfügen
   → speichern). Dann **neue Sitzung** starten, damit die Variable gilt; weiter mit Schritt 3.
5. Kontrolle: `python -m kids.youtube` muss den **Kids-Kanal** zeigen.

Kanal-Grundeinstellungen (Rolf, in YouTube Studio → Einstellungen → Kanal → Erweiterte Einstellungen):
„Ja, diesen Kanal als für Kinder bestimmt festlegen“ wählen. Claude erklärt, warum (COPPA, Pflicht bei
Kinder-Inhalten; Folge: keine personalisierte Werbung, keine Kommentare).

Gmail-Fallback (optional, aber empfohlen – dann klappt die Mail auch ohne Connector):
`python auth_youtube.py url gmail` → gleicher Ablauf, Konto rolf.korr@gmail.com, Häkchen „E-Mails senden“ →
`python auth_youtube.py token gmail "<Adresse>"` → `GMAIL_REFRESH_TOKEN` eintragen.

## Schritt 3 – Kompletter Testlauf (ohne Rolf, ca. 7–10 $)

```bash
python run_kids_short.py --upload --private --out build/kids/test1 2>&1 | tee build/kids/test1.log
```
Dann prüfen:
1. `result.json`: `status: ok`, `url` vorhanden, `privacy: private`, Kosten plausibel.
2. `contact_sheet.jpg` und `thumbnail.jpg` mit `Read` sichten (Figur konsistent? kein Text? süß? Loop-Ende?).
3. YouTube: `python -c "from kids import youtube as y; print(y.status('<id>'))"` → `selfDeclaredMadeForKids: true`,
   `privacyStatus: private`, Titel/Beschreibung korrekt.
4. Rolf den Link + Prüfbild schicken (SendUserMessage/SendUserFile) mit: „Bitte einmal anschauen (privat, nur du
   siehst es). Passt der Look? Antworte mit ‚passt‘ oder sag, was anders sein soll.“ **Warte** auf die Antwort.
   Änderungswünsche → `STYLE_BIBLE`/Prompts anpassen, Schritt 3 wiederholen (max. 2×, Budget beachten).
5. Nach „passt“: Testvideo(s) löschen: `python -c "from kids import youtube as y; y.delete('<id>')"`, bestätigen
   mit `y.status('<id>')` → leer.

## Schritt 4 – E-Mail-Weg testen (ohne Rolf)

Sende eine Testmail an rolf.korr@gmail.com („[Kids-Short] Test – Mailweg funktioniert“) über
`mcp__Gmail__send_message`; ist das Tool nicht da, über `kids.mail.send` (GMAIL_REFRESH_TOKEN). Rolf kurz fragen,
ob sie angekommen ist. Notiere, welcher Weg funktioniert hat, in `KIDS_ROUTINE_PROMPT.md` Schritt 5 (den
funktionierenden Weg als „bevorzugt“ eintragen) und committe.

## Schritt 5 – Tägliche Aufgabe anlegen (ohne Rolf)

Mit `mcp__claude-code-remote__create_trigger` (Repo ist als Projekt hinterlegt):
- `name`: `Kids-Short täglich 16:00`
- `cron_expression`: `CRON_TZ=Europe/Berlin 25 15 * * *` (Start 15:25, damit der Short pünktlich um 16:00 geplant
  online geht; Laufzeit 10–25 Minuten plus Warten bis 16:01)
- `prompt`: „Antworte auf Deutsch. Das Arbeitsverzeichnis ist Rolfs Repository rkorr-de/aixwalker-pipeline. Führe
  zuerst `git pull` aus, lies dann KIDS_ROUTINE_PROMPT.md (Read) und führe die Routine ‚Kids-Short täglich 16:00‘
  vollständig aus – Schritt 1 bis 5 in dieser Reihenfolge, ohne Rückfragen. Ziel: ein neuer 15-Sekunden-Kids-Short,
  um 16:00 Uhr Berlin öffentlich auf dem Kids-Kanal, danach E-Mail an rolf.korr@gmail.com.“
- `initiation`: `human_request`; `notifications`: `{push: true, email: false}` (die eigentliche Mail kommt aus der
  Routine); `requires_local_device` NICHT setzen (läuft komplett in der Cloud).
- Prüfe im Ergebnis `derived_state.permission_mode`: steht da nicht `auto`, Rolf anleiten, in der Aufgabe
  „Automatisch genehmigen“ einzuschalten (Anfängersprache: Claude → Aufgaben → „Kids-Short täglich 16:00“ →
  Einstellungen → Schalter „Automatisch genehmigen“ an). Ohne das bleibt der Lauf nachts stehen.
- Gmail-Connector muss der Aufgabe zugeordnet sein (wie bei „YT-Stats für Morgenbriefing“). Ist das nicht
  automatisch der Fall, ist der GMAIL_REFRESH_TOKEN-Weg aus Schritt 2 Pflicht.

Zur Kontrolle einmal **sofort auslösen** (`mcp__claude-code-remote__fire_trigger`) – das ist der echte erste Lauf
(wird öffentlich; ist es nach 16:00 Uhr, veröffentlicht `--publish-local 16:00` in 2 Minuten). Danach Rolf
berichten: Link, Kosten, nächste Laufzeit, und was er sonntags noch tun sollte (nichts – nur die Mail lesen).

## Schritt 6 – Abschluss

- Alle Änderungen committen und pushen (`git add -A && git commit -m "kids: Einrichtung abgeschlossen" && git push`).
- Rolf eine Zusammenfassung in Anfängersprache geben: was täglich passiert, wo er den Kanal sieht, wie er die
  Aufgabe pausiert (Claude → Aufgaben → Schalter aus), wie er das Budget ändert (Umgebungsvariable
  `KIDS_BUDGET_USD`), was die Fehlermail bedeutet.

## Technische Notizen

- Veo-API: `models/<veo>:predictLongRunning` mit `instances[{prompt,image}]`, `parameters{aspectRatio:"9:16",
  durationSeconds:8, resolution, negativePrompt, referenceImages}`; Polling über `operations/...`; Download der
  `video.uri` mit API-Key. Alles in `kids/veo.py`, Modelle über `KIDS_VEO_MODELS` (Komma-Liste, Standard zuerst).
- Loop: Clip 2 startet mit dem letzten Bild von Clip 1 und bekommt Keyframe 1 als `lastFrame`, damit das Ende zum
  Anfang passt (Veo 3.1). Unterstützt das Modell `lastFrame` nicht, läuft es automatisch ohne.
- „Für Kinder“: `selfDeclaredMadeForKids: true` beim Upload (Pflicht). `defaultAudioLanguage: zxx` = keine Sprache.
- Budget: `kids/costs.py` prüft **vor** jedem kostenpflichtigen Aufruf; Exit-Code 2 = Budget erreicht, kein Upload.
- Themenvielfalt: `kids/story.py` liest die bisherigen Upload-Titel und meidet Wiederholungen; `THEME_POOL` in
  `kids/config.py` kann jederzeit erweitert werden.
