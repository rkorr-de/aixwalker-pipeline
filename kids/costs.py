"""Kostenzähler mit harter Budgetgrenze für die Kids-Shorts.

Vor jedem kostenpflichtigen Aufruf wird geprüft, ob der Lauf damit über KIDS_BUDGET_USD käme; dann wird
BudgetExceeded ausgelöst (kein Upload, stattdessen Fehlermail). Ledger-Datei liegt in build/kids/<datum>/costs.json.
"""
import json
import threading
from pathlib import Path

from . import config

_lock = threading.Lock()
_path: Path | None = None
_ledger: dict = {"veo_sec_standard": 0, "veo_sec_fast": 0, "image_flash": 0, "image_pro": 0,
                 "lyria_track": 0, "text_call": 0, "veo_failed": 0}


class BudgetExceeded(RuntimeError):
    pass


def start(path: Path) -> None:
    global _path
    _path = path
    if path.exists():
        try:
            _ledger.update({k: v for k, v in json.loads(path.read_text()).items() if k in _ledger})
        except Exception:  # noqa: BLE001
            pass
    _save()


def _save() -> None:
    if _path:
        _path.parent.mkdir(parents=True, exist_ok=True)
        _path.write_text(json.dumps({**_ledger, "usd": total_usd(), "eur": eur(total_usd()),
                                     "budget_usd": config.BUDGET_USD}, indent=2))


def eur(usd: float) -> float:
    return round(usd * config.USD_EUR_RATE, 2)


def total_usd() -> float:
    return round(sum(_ledger.get(k, 0) * p for k, p in config.PRICES_USD.items()), 3)


def price(key: str, n: float = 1) -> float:
    return config.PRICES_USD[key] * n


def ensure_budget(key: str, n: float = 1) -> None:
    """Löst BudgetExceeded aus, wenn der nächste Aufruf das Budget sprengen würde."""
    projected = total_usd() + price(key, n)
    if projected > config.BUDGET_USD:
        raise BudgetExceeded(f"Budget {config.BUDGET_USD:.2f} $ würde überschritten: bisher {total_usd():.2f} $, "
                             f"nächster Schritt {key}×{n} = {price(key, n):.2f} $ → {projected:.2f} $")


def count(key: str, n: float = 1) -> None:
    with _lock:
        _ledger[key] = _ledger.get(key, 0) + n
        _save()


def estimate(standard: bool = True, retries: int = 1) -> dict:
    """Voranschlag: 2 Clips × 8 s (+ Reserve), Bilder, Musik, Textaufrufe."""
    sec_key = "veo_sec_standard" if standard else "veo_sec_fast"
    clips = 2 + retries
    veo = price(sec_key, clips * config.VEO_CLIP_SEC)
    imgs = price("image_flash", 3) + price("image_pro", 1)
    music = price("lyria_track", 1)
    text = price("text_call", 3)
    usd = round(veo + imgs + music + text, 2)
    return {"usd": usd, "eur": eur(usd), "lines": [
        f"{clips} Veo-Clips à {config.VEO_CLIP_SEC} s ({'Standard' if standard else 'Fast'}) = {veo:.2f} $",
        f"3 Nano-Banana-Bilder + 1 Pro-Thumbnail = {imgs:.2f} $",
        f"1 Lyria-Musikbett = {music:.2f} $, Textaufrufe ≈ {text:.2f} $"]}


def report() -> str:
    u = total_usd()
    return (f"Tatsächlicher API-Verbrauch: {u:.2f} $ ≈ {eur(u):.2f} € "
            f"(Veo {_ledger['veo_sec_standard'] + _ledger['veo_sec_fast']} s, {_ledger['image_flash']} Flash-Bilder, "
            f"{_ledger['image_pro']} Pro-Bilder, {_ledger['lyria_track']} Lyria, {_ledger['text_call']} Textaufrufe, "
            f"{_ledger['veo_failed']} fehlgeschlagene Veo-Versuche). Monatsstand: {config.BILLING_URL}")


def ledger() -> dict:
    return dict(_ledger)
