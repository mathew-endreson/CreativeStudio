#!/usr/bin/env python3
"""Word-timed Arabic (Darija) transcript with faster-whisper large-v3-turbo.

    python transcribe.py <audio.wav> [--out words.json] [--slices 0.2-3.1 3.1-7.6 ...]

Pass the 16 kHz mono wav made by new_project.py. Without --slices it transcribes
the whole file and writes JSON; with --slices it re-transcribes each range on its
own (prints absolute times) - use that to double-check wording and timing of
unclear stretches.

The wav is read with numpy and handed to the model as an array, because this
machine's PyAV is too new for faster-whisper's own decoder. CUDA lacks cublas
here, so it falls back to CPU int8 (fine: ~30 s of audio takes well under a minute).
"""
import argparse
import json
import wave

import numpy as np
from faster_whisper import WhisperModel

MODEL = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
PROMPT = "عسل شوك الإبل، إي بوكس، الكبد، التوصيل لجميع الولايات، طلبية"


def load_model():
    try:
        m = WhisperModel(MODEL, device="cuda", compute_type="float16")
        segs, _ = m.transcribe(np.zeros(16000, np.float32), language="ar")
        list(segs)  # segments are lazy: consume them so a missing CUDA lib fails here
        return m
    except Exception as e:  # noqa: BLE001
        print(f"(cuda unavailable: {str(e)[:80]}; using cpu)")
        return WhisperModel(MODEL, device="cpu", compute_type="int8")


def words_of(model, audio, offset, prompt):
    segs, _ = model.transcribe(audio, language="ar", word_timestamps=True, beam_size=5,
                               condition_on_previous_text=False, initial_prompt=prompt)
    out = []
    for s in segs:
        out.append({"start": round(offset + s.start, 3), "end": round(offset + s.end, 3), "text": s.text.strip(),
                    "words": [{"w": w.word.strip(), "s": round(offset + w.start, 3),
                               "e": round(offset + w.end, 3), "p": round(w.probability, 2)} for w in s.words]})
    return out


def show(segs):
    for s in segs:
        print(f"{s['start']:6.2f}-{s['end']:6.2f}  {s['text']}")
        print("    " + " ".join(f"{w['w']}[{w['s']:.2f}-{w['e']:.2f}]" for w in s["words"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--out")
    ap.add_argument("--slices", nargs="*", default=[])
    ap.add_argument("--prompt", default=PROMPT)
    a = ap.parse_args()
    with wave.open(a.wav, "rb") as wf:
        sr = wf.getframerate()
        x = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    if sr != 16000:
        raise SystemExit("expected a 16 kHz mono wav (new_project.py writes .work/audio.wav)")
    model = load_model()
    if not a.slices:
        segs = words_of(model, x, 0.0, a.prompt)
        show(segs)
        if a.out:
            with open(a.out, "w", encoding="utf-8") as f:
                json.dump(segs, f, ensure_ascii=False, indent=1)
        return
    for sl in a.slices:
        s0, s1 = (float(v) for v in sl.split("-"))
        print(f"== {s0:.2f}-{s1:.2f}")
        show(words_of(model, x[int(s0 * 16000):int(s1 * 16000)], s0, None))


if __name__ == "__main__":
    main()
