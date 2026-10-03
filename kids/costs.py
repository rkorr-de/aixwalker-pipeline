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
_ledger: dict = {"veo_sec_standard": 0, "veo_sec_fast": 0, "veo_sec_lite": 0, "image_flash": 0, "image_pro": 0,
                 "lyria_track": 0, "text_call": 0, "text_call_pro": 0,
                 "kling_sec_pro": 0, "kling_sec_pro_audio": 0, "kling_sec_standard": 0, "kling_sec_standard_audio": 0,
                 "sfx_sec": 0,
                 "veo_failed": 0}


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
    """Voranschlag: Video (Kling 15 s oder Veo 2 × 8 s, + 1 Reserve-Durchgang), Bilder, Musik, Prüfungen."""
    if config.VIDEO_PROVIDER == "kling":
        vid = price(f"kling_sec_{config.KLING_TIER}", 15)
        sfx = price("sfx_sec", 15)
        imgs = price("image_flash", 2) + price("image_pro", 1)
        rest = price("lyria_track", 1) + price("text_call", 4) + price("text_call_pro", 6)
        usd = round(vid + sfx + imgs + rest, 2)
        return {"usd": usd, "eur": eur(usd), "lines": [
            f"Kling 3.0 {config.KLING_TIER} 15 s = {vid:.2f} $, Geräusche {sfx:.2f} $",
            f"2 Nano-Banana-Bilder + 1 Pro-Thumbnail = {imgs:.2f} $",
            f"Musik + Story-/Videoprüfung ≈ {rest:.2f} $ (Neuversuch bei abgelehnter Prüfung kostet erneut)"]}
    sec_key = "veo_sec_standard" if standard else "veo_sec_fast"
    clips = 2 + retries
    veo = price(sec_key, clips * config.VEO_CLIP_SEC)
    imgs = price("image_flash", 3) + price("image_pro", 1)
    music = price("lyria_track", 1)
    text = price("text_call", 4) + price("text_call_pro", 6)
    usd = round(veo + imgs + music + text, 2)
    return {"usd": usd, "eur": eur(usd), "lines": [
        f"{clips} Veo-Clips à {config.VEO_CLIP_SEC} s ({'Standard' if standard else 'Fast'}) = {veo:.2f} $",
        f"3 Nano-Banana-Bilder + 1 Pro-Thumbnail = {imgs:.2f} $",
        f"1 Lyria-Musikbett = {music:.2f} $, Textaufrufe ≈ {text:.2f} $"]}


def report() -> str:
    u = total_usd()
    return (f"Tatsächlicher API-Verbrauch: {u:.2f} $ ≈ {eur(u):.2f} € "
            f"(Kling {_ledger['kling_sec_pro'] + _ledger['kling_sec_standard'] + _ledger['kling_sec_pro_audio'] + _ledger['kling_sec_standard_audio']} s, "
            f"Veo {_ledger['veo_sec_standard'] + _ledger['veo_sec_fast'] + _ledger['veo_sec_lite']} s, {_ledger['image_flash']} Flash-Bilder, "
            f"{_ledger['image_pro']} Pro-Bilder, {_ledger['lyria_track']} Lyria, {_ledger['text_call']} Textaufrufe, "
            f"{_ledger['veo_failed']} fehlgeschlagene Veo-Versuche). Monatsstand: {config.BILLING_URL}")


def ledger() -> dict:
    return dict(_ledger)
