"""Kids-Shorts-Pipeline.

Beim ersten Import wird geprüft, ob die nötigen Python-Pakete in GENAU dem Python vorhanden sind, mit dem gerade
gearbeitet wird. In den Cloud-Sitzungen zeigt `pip` manchmal auf ein anderes Python als `python` – dann fehlte
z. B. `googleapiclient` (07.10.2026), obwohl `pip install -r requirements.txt` gelaufen war. Deshalb wird hier
notfalls mit `<dieses Python> -m pip` nachinstalliert, statt abzubrechen.
"""
import importlib
import subprocess
import sys
from pathlib import Path

_NEEDED = {   # Import-Name → pip-Paket
    "googleapiclient": "google-api-python-client",
    "google.auth": "google-auth",
    "google_auth_oauthlib": "google-auth-oauthlib",
    "requests": "requests",
    "PIL": "Pillow",
    "numpy": "numpy",
}


def _missing() -> list[str]:
    out = []
    for mod, pkg in _NEEDED.items():
        try:
            importlib.import_module(mod)
        except Exception:  # noqa: BLE001
            out.append(pkg)
    return out


def _ensure_packages() -> None:
    miss = _missing()
    if not miss:
        return
    print(f"[kids] Fehlende Python-Pakete für {sys.executable}: {', '.join(miss)} – installiere nach …", flush=True)
    req = Path(__file__).resolve().parent.parent / "requirements.txt"
    base = [sys.executable, "-m", "pip", "install", "-q", "--break-system-packages"]
    attempts = ([base + ["-r", str(req)]] if req.exists() else []) + [base + miss, [*base[:-1], "--user", *miss]]
    for cmd in attempts:
        try:
            subprocess.run(cmd, check=False, timeout=900)
        except Exception as e:  # noqa: BLE001
            print(f"[kids] pip-Aufruf fehlgeschlagen: {e}", flush=True)
        importlib.invalidate_caches()
        if not _missing():
            print("[kids] Pakete nachinstalliert – weiter.", flush=True)
            return
    print(f"[kids] WARNUNG: weiterhin fehlend: {', '.join(_missing())}", flush=True)


_ensure_packages()
