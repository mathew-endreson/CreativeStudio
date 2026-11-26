"""Frame-exact multi-segment join (generalises remix_join.py).

    python multi_join.py <spec.json> <out> [--alpha]

spec: {"sources": {"v1": "path.mp4", ...},            # with --alpha: {"v1": "cutout.webm", ...}
       "segments": [{"src": "v1", "a0": 0, "a1": 5.4667, "v0": null, "v1": 5.3667}, ...]}
a0/a1 = the segment's span (audio, and total picture length). v0/v1 = optional picture range inside it;
the picture is padded by cloning its first/last frame to fill [a0, a1] (hides flashes / stray captions under the
camel whip). All times are snapped to whole frames at 30 fps so audio and picture never drift across joins.
--alpha: picture only, VP9 with alpha (for the speaker cutout), same frame-exact cuts.
"""
import json, subprocess, sys

spec = json.load(open(sys.argv[1], encoding="utf-8"))
out = sys.argv[2]
alpha = "--alpha" in sys.argv
F = 30
fr = lambda t: int(round(t * F))
names = list(spec["sources"])
inputs = []
for n in names:
    if alpha:
        inputs += ["-c:v", "libvpx-vp9"]
    inputs += ["-i", spec["sources"][n]]
g, labels, t, joins = [], [], 0, []
for i, s in enumerate(spec["segments"]):
    k = names.index(s["src"])
    A0, A1 = fr(s["a0"]), fr(s["a1"])
    V0 = fr(s["v0"]) if s.get("v0") is not None else A0
    V1 = fr(s["v1"]) if s.get("v1") is not None else A1
    pre, post = V0 - A0, A1 - V1
    pad = f",tpad=start={pre}:start_mode=clone:stop={post}:stop_mode=clone" if (pre or post) else ""
    fmt = ",format=yuva420p" if alpha else ""
    g.append(f"[{k}:v]trim=start_frame={V0}:end_frame={V1},setpts=PTS-STARTPTS{fmt}{pad}[v{i}]")
    labels.append(f"[v{i}]")
    if not alpha:
        n = (A1 - A0) * 1600
        g.append(f"[{k}:a]atrim=start_sample={A0 * 1600}:end_sample={A1 * 1600},asetpts=PTS-STARTPTS,"
                 f"afade=t=in:d=0.02,afade=t=out:st={(A1 - A0) / F - 0.02:.4f}:d=0.02[a{i}]")
        labels.append(f"[a{i}]")
    t += (A1 - A0)
    joins.append(round(t / F, 4))
g.append("".join(labels) + f"concat=n={len(spec['segments'])}:v=1:a={0 if alpha else 1}" + ("[v]" if alpha else "[v][a]"))
cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex", ";".join(g), "-map", "[v]"]
if alpha:
    cmd += ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "28", "-g", "30", "-auto-alt-ref", "0",
            "-row-mt", "1", "-an", out]
else:
    cmd += ["-map", "[a]", "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-g", "30", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", out]
subprocess.run(cmd, check=True)
print(f"joins at {joins[:-1]}  total {joins[-1]:.4f}s ({t} frames) -> {out}")
