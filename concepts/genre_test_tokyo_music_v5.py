"""Lyria-Testprompt v5 (Rolf 21.10.2026): gedämpfte Trompete (Filz-Bucket-Mute), Prompt wörtlich. Nur Hörproben."""
PROMPT = ("Audiophile high-fidelity recording, crystal clear pristine instrument separation, wide stereo imaging. Ultra-quiet and intensely intimate modern chillhop and Tokyo cafe jazz fusion. Extremely sparse, minimalist, and low volume arrangement with high dynamic range. Featured is an exquisitely soft, deeply muted trumpet played with a warm felt bucket mute, bordering on a gentle whisper. Smooth, velvety, and pure trumpet tone, mixed cleanly and gently with no muddy frequencies, completely avoiding any brassy harshness, piercing highs, roughness, or air noise. Very minimal accompaniment: highly isolated single notes on a felt piano, a distinct deep warm sub-bass, and a modern, slow lo-fi drum groove with a muffled kick and soft dry rimshot. The mix is completely dry with almost zero reverb, distinct discrete panning for each instrument, creating a very close, private, and late-night aesthetic. Deep focus, soothing background music, strictly instrumental, no vocals, master-quality audio.")

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from pipeline import lyria
    out = Path("build/lyria-test-v5"); out.mkdir(parents=True, exist_ok=True)
    for i in (1, 2):
        p = lyria.generate_track(PROMPT, out / f"testsong_v5_{i}.mp3")
        print(p, p.stat().st_size)
