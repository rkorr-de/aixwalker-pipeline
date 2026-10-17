# Konzept: Samstags-Mega-Mix – Stand 17.10.2026 (v3, nach Rolfs Antworten)

**Ziel:** mehr lange Inhalte und mehr Wiedergabezeit bei minimalen Kosten. Claude baut alles selbst zusammen.

| Thema | Entscheidung |
|---|---|
| Wann | jeden Samstag, Veröffentlichung 14:00 Uhr Berlin (Bau ab dem Vormittag, geplante Freischaltung) |
| Länge | bis 8 Std. (Material begrenzt es zuerst) |
| Musik | nur vorhandene Songs der Genre-Mixe, Zufallsreihenfolge, pro Mix kein Song doppelt, keine DistroKid-Abgabe |
| Neue Bilder | Hauptbild ohne Schrift (outdoor; Cabin innen) → Thumbnail mit auffälliger Schrift + Album-Cover 3000×3000; unbeschriftetes Bild in Drive |
| Italian / Lounge | kein neues Video; Kosten nur das Hauptbild (ca. 0,24 $) |
| Cabin | 2 neue Veo-Clips 4K, nahtlos wie bisher; nur ruhig liegender Schnee, **kein Schneien**; ca. 5 $ |
| Shorts | 2 je Mega-Mix: Samstag + Sonntag; Cabin aus dem neuen 4K-Material, sonst aus bezahlten Kling-Clips |
| Related Video | in die Planung eingebaut: Einträge in `shorts2` mit `mix_video_id`; Abendaufgabe 19:45 verknüpft und schaltet öffentlich |
| Sonntag | die Sonntags-Cabin-Aufgabe bleibt; Songs dürfen wiederverwendet werden |

Umsetzung: `run_megamix.py`, `pipeline/megamix.py`, Test `tests/test_megamix.py`. Details im Abschnitt „Samstags-Mega-Mix“ der `ROUTINE_PROMPT.md`.
