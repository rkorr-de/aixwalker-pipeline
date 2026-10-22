"""Variationen für das Bild-Prompt der Tokyo-Räume (Rolf 22.10.2026, autark):

* Schreibtisch: vorn (links/rechts im Bild) ODER im hinteren Teil der Wohnung – Hauptsache sichtbar.
* Bürostuhl: Farbe cognac ODER schwarz (Leder) und wechselnde Stellung.
* Couch: mal Stoff (wechselnde Farbe), mal Leder (wechselnde Farbe).
* Wandbild im Wohnbereich: ab und zu ein großes japanisches abstraktes Tuschebild in Schwarz-Weiß (jedes Mal ein anderes,
  nie wiederholt), sonst anderes Wandbild oder keins.

`choose()` wählt automatisch anhand des Verlaufs im Gedächtnis („tokyo“, Feld „variation“): nichts wiederholt sich direkt,
Tuschebilder nie. `apply()` setzt die Wahl in die Prompt-Bausteine aus genre_test_tokyo_rooms_v3 ein.
"""
import random

# ---- Auswahllisten ---------------------------------------------------------------------------------------------------
DESK_POS = ("front", "back")

CHAIR_COLORS = {
    "cognac": "an Eames-style designer office chair with cognac-brown leather upholstery on a slim polished aluminum frame",
    "black": "a sleek designer office chair with black leather upholstery on a slim matte black frame",
}
CHAIR_POSES = {
    "away": "pushed back a little and slightly turned away from the desk",
    "toward_camera": "turned three-quarters toward the camera as if someone has just got up",
    "tucked": "pulled neatly up to the desk, facing the monitors, seen from behind",
    "angled": "rotated about 45 degrees with one armrest toward the camera",
    "window": "tilted back slightly and turned toward the window instead of the screens",
}

SOFA_FABRIC = ("oatmeal bouclé", "charcoal linen", "warm sand wool", "deep olive velvet", "greige woven fabric", "dusty rose linen")
SOFA_LEATHER = ("cognac-brown leather", "black leather", "dark tan leather", "espresso-brown leather", "warm grey leather")

INK_ART = {
    "enso": "one single huge bold circular brushstroke (enso) in black ink on white paper with dry-brush texture",
    "three_sweeps": "a wide calm horizontal sweep of three heavy black brushstrokes with fine ink splatters on white",
    "rain_drips": "vertical cascading ink drips and thin hairline strokes on white, like falling rain",
    "diptych": "a diptych of two tall panels: left a dense black ink mass with soft grey wash edges, right almost empty white with one thin diagonal stroke",
    "triptych": "a triptych of three square panels, each with a different black ink blot, grey wash and one fine line",
    "mist_peak": "layered grey-wash shapes dissolving into mist with one dark ink peak, abstract, no recognizable landscape detail",
    "splash": "an explosive ink splash radiating from the lower left with fine splatter dots on white",
    "cross": "two broad crossing strokes forming an abstract X with visible dry-brush bristle texture",
    "single_line": "a long thin horizontal panel with a single fine wavering black line and a few ink dots",
    "wiped_block": "a large square canvas with a dense black rectangle wiped with a white dry brush, minimal and bold",
    "ripples": "overlapping translucent grey-and-black wash circles like ripples on water",
    "scroll": "a tall vertical scroll-format abstract with one sinuous black stroke from top to bottom and tiny ink specks",
    "tangle": "tangled loose calligraphic-style black lines, energetic and abstract, without any readable characters",
    "comet": "a soft grey wash gradient with one crisp black comet-like brushstroke across it",
    "stipple": "a dense field of black ink dots of different sizes fading into white, like drifting snow",
    "arc": "one huge sweeping black arc with feathered dry edges over a pale grey wash, calm and powerful",
}
OTHER_ART = {
    "sand_canvas": "a large framed minimalist abstract canvas in warm sand and terracotta tones",
    "woodblock": "a pair of small framed ukiyo-e-inspired woodblock prints of waves and cranes (no text)",
    "alley_photo": "a wide framed black-and-white photograph of a quiet Tokyo alley at night (no text, no signs)",
    "green_gold": "a large dark-green abstract canvas with one thin gold line",
    "none": "",   # keine Wandbilder, nur Regal mit Keramik
}


def _hist(history: list[dict], key: str) -> list:
    return [e.get("variation", {}).get(key) for e in history if isinstance(e.get("variation"), dict)]


def choose(history: list[dict], seed: str, desk_pos: str = "auto", chair: str = "auto", sofa: str = "auto",
           art: str = "auto") -> dict:
    """Wählt die Variation für den neuen Raum. `history`: Gedächtnis-Einträge „tokyo“ (alt→neu). Ein Wert ≠ „auto“ gilt fest
    (art: „ink“, „other“ oder ein Schlüssel aus INK_ART/OTHER_ART)."""
    rnd = random.Random(seed)
    sub = lambda name: random.Random(f"{seed}/{name}")   # eigener Zufallsstrom je Merkmal → Merkmale unabhängig voneinander
    last = (history[-1].get("variation") or {}) if history else {}

    def other(options, prev, name="x"):
        pool = [o for o in options if o != prev] or list(options)
        return sub(name).choice(pool)

    def balanced(options, key):
        """Zufall, unabhängig von den anderen Merkmalen; nie dreimal derselbe Wert hintereinander."""
        h = _hist(history, key)[-2:]
        pool = [o for o in options if not (len(h) == 2 and h[0] == h[1] == o)]
        return sub(key).choice(pool or list(options))

    pos = desk_pos if desk_pos != "auto" else balanced(DESK_POS, "desk_pos")           # vorn / hinten
    ch = chair if chair != "auto" else balanced(tuple(CHAIR_COLORS), "chair")          # cognac / schwarz
    pose = other(tuple(CHAIR_POSES), last.get("chair_pose"), "pose")
    if sofa != "auto":
        material = "leather" if sofa == "leather" else "fabric"
    else:
        material = balanced(("fabric", "leather"), "sofa_material")
    colors = SOFA_LEATHER if material == "leather" else SOFA_FABRIC
    recent = set(_hist(history, "sofa_color")[-3:])
    color = sub("sofa_color").choice([c for c in colors if c not in recent] or list(colors))

    used_ink = {k for k in _hist(history, "art_key") if k in INK_ART}
    if art in INK_ART:
        art_key = art
    elif art in OTHER_ART:
        art_key = art
    else:
        want_ink = art == "ink" or (art == "auto" and not last.get("ink") and sub('ink').random() < 0.55)   # ab und zu, nie zweimal hintereinander
        if want_ink:
            fresh = [k for k in INK_ART if k not in used_ink]
            art_key = sub('inkart').choice(fresh or list(INK_ART))   # erst wenn alle 16 gezeigt wurden, wieder von vorn
        else:
            art_key = other(tuple(OTHER_ART), last.get("art_key"), "otherart")
    return {"desk_pos": pos, "chair": ch, "chair_pose": pose, "sofa_material": material, "sofa_color": color,
            "art_key": art_key, "ink": art_key in INK_ART}


def apply(var: dict, side: str, base) -> dict:
    """Setzt die Variation in die Bausteine von genre_test_tokyo_rooms_v3 (`base`) ein. Liefert {"desk", "cozy", "style", "art"}."""
    import genre_test_tokyo_lounge_v2 as v
    chair = (f"at the desk stands {CHAIR_COLORS[var['chair']]}, {CHAIR_POSES[var['chair_pose']]}")
    desk = base.DESK.format(side=side)
    assert v.CHAIR in desk, "DESK enthält die Stuhl-Beschreibung nicht mehr"
    desk = desk.replace(v.CHAIR, chair)
    # der Satz nach der Stuhl-Beschreibung im Original (", pushed back a little and slightly turned away from the desk. ") entfällt
    desk = desk.replace(", pushed back a little and slightly turned away from the desk. ", ". ")
    if var["desk_pos"] == "back":
        front = f"The home-office zone is only a part of the picture and sits in the {side} third of the frame, NOT in the center:"
        assert front in desk, "DESK-Einleitung geändert"
        desk = desk.replace(front, (f"The home-office zone is located in the REAR part of the loft, far from the camera (roughly the back third of the room's depth, "
                                    f"on the {side} side, seen from a distance so that the workplace looks fairly small in the frame, NOT in the foreground and not in the center), "
                                    "but both monitors, the keyboard, the mouse and the office chair are still clearly recognizable and visible:"))
    sofa_old = "a soft wool throw on a low modular designer sofa"
    assert sofa_old in base.COZY, "COZY-Sofa-Satz geändert"
    sofa = f"a low modular designer sofa in {var['sofa_color']}" + (" with a soft wool throw" if var["sofa_material"] == "fabric" else " with a folded wool throw")
    cozy = base.COZY.replace(sofa_old, sofa)
    old_style = "the Eames chair is clearly cognac-brown leather in every image, "
    assert old_style in base.STYLE, "STYLE-Stuhl-Satz geändert"
    style = base.STYLE.replace(old_style, f"the office chair is clearly {'cognac-brown' if var['chair'] == 'cognac' else 'black'} leather in every image, ")
    if var["ink"]:
        art = ("In the living area, on the wall above the sofa, hangs ONE large framed abstract Japanese ink painting in strictly black and white "
               f"(sumi-e style, no color, no text, no readable characters): {INK_ART[var['art_key']]}. ")
    elif OTHER_ART.get(var["art_key"]):
        art = f"On the living-area wall hangs {OTHER_ART[var['art_key']]}. "
    else:
        art = "The living-area wall stays calm and bare apart from a wooden shelf with ceramics. "
    return {"desk": desk, "cozy": cozy, "style": style, "art": art}


def check_text(var: dict) -> str:
    """Zusätze für die automatische Bildprüfung (JSON-Schlüssel + Regeln)."""
    color = "cognac-brown" if var["chair"] == "cognac" else "black"
    return (f"\"chair\" (true if an office chair with {color} leather upholstery stands at or near the desk), "
            f"\"art_ink\" (true if a large framed abstract black-and-white ink painting hangs on a wall; "
            f"{'REQUIRED' if var['ink'] else 'not required'}), ")
