"""Feste Bibliothek sanfter, kindgerechter Geräusche (einmalig erzeugt, geprüft, im Repo unter assets/kids_sfx/).

Warum: Eine frei erzeugte 15-s-Geräuschspur wurde zu schrillem „Chipmunk-Gebrabbel“. Stattdessen wählt die Story
4–7 kurze Geräusche aus dieser Liste und legt fest, in welcher Sekunde sie erklingen (story["sfx_cues"]).

Neu erzeugen/ergänzen: `python -m kids.sfx_library` – erzeugt fehlende Geräusche über fal.ai (ElevenLabs Sound
Effects V2, ca. 0,004 $ je Geräusch), kürzt Stille, normalisiert die Lautstärke und lässt jedes Geräusch von
config.CRITIC_MODEL anhören. Unter Note 8 wird es neu erzeugt (max. 3 Versuche), sonst nicht benutzt.
"""
import json
import subprocess
from pathlib import Path

from . import config, costs, fal, gemini

DIR = config.ROOT / "assets" / "kids_sfx"
INDEX = DIR / "index.json"

_NO_VOICE = "no voice, no speech, no singing, no babble, no music, clean, soft, gentle, not loud, not harsh"
LIBRARY: dict[str, tuple[str, float]] = {
    # key: (Beschreibung für ElevenLabs, Länge in s)
    "footsteps": ("soft little padded cartoon footsteps on a carpet, four slow cute steps", 2.0),
    "tiptoe": ("very soft cartoon tiptoe steps, three tiny careful steps", 1.5),
    "slide": ("a wooden toy block sliding slowly and smoothly across a wooden floor", 1.5),
    "thud": ("a soft muffled thud of a light toy block landing on a soft play mat", 0.8),
    "boing": ("one soft gentle cartoon boing, warm and round, low volume", 0.8),
    "pop": ("one soft cute bubble pop", 0.5),
    "whoosh": ("a gentle soft airy whoosh, like a small toy moving", 0.8),
    "sparkle": ("magical twinkling sparkle chime, soft fairy glitter, warm", 1.5),
    "tada": ("cheerful soft xylophone and glockenspiel 'ta-da' success jingle, three bright rising notes", 1.5),
    "oh_no": ("gentle soft descending two-note marimba 'oh-oh', cute and not sad", 1.0),
    "question": ("curious soft rising two-note xylophone 'hmm?' sound", 0.8),
    "idea": ("a bright soft single bell ding, like a light bulb idea moment in a cartoon", 0.8),
    "clap": ("small soft cartoon paw claps, four quick gentle claps", 1.2),
    "hug": ("soft cozy fabric rustle and a warm gentle harp shimmer", 1.5),
    "munch": ("cute soft crunchy munching of an apple, three small bites", 1.5),
    "rustle": ("soft gentle rustle of leaves and grass", 1.5),
    "ball": ("a soft rubber ball bouncing gently three times on a wooden floor", 1.5),
    "heart": ("warm twinkly harp glissando, sweet and loving", 1.5),
    "squeak_happy": ("one tiny cute happy squeak of a baby hamster, short, soft, sweet", 0.6),
    "chirp_happy": ("one short sweet happy chirp of a baby bird, soft", 0.6),
    "purr": ("a soft gentle content purr of a kitten", 1.5),
    "coo": ("a soft cute cooing sound of a baby dove, gentle", 1.0),
    "yawn_soft": ("a tiny soft sleepy sigh sound, like a sleepy puppy, very gentle", 1.0),
    "giggle_toy": ("a soft cute squeaky toy honk, one short squeeze", 0.6),
    "pluck": ("a single soft pizzicato string pluck, playful", 0.5),
}

RATING_PROMPT = (
    "Listen carefully to this short sound effect for a toddler cartoon. Intended sound: {desc}. "
    'Answer as JSON: {{"matches": true/false, "has_voice_or_babble": true/false, "harsh_or_shrill": true/false, '
    '"toddler_friendly": 1-10, "description": "what you actually hear, in English, max 20 words"}}'
)


def _clean(src: Path, dst: Path) -> None:
    """Stille am Anfang/Ende weg, Lautstärke angleichen (−20 LUFS), sanftes Aus-/Einblenden."""
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-af",
                    "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                    "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                    "loudnorm=I=-20:TP=-3:LRA=7,afade=t=in:d=0.02,aformat=sample_rates=48000:channel_layouts=stereo",
                    "-c:a", "libmp3lame", "-q:a", "3", str(dst)], check=True)


def _vol(f: Path, key: str) -> float:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(f), "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    return float(next(l for l in r.splitlines() if key in l).split(":")[-1].split()[0])


def level(f: Path, mean_db: float = -15.0) -> None:
    """Kurze Geräusche einheitlich gut hörbar machen: mittlere Lautstärke auf `mean_db`, Spitzen begrenzt."""
    tmp = f.with_suffix(".lvl.mp3")
    gain = mean_db - _vol(f, "mean_volume")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(f), "-af",
                    f"volume={gain:.1f}dB,alimiter=limit=0.89:attack=2:release=50:level=false",
                    "-c:a", "libmp3lame", "-q:a", "3", str(tmp)], check=True)
    tmp.replace(f)


def index() -> dict:
    return json.loads(INDEX.read_text()) if INDEX.exists() else {}


def available() -> dict[str, str]:
    """Nutzbare Geräusche: {key: Beschreibung} – nur geprüfte Dateien."""
    idx = index()
    return {k: LIBRARY[k][0] for k, v in idx.items() if v.get("ok") and k in LIBRARY and (DIR / f"{k}.mp3").exists()}


def path(key: str) -> Path | None:
    p = DIR / f"{key}.mp3"
    return p if key in available() and p.exists() else None


def build(force: bool = False) -> dict:
    DIR.mkdir(parents=True, exist_ok=True)
    idx = index()
    for key, (desc, sec) in LIBRARY.items():
        if not force and idx.get(key, {}).get("ok"):
            continue
        for attempt in range(3):
            raw = DIR / f"_{key}_raw.mp3"
            fal.sound_effects(f"{desc}, {_NO_VOICE}", raw, seconds=max(0.5, sec))
            _clean(raw, DIR / f"{key}.mp3")
            level(DIR / f"{key}.mp3")
            raw.unlink(missing_ok=True)
            r = gemini.text_json(RATING_PROMPT.format(desc=desc), "Answer ONLY with valid JSON.", temperature=0.1,
                                 model=config.CRITIC_MODEL, media=[("audio/mpeg", (DIR / f"{key}.mp3").read_bytes())])
            ok = (bool(r.get("matches")) and not r.get("has_voice_or_babble") and not r.get("harsh_or_shrill")
                  and int(r.get("toddler_friendly", 0)) >= 8)
            idx[key] = {"ok": ok, "attempt": attempt + 1, **r}
            print(f"{key:13s} Versuch {attempt + 1}: {'OK ' if ok else 'neu'} {r.get('toddler_friendly')}/10 – "
                  f"{r.get('description', '')}")
            INDEX.write_text(json.dumps(idx, indent=1, ensure_ascii=False))
            if ok:
                break
        if not idx[key]["ok"]:
            (DIR / f"{key}.mp3").unlink(missing_ok=True)
    return idx


if __name__ == "__main__":
    import sys
    if "--level" in sys.argv:   # vorhandene Dateien neu auf einheitliche Lautstärke bringen
        for k in available():
            level(DIR / f"{k}.mp3")
        print("Lautstärke angeglichen:", ", ".join(available()))
        sys.exit(0)
    costs.start(config.BUILD / "sfx_library_costs.json")
    build(force="--force" in sys.argv)
    print("Nutzbar:", ", ".join(available()))
    print(costs.report())
