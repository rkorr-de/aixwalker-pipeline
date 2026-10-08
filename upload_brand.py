#!/usr/bin/env python3
"""Lädt die aktuellen Kanal-Markendateien (Banner, Logo) nach Drive: „AIX WALKER Mixe/_kanal“. Kein Mix, keine Kosten.

    python upload_brand.py
"""
from pathlib import Path

from pipeline import drive

ROOT = Path(__file__).parent
FILES = [ROOT / "assets" / "brand" / "kanalbanner_aktiv.jpg", ROOT / "assets" / "brand" / "aixwalker_logo.png"]

if __name__ == "__main__":
    links = drive.upload_mix_package("_kanal", [f for f in FILES if f.exists()])
    for k, v in links.items():
        print(f"{k}: {v}")
