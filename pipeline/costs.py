"""Kostenzähler für die Gemini-API (Lyria, Nano Banana).

Google bietet keinen Guthaben-/Kontostand-Endpunkt für die Gemini-API; abgerechnet wird monatlich über Cloud Billing.
Deshalb: Voranschlag vor dem Lauf (aus dem Konzept) und tatsächlicher Verbrauch nach dem Lauf (aus den echten
API-Aufrufen), beides in USD und EUR. Preise in config.PRICES_USD pflegen, falls Google sie ändert.
"""
import json
import os
import threading
from pathlib import Path

from . import config

_lock = threading.Lock()
_ledger_path: Path | None = None
_ledger: dict = {"lyria_tracks": 0, "lyria_retries": 0, "image_flash": 0, "image_pro": 0, "image_pro_4k": 0, "image_failed": 0}


def start(ledger_path: Path) -> None:
    """Ledger-Datei setzen; vorhandene Zählung (Neustart nach Abbruch) wird fortgeführt."""
    global _ledger_path, _ledger
    _ledger_path = ledger_path
    if ledger_path.exists():
        try:
            _ledger.update(json.loads(ledger_path.read_text()))
        except Exception:  # noqa: BLE001
            pass
    _save()


def _save() -> None:
    if _ledger_path:
        _ledger_path.parent.mkdir(parents=True, exist_ok=True)
        _ledger_path.write_text(json.dumps({**_ledger, "usd": total_usd(), "eur": usd_to_eur(total_usd())}, indent=2))


def count(key: str, n: int = 1) -> None:
    with _lock:
        _ledger[key] = _ledger.get(key, 0) + n
        _save()


def usd_to_eur(usd: float) -> float:
    return round(usd * float(os.environ.get("USD_EUR_RATE", config.USD_EUR_RATE)), 2)


def total_usd(ledger: dict | None = None) -> float:
    led = ledger or _ledger
    p = config.PRICES_USD
    # lyria_tracks zählt jede erfolgreiche Erzeugung (Neuversuche eingeschlossen); lyria_retries ist nur Information
    return round(led.get("lyria_tracks", 0) * p["lyria_track"]
                 + led.get("image_flash", 0) * p["image_flash"] + led.get("image_pro", 0) * p["image_pro"]
                 + led.get("image_pro_4k", 0) * p.get("image_pro_4k", p["image_pro"])
                 + led.get("veo_sec_4k_fast", 0) * p["veo_sec_4k_fast"], 3)


def estimate(concept: dict) -> dict:
    """Voranschlag aus dem Konzept: Tracks (+ Reserve bis Mindestlänge, + 15 % Neuversuche), Cover, Album, Thumbnail."""
    p = config.PRICES_USD
    minutes = float(concept.get("minutes_per_track", config.DEFAULT_MINUTES_PER_TRACK))
    min_minutes = float(concept.get("min_minutes", config.MIN_MIX_MINUTES))
    planned = len(concept["tracks"])
    needed = max(planned if concept.get('format') != 'long' else 0, int(-(-min_minutes // max(minutes * 0.56, 1))))  # Lyria liefert ca. 2,8–3 Min statt 5
    retries = max(1, round(needed * 0.15))
    tracks_usd = (needed + retries) * p["lyria_track"]
    group = config.LONG_ART_GROUP if concept.get("format") == "long" else 1
    needed_art = -(-needed // group)
    images_usd = needed_art * p["image_flash"] + p["image_pro_4k"]  # Cover je Track(-Gruppe) (Flash) + 1 Hauptbild 4K (Album + Thumbnail)
    usd = round(tracks_usd + images_usd, 2)
    return {"tracks_planned": planned, "tracks_expected": needed, "retries_reserved": retries,
            "usd": usd, "eur": usd_to_eur(usd),
            "lines": [f"{needed + retries} Lyria-Tracks (inkl. {retries} Reserve/Neuversuche) à {p['lyria_track']:.3f} $ = {tracks_usd:.2f} $",
                      f"{needed_art} Track-Cover à {p['image_flash']:.3f} $ + 1 Hauptbild 4K für Album-Cover und Thumbnail à {p['image_pro_4k']:.3f} $ = {images_usd:.2f} $"]}


def report() -> str:
    usd = total_usd()
    led = _ledger
    return (f"Tatsächlicher API-Verbrauch: {usd:.2f} $ ≈ {usd_to_eur(usd):.2f} € "
            f"({led['lyria_tracks']} Lyria-Erzeugungen, davon {led['lyria_retries']} Neuversuche nach QC, "
            f"{led['image_flash']} Flash-Bilder, {led['image_pro']} Pro-Bilder, {led.get('image_pro_4k', 0)} Pro-4K-Bilder, {led['image_failed']} Bild-Fallbacks ohne Kosten)")


def budget_hint(usd: float) -> str:
    limit = float(os.environ.get("BUDGET_WARN_USD", config.BUDGET_WARN_USD))
    txt = (f"Hinweis: Google bietet keinen Kontostand für die Gemini-API; der reale Monatsstand steht unter "
           f"{config.BILLING_URL} (Abrechnung monatlich per Cloud Billing).")
    if usd > limit:
        txt = f"WARNUNG: Voranschlag {usd:.2f} $ liegt über der Schwelle BUDGET_WARN_USD={limit:.2f} $ – vor dem Start Rücksprache. " + txt
    return txt


if __name__ == "__main__":
    import sys
    c = json.loads(Path(sys.argv[1] if len(sys.argv) > 1 else "concepts/example.json").read_text())
    e = estimate(c)
    print(f"Kostenvoranschlag „{c['album']}“: {e['usd']:.2f} $ ≈ {e['eur']:.2f} €")
    for ln in e["lines"]:
        print(" -", ln)
    print(budget_hint(e["usd"]))
