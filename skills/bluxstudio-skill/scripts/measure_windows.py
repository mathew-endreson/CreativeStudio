#!/usr/bin/env python3
"""Measure speech windows in a source take, so cut points never land in silence.

    python measure_windows.py <wav or mp4> <from> <to> [--thr -32] [--gap 0.25]

Prints the speech runs (> thr dBFS, gaps shorter than --gap merged) inside the
range, plus any inner pause longer than 0.30 s. Windows are absolute seconds in
the source file, ready to paste into a clip's "win" entries.
"""
import subprocess
import sys
import numpy as np

args = [a for a in sys.argv[1:] if not a.startswith("--")]
opts = {}
for i, a in enumerate(sys.argv[1:]):
    if a.startswith("--"):
        opts[a[2:]] = sys.argv[i + 2]

src, a, b = args[0], float(args[1]), float(args[2])
thr = float(opts.get("thr", -32))
gap = float(opts.get("gap", 0.25))
HOP = 0.025

raw = subprocess.run(
    ["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", src,
     "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
    capture_output=True, check=True).stdout
x = np.frombuffer(raw, dtype=np.float32)
n = int(HOP * 16000)
frames = len(x) // n
rms = np.array([np.sqrt(np.mean(x[i * n:(i + 1) * n] ** 2) + 1e-12) for i in range(frames)])
db = 20 * np.log10(rms + 1e-12)
t = a + np.arange(frames) * HOP

voiced = db > thr
runs = []
i = 0
while i < frames:
    if voiced[i]:
        j = i
        while j + 1 < frames and voiced[j + 1]:
            j += 1
        runs.append([t[i], t[j] + HOP])
        i = j + 1
    else:
        i += 1
merged = []
for r in runs:
    if merged and r[0] - merged[-1][1] < gap:
        merged[-1][1] = r[1]
    else:
        merged.append(r)

print(f"range {a:.2f}-{b:.2f}  thr {thr:.0f} dB  gap {gap:.2f} s")
print("speech windows:")
for s, e in merged:
    print(f"  ({s:.2f}, {e:.2f})   {e - s:5.2f}s")
print("inner pauses >0.30 s:")
for (s1, e1), (s2, e2) in zip(merged, merged[1:]):
    if s2 - e1 > 0.30:
        print(f"  {e1:.2f} -> {s2:.2f}   {s2 - e1:5.2f}s")
if merged:
    print(f"first sound {merged[0][0]:.2f}  last sound {merged[-1][1]:.2f}")
