#!/usr/bin/env python3
"""Write index.html for a remix WITH the user's assets animated in front of the speaker.

    python remix_broll.py <project dir> <beats.json>

beats.json:
{
  "id": "mix01-h10-b5", "t_body": 3.067, "dur": 34.7,
  "t_cta": 30.1, "t_jumps": [1.4],                              # optional (map_beats.py writes them)
  "sfx": [{"src": "pop.mp3", "t": 3.4, "vol": 0.14}],          # whoosh at the join is added automatically
  "beats": [ ... ]                                               # times are in the remix's own timeline
}

A beat is one asset the user uploaded (asset_lib.py place fills img / w / h / x / top from the library):
  {"kind": "asset", "lib": "<library id>", "img": "assets/img/lib-<id>.png", "w": 380, "h": 300, "x": 350, "top": 960,
   "in": 5.2, "out": 8.0, "keys": [5.6], "breathe": [6.1], "shake": [7.0]}
  keys = pop + light glint, breathe = slow swell, shake = shudder (asset_motion.js has the motion).
Beats without an img (the old /camel discs, liver, jar packshots, from batches made before Nov 26 2026) are
dropped with a note: that motion-graphic style is gone from the skill.
Needs assets/footage/main.mp4 and the pictures in assets/img (asset_lib.py place copies them there).
"""
import json
import pathlib
import sys

SKILL = pathlib.Path(__file__).resolve().parents[1]
proj, spec = pathlib.Path(sys.argv[1]), json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8-sig"))
T, DUR, ID = float(spec["t_body"]), float(spec["dur"]), spec["id"]

audio = [f'  <audio id="sw" class="clip" src="assets/sfx/whoosh-short.mp3" data-start="{T - 0.20:.2f}" data-duration="0.57" data-track-index="3" data-volume="0.32"></audio>']
lens = {"pop.mp3": 0.72, "sparkle.mp3": 1.8, "ping.mp3": 1.32, "click-soft.mp3": 0.37, "whoosh.mp3": 0.57, "whoosh-short.mp3": 0.57}
for k, s in enumerate(spec.get("sfx", [])):
    audio.append(f'  <audio id="s{k}" class="clip" src="assets/sfx/{s["src"]}" data-start="{s["t"]:.2f}" '
                 f'data-duration="{lens.get(s["src"], 1.0)}" data-track-index="{4 + k % 2}" data-volume="{s.get("vol", 0.14)}"></audio>')

beats = [b for b in spec["beats"] if b.get("img")]
dropped = [f'{b.get("kind", "?")} {b["in"]:.2f}' for b in spec["beats"] if not b.get("img")]
html = (SKILL / "assets" / "remix_broll_template.html").read_text(encoding="utf-8-sig")
motion = (SKILL / "assets" / "asset_motion.js").read_text(encoding="utf-8-sig")
T_CTA = spec.get("t_cta")  # optional: body -> CTA join (camel T2: punch, sweep left -> right, flash .50; add a whoosh in sfx)
html = (html.replace("{{ID}}", ID).replace("{{DUR}}", f"{DUR}").replace("{{T_BODY}}", f"{T}")
        .replace("{{T_CTA}}", "null" if T_CTA is None else f"{float(T_CTA)}")
        .replace("{{T_JUMPS}}", json.dumps([float(t) for t in spec.get("t_jumps", [])]))
        .replace("{{BEATS}}", json.dumps(beats, ensure_ascii=False, indent=1))
        .replace("{{AUDIO}}", "\n".join(audio))
        .replace("/*ASSET-MOTION*/", motion))
(proj / "index.html").write_text(html, encoding="utf-8")
missing = [p for p in ["assets/footage/main.mp4", *sorted({b["img"] for b in beats})] if not (proj / p).exists()]
print(f"wrote {proj / 'index.html'}  ({len(beats)} assets)" + (f"  MISSING: {missing}" if missing else ""))
if dropped:
    print(f"  dropped {len(dropped)} beat(s) with no picture (old disc / jar style): {', '.join(dropped)}")
