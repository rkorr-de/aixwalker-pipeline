"""Lyria-Testprompt v4 (Rolf 20.10.2026): weicher, verträumter Sub-Tone-Tenorsaxophon, Prompt wörtlich."""
PROMPT = ("Audiophile high-fidelity recording, crystal clear pristine instrument separation, wide stereo imaging. Ultra-quiet, intensely intimate, and subtly dreamy modern chillhop and Tokyo cafe jazz fusion. Extremely sparse, minimalist, and low volume arrangement with high dynamic range. The main focus is an exquisitely soft, muted, and velvety tenor saxophone played in a gentle sub-tone that borders on a whisper, lending a wistful, dreamy, and floating quality to the melody. Mixed cleanly with no muddy frequencies, completely avoiding any harshness or brassiness. Very minimal accompaniment: floating, highly isolated single notes on a soft felt piano, a distinct deep warm sub-bass, and a modern, slow lo-fi drum groove with a muffled kick and soft brushed rimshot. Intimate close-mic mixing with a delicate, warm, dreamy micro-ambiance and distinct discrete panning for each instrument, creating a very close, private, and nostalgic late-night aesthetic. Deep focus, soothing background music, strictly instrumental, no vocals, master-quality audio.")

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from pipeline import lyria
    out = Path("build/lyria-test-v4"); out.mkdir(parents=True, exist_ok=True)
    for i in (1, 2):
        p = lyria.generate_track(PROMPT, out / f"testsong_v4_{i}.mp3")
        print(p, p.stat().st_size)
