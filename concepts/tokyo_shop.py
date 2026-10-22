"""Amazon-Partnerlinks für die Tokyo-Mix-Beschreibung (Rolf 22.10.2026).
Zeigt NUR die Produkte, die in der Variation des jeweiligen Raums vorkommen (`var` aus tokyo_variation.choose).
Partner-ID: gigglemeadow2-21 (Amazon.de). Fehlt ein Produkt hier, bleibt die Zeile weg."""

TAG = "gigglemeadow2-21"


def _dp(asin: str) -> str:
    return f"https://www.amazon.de/dp/{asin}?tag={TAG}"


# Schlüssel = Wert in der Variation (var["kb"], var["audio"], var["pc"], var["purifier"]) bzw. "headphones", "rack"
PRODUCTS = {
    ("kb", "hhkb"): ("⌨️", "HHKB Studio keyboard", "https://link.amazon/B04UzR5um"),
    ("kb", "keychron"): ("⌨️", "Keychron Q1 Ultra keyboard", "https://link.amazon/B02bHiavI"),
    ("audio", "kef"): ("🔊", "KEF LSX II LT active speakers", _dp("B0CRVW7DQD")),
    ("headphones", True): ("🎧", "Sennheiser HD 800 S headphones", "https://link.amazon/B01DJyajy"),
    ("pc", "north"): ("🖥️", "Fractal Design North XL case", "https://link.amazon/B0acnLSFq"),
    ("pc", "sff"): ("🖥️", "Fractal Design Terra case", "https://link.amazon/B05haD6UO"),
    ("purifier", "dyson"): ("🌿", "Dyson Purifier Cool air purifier", "https://link.amazon/B09gj5vtt"),
    ("rack", True): ("📡", "Ubiquiti UniFi Dream Machine SE", _dp("B09QZBBRRS")),
}
# Nicht auf Amazon.de verlinkt (bisher kein Link): genelec, alu-PC, balmuda, Stuhl (Eames/Aeron), Schiit-Verstärker.

HOOKS = [
    "Love the setup? Here's the exact gear behind tonight's desk:",
    "Want this calm, focused corner for yourself? Here's what's on the desk:",
    "Build your own late-night focus setup with the gear from this room:",
    "Your best deep-work night starts with the right tools. This is what you see here:",
]
DISCLOSURE = "Ad · Affiliate links – Als Amazon-Partner verdiene ich an qualifizierten Verkäufen."


def shop_block(var: dict | None, vol: int = 0) -> str:
    """Fertiger Textblock (leer, wenn keine Variation bekannt oder kein Produkt verlinkbar)."""
    if not var:
        return ""
    keys = [("kb", var.get("kb")), ("audio", var.get("audio")), ("headphones", bool(var.get("audio"))),
            ("pc", var.get("pc")), ("purifier", var.get("purifier")), ("rack", bool(var.get("rack")))]
    lines = []
    for k in keys:
        if k in PRODUCTS:
            icon, name, url = PRODUCTS[k]
            lines.append(f"{icon} {name}: {url}")
    if not lines:
        return ""
    return f"{HOOKS[vol % len(HOOKS)]}\n" + "\n".join(lines) + f"\n{DISCLOSURE}"
