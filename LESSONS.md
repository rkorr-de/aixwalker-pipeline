# Lessons Learned (Stand 2026-09-30, Mix „Rainy Night Cabin“)

Beim nächsten Lauf vorab lesen und beachten. Was schiefging und was jetzt gilt:

| Problem | Folge | Regel / Fix |
|---|---|---|
| Titel sagte „45 Min“, Video war 37:03 | Falsche Angabe auf YouTube, Thumbnail, Beschreibung | `sync_concept` gleicht Minuten, Tags, Shorts automatisch an echte Laufzeit an (abgerundet). Vorher planen: ein Track dauert real ~2,9 min (nicht 3,2) → für 45 Min **16 Tracks**, für 40 Min 14 |
| Shorts-Zeitmarke zeigte falschen Track (09:30 statt 17:03) | Falscher Clip-Vorschlag | Shorts als `{"track": "<Titel>", "offset": 10, "length": 40}` angeben, Pipeline rechnet aus den echten Startzeiten |
| Gemini-Credits leer (HTTP 402) → stiller Fallback auf Platzhalter-Bild | Thumbnail/Covers ohne Motiv, echte Bilder überschrieben, zwei Zusatzläufe, Duplikate auf YouTube | Kein Fallback mehr in echten Läufen, Lauf bricht ab. **Vor dem Start einen Bild-Testaufruf** machen; bei 402 sofort Rolf melden (AI Studio Credits) und nichts überschreiben |
| Videodatei lässt sich per API nicht austauschen | `--update-video` ändert nur Text/Tags/Thumbnail; bei geänderter Länge neuer Upload + altes Video löschen | Länge **vor** dem Upload festlegen (Track-Anzahl planen). Duplikate nur nach Rolfs Ja löschen |
| Lauf nach Textkorrektur komplett neu gerendert (~20 min) | Zeitverlust, Bilder erneut erzeugt | Bei reinen Text-/Zeitkorrekturen nur Metadaten + Thumbnail neu, nicht alles (Motiv `thumbnail/art.png` wiederverwenden) |
| ZIP 116–144 MB, Dateiversand max. 30 MB | ZIP nicht zustellbar | Pipeline erzeugt `delivery/` mit `mp3_teil*.zip` (je ≤ 25 MB) + `album_3000.png`; MP3s wiegen ~6 MB (Cover eingebettet) |
| `pkill -f run_mix` tötete die eigene Shell | Lauf nicht gestartet | Laufenden Lauf per PID stoppen, nie mit `pkill -f` auf Befehlszeilen |
| Löschbefehl mit Shell-Variable (`rm $D/*`) blockiert | Verzögerung | Feste Pfade verwenden |
| Zusatzsuchen nach SendUserMessage scheiterten | Tool existiert in der Sitzung nicht | Meldungen als normale Antwort ausgeben |

## Standardablauf ab jetzt
1. Bild-API testen, Rolf bei Fehler sofort melden.
2. Track-Anzahl so wählen, dass Dauer = Zielminuten (real ~2,9 min/Track).
3. Lauf, danach **Prüfliste**: Titel/Beschreibung/Tags/Thumbnail zeigen echte Minuten; Thumbnail visuell prüfen (Motiv da, Text lesbar, nichts Wichtiges verdeckt); Shorts-Zeiten gegen Kapitel; Video privat; KI-Label; Playlist.
4. Auslieferung: `delivery/`-Dateien senden, Video-Link, Titel, Beschreibung, Kapitel, Community-Text, Shorts.
5. Beim ersten Release DistroKid-Anleitung; danach Store-Links in Beschreibung nachtragen.
