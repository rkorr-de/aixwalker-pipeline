# Social-Plan: Instagram & TikTok für Giggle Meadow (für die Sitzung in der AixWalker-Umgebung)

Rolf startet in Claude Code (Repo `rkorr-de/aixwalker-pipeline`, Umgebung **AixWalker**) einen Chat mit
**„Los geht's mit dem Social-Plan“**. Antworten auf Deutsch, Anweisungen an Rolf in Anfänger-Sprache.

Vereinbart am 04.10.2026: Instagram Reel täglich 17:00 und TikTok täglich 18:00 mit dem Short des Tages, über
Metricool (Marke 7233482, Konto 5602673). Facebook bewusst weggelassen. Konten heißen `gigglemeadowshorts`.
Rolfs Anleitung zum Anlegen der Konten steht im Claude-Doc „Giggle Meadow – Instagram & TikTok einrichten“.

## Schritt 1 – Voraussetzungen prüfen (ohne Rolf)

```bash
cd aixwalker-pipeline && git pull && pip install -q -r requirements.txt --break-system-packages
env | grep -c '^METRICOOL_TOKEN='        # muss 1 sein
python - <<'EOF'
import os, requests
r = requests.get("https://app.metricool.com/api/v2/settings/brands", headers={"X-Mc-Auth": os.environ["METRICOOL_TOKEN"]},
                 params={"userId": "5602673"}, timeout=30)
print(r.status_code, r.text[:1500])
EOF
```
Fehlt der Token: Rolf anleiten (Doc, Abschnitt 5, Punkte 5–6), Sitzung beenden lassen und neu starten.
Liefert die Antwort keine Instagram-/TikTok-Verbindung für Marke 7233482 (`networksData` ohne `instagramData`/
`tiktokData` o. ä.): Rolf zu Doc-Abschnitt 5 Punkte 3–4 zurückschicken. Ist der Endpunkt anders als erwartet
(404), über `mcp__Metricool_Social_Media_Management__getBrandSettings` prüfen (ToolSearch) und die URL in
`kids/social.py` anpassen – die Scheduler-URL `POST /api/v2/scheduler/posts?userId&blogId` mit Header `X-Mc-Auth`
ist die bekannte; bei Abweichung die Metricool-API-Doku per WebFetch lesen (https://app.metricool.com/api/docs oder
„Metricool API scheduler posts“ suchen).

## Schritt 2 – Test als Entwurf (ohne Rolf, keine Veröffentlichung)

Den neuesten veröffentlichten Short nehmen (`build/kids/<letztes Datum>/result.json` mit `video_id` und `drive`; fehlt
lokal, den Ordner aus Drive laden – `python -m kids.compilation` nutzt dieselbe Logik, oder `result.json` aus dem
Drive-Tagesordner herunterladen):

```bash
KIDS_SOCIAL_DRAFT=1 python -m kids.social build/kids/<Datum>
```
Erwartet: je Netzwerk ein Eintrag mit `plannerUrl`. Fehler (400) → Body-Felder gegen die Metricool-Antwort
anpassen (häufig: `videoThumbnailUrl` nicht erlaubt → wird automatisch ohne wiederholt; `publicationDate`-Format;
Instagram verlangt Creator-/Business-Konto). Danach Rolf schicken: „Bitte in Metricool unter **Planung** die beiden
Entwürfe ansehen (Instagram, TikTok). Passt der Text? Antworte mit ‚passt‘ oder sag, was anders soll.“ **Warten.**
Änderungswünsche → Texte in `kids/social.py` (`_fallback_texts`, Gemini-Prompt, `HASHTAGS`) anpassen, Test wiederholen.

## Schritt 3 – Scharf schalten (ohne Rolf)

Nach „passt“: die Entwürfe in Metricool löschen lassen (Rolf: Planung → Entwurf öffnen → Löschen) oder per API
entfernen. Dann einmal echt: `python -m kids.social build/kids/<Datum>` (ohne DRAFT) – die Posts gehen zur nächsten
freien Zeit (mindestens 15 Minuten in der Zukunft) raus. Rolf die beiden Planner-Links schicken. Ab dem nächsten
16:00-Lauf passiert es automatisch (Schritt 4d der Routine), ohne weiteres Zutun.

## Schritt 4 – Abschluss

- Änderungen committen/pushen.
- Rolf in Anfängersprache zusammenfassen: was täglich wann passiert, wo er die Posts sieht (Metricool → Planung;
  Instagram/TikTok-Profil), wie er es pausiert (Umgebungsvariable `KIDS_SOCIAL_NETWORKS` leeren oder Metricool-
  Verbindung trennen), dass die Mail beide Planner-Links enthält.

## Technische Notizen

- Medien: `kids/social.py` gibt `short.mp4`/`thumbnail.jpg` im Drive-Tagesordner „jeder mit Link“ frei und übergibt
  `https://drive.google.com/uc?export=download&id=<id>`. Lehnt Metricool den Link ab, Alternative: Datei über
  Metricool-Upload-Endpunkt hochladen (API-Doku) oder Google Drive in Metricool verknüpfen (Einstellungen).
- Texte: Gemini (≈ 0,5 Cent) mit fester Vorlage als Fallback; Hashtags fest in `HASHTAGS`.
- Zeiten: `KIDS_SOCIAL_TIMES` (Standard `instagram=17:00,tiktok=18:00`), Netzwerke `KIDS_SOCIAL_NETWORKS`.
- Instagram-Posts werden als KI-Inhalt gekennzeichnet (`isAiGenerated`), TikTok ebenso (`isAigc`), TikTok-Kommentare
  aus – bewusst, Kinder-Inhalt.
