"""Amazon-Partnerlinks (Apricot-Lamb-Kuscheltiere) für die Videobeschreibungen von Giggle Meadow.

Je Video ein kurzer Block für Eltern mit 3 Kuscheltieren: zuerst die, die zum Tier/Thema der Geschichte passen
(Hase zum Hasen-Short), dann wechselnd weitere. Immer mit Werbekennzeichnung und Amazon-Pflichtsatz.
Liste von Rolf vom 14.10.2026; ersetzt den früheren Einzel-Link (Ziggys Kuschelhase, B072JH191N).

Abschalten: Umgebungsvariable `KIDS_AFFILIATE_LINE` leer setzen.
"""
import hashlib
import os
import re

# (Emoji, Beschreibung EN, Link, Stichwörter für die Zuordnung zur Geschichte)
PRODUCTS = [
    ("🐰", "Bunny plush – soft corduroy, 30 cm", "https://link.amazon/B0daob1me", ["bunny", "rabbit", "hare", "carrot"]),
    ("🦆", "Duck plush – velvet-soft, 23 cm", "https://link.amazon/B0fJCXySJ", ["duck", "duckling", "pond"]),
    ("🐧", "Penguin plush – extra fluffy, 20 cm", "https://link.amazon/B09MBEAuB", ["penguin", "ice", "snow", "walrus", "seal"]),
    ("🌸", "Cherry blossom plush – 25 cm", "https://link.amazon/B0c2p9Qc2", ["flower", "blossom", "plant", "garden", "seed", "water"]),
    ("🍀", "Lucky clover plush – 16 cm", "https://link.amazon/B0ilzqoxk", ["clover", "lucky", "meadow", "grass", "leaf"]),
    ("🐸", "Frog plush – 23 cm", "https://link.amazon/B0gA8xY3r", ["frog", "toad", "puddle", "rain"]),
    ("🦕", "Dino plush – green, 19 cm", "https://link.amazon/B00r6G6p1", ["dino", "dinosaur"]),
    ("🦀", "Crab plush – 23 cm", "https://link.amazon/B09vPIkCj", ["crab", "beach", "sea", "ocean", "sand", "shell"]),
    ("🦉", "Owl plush – 18 cm", "https://link.amazon/B07rfmv4i", ["owl", "night", "moon", "sleep", "bedtime"]),
    ("🐉", "Dragon plush – grass green, 20 cm", "https://link.amazon/B0bUtRf2T", ["dragon"]),
    ("🐻", "Bear plush – navy blue, 20 cm", "https://link.amazon/B00NkyIqq", ["bear", "teddy", "honey"]),
]
HEADER = "🧸 Cuddly friends from Giggle Meadow – for parents (ad · Amazon affiliate links):"
FOOTER = "As an Amazon Associate we earn from qualifying purchases."
OLD_MARKERS = ["B072JH191N", "Ziggy's favorite cuddly bunny"]   # früherer Einzel-Link – wird überall ersetzt


def enabled() -> bool:
    v = os.environ.get("KIDS_AFFILIATE_LINE")
    return v is None or v.strip() != ""      # nur ausdrücklich leer gesetzt = aus


def pick(text: str, n: int = 3) -> list[tuple]:
    """Passende Produkte zuerst (Wort-Treffer im Text), dann wechselnd weitere – je Video stabil."""
    low = text.lower()
    hits = [p for p in PRODUCTS if any(re.search(rf"\b{re.escape(k)}s?\b", low) for k in p[3])]
    seed = int(hashlib.md5(low.encode()).hexdigest(), 16)
    rest = [p for p in PRODUCTS if p not in hits]
    rest = rest[seed % len(rest):] + rest[:seed % len(rest)] if rest else []
    return (hits + rest)[:n]


def block(text: str, n: int = 3) -> str:
    rows = [f"{e} {name}: {url}" for e, name, url, _ in pick(text, n)]
    return "\n".join([HEADER, *rows, FOOTER])


def strip_old(desc: str) -> str:
    """Entfernt alte Affiliate-Zeilen und einen früher eingefügten Block (für Neusetzen)."""
    paras = [p for p in desc.split("\n\n") if not any(m in p for m in OLD_MARKERS) and HEADER not in p]
    return "\n\n".join(paras).strip()


def apply(desc: str, text_for_match: str = "", n: int = 3) -> str:
    """Setzt den Block vor den Hashtag-Absatz (bzw. ans Ende); ersetzt alte Links."""
    desc = strip_old(desc)
    if not enabled():
        return desc
    b = block(text_for_match or desc, n)
    parts = desc.rstrip().split("\n\n")
    if len(parts) > 1 and parts[-1].lstrip().startswith("#"):
        parts.insert(len(parts) - 1, b)
    else:
        parts.append(b)
    return "\n\n".join(parts)[:4900]


def update_channel(dry: bool = False) -> list[str]:
    """Tauscht in allen Videos des Kids-Kanals die Affiliate-Links aus (alter Link raus, neuer Block rein)."""
    from . import youtube
    yt = youtube.service()
    pl = youtube.my_channel()["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, tok = [], None
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=pl, maxResults=50, pageToken=tok).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        tok = r.get("nextPageToken")
        if not tok:
            break
    changed = []
    for i in range(0, len(ids), 50):
        for v in yt.videos().list(part="snippet", id=",".join(ids[i:i + 50])).execute()["items"]:
            sn = v["snippet"]
            n = 3 if "#shorts" in sn["title"].lower() else 5
            new = apply(sn.get("description", ""), sn["title"] + "\n" + sn.get("description", ""), n)
            if new == sn.get("description", ""):
                continue
            body = {"id": v["id"], "snippet": {k: sn[k] for k in ("title", "categoryId", "tags", "defaultLanguage",
                                                                  "defaultAudioLanguage") if k in sn}}
            body["snippet"]["description"] = new
            if not dry:
                yt.videos().update(part="snippet", body=body).execute()
            changed.append(f"{v['id']} {sn['title'][:60]}")
    return changed


if __name__ == "__main__":
    import sys
    for c in update_channel(dry="--dry" in sys.argv):
        print(c)
