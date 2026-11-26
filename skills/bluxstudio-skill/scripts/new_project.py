#!/usr/bin/env python3
"""Set up a /camel edit: one HyperFrames project folder per footage.

    python new_project.py "<footage file>" <slug>

Creates _hyperframes/<slug>/ next to the other compositions, with
  index.html            the Timeline 1 reference, already pointed at this footage,
                        its duration and fps, with asset_motion.js pasted in
                        (captions, route, CTA and the ILLUS assets still to be written)
  assets/footage/main.* the footage (re-encoded only if it is not 1080x1920 or its
                        keyframes are more than ~1 s apart, which freezes seeks)
  assets/fonts, sfx     Thmanyah Sans, the 6 sound accents (assets/img is filled by asset_lib.py place)
  .work/audio.wav       16 kHz mono, for transcribe.py / measure_windows.py
  .work/sheet.jpg       a contact sheet (1 frame / 2 s) to see the framing
and copies the local u2net_human_seg model into the HyperFrames cache so
`npx hyperframes remove-background` never has to download it.
Prints a JSON summary at the end.
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys

SKILL = pathlib.Path(__file__).resolve().parents[1]
ROOT = pathlib.Path(__file__).resolve().parents[4]
HF = ROOT / "_hyperframes"


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        sys.stderr.write(p.stdout + p.stderr)
        raise SystemExit(f"failed: {' '.join(map(str, cmd[:5]))} ...")
    return p.stdout


def probe(path):
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
               "-show_entries", "stream=width,height,r_frame_rate,nb_read_packets",
               "-show_entries", "format=duration", "-of", "json", str(path)])
    d = json.loads(out)
    s = d["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    fps = float(num) / float(den)
    frames = int(s.get("nb_read_packets") or 0)
    keys = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-skip_frame", "nokey",
                "-show_entries", "frame=pts_time", "-of", "csv=p=0", str(path)]).split()
    keys = [float(k.strip(",")) for k in keys if k.strip(",")]
    gap = max((b - a for a, b in zip(keys, keys[1:])), default=0.0)
    return {"w": s["width"], "h": s["height"], "fps": fps, "fps_str": s["r_frame_rate"],
            "frames": frames, "format_duration": float(d["format"]["duration"]), "max_key_gap": gap}


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    src = pathlib.Path(sys.argv[1]).resolve()
    slug = re.sub(r"[^a-z0-9_-]+", "-", sys.argv[2].lower()).strip("-")
    if not src.exists():
        raise SystemExit(f"footage not found: {src}")
    proj = HF / slug
    if (proj / "index.html").exists():
        raise SystemExit(f"{proj} already exists; pick another slug or edit it in place")
    for sub in ["assets/footage", "assets/fonts", "assets/img", "assets/sfx", "renders", ".work"]:
        (proj / sub).mkdir(parents=True, exist_ok=True)

    info = probe(src)
    fps_i = round(info["fps"])
    dst = proj / "assets" / "footage" / ("main" + src.suffix.lower())
    needs_scale = (info["w"], info["h"]) != (1080, 1920)
    needs_gop = info["max_key_gap"] > 1.05
    if needs_scale or needs_gop:
        dst = dst.with_suffix(".mp4")
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,format=yuv420p"
        print(f"re-encoding footage (scale={needs_scale}, keyframe gap {info['max_key_gap']:.2f}s)")
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-vf", vf,
             "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-g", str(fps_i),
             "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2",
             "-movflags", "+faststart", str(dst)])
        info = {**probe(dst), "reencoded": True}
    else:
        shutil.copy2(src, dst)
        info["reencoded"] = False

    # duration = whole frames, so the render never ends on a black frame
    dur = round((info["frames"] / info["fps"]) if info["frames"] else info["format_duration"] - 1 / info["fps"], 3)

    shutil.copy2(SKILL / "assets" / "thmanyah-sans-black.otf", proj / "assets" / "fonts")
    for f in (SKILL / "assets" / "sfx").glob("*.mp3"):
        shutil.copy2(f, proj / "assets" / "sfx")

    html = (SKILL / "assets" / "reference.html").read_text(encoding="utf-8")
    html = html.replace("assets/footage/t1.mov", f"assets/footage/{dst.name}")
    html = html.replace("assets/footage/t1_cutout.webm", "assets/footage/main_cutout.webm")
    html = html.replace('data-composition-id="t1"', f'data-composition-id="{slug}"')
    html = html.replace('const ID = "t1";', f'const ID = "{slug}";')
    html = html.replace('data-duration="29.458"', f'data-duration="{dur}"')
    html = html.replace("const DUR = 29.458;", f"const DUR = {dur};")
    html = html.replace('data-fps="24"', f'data-fps="{fps_i}"')
    html = html.replace("/*ASSET-MOTION*/", (SKILL / "assets" / "asset_motion.js").read_text(encoding="utf-8-sig"))
    (proj / "index.html").write_text(html, encoding="utf-8")

    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(dst), "-vn",
         "-ac", "1", "-ar", "16000", str(proj / ".work" / "audio.wav")])
    step = max(1.0, dur / 16)
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(dst),
         "-vf", f"fps=1/{step:.3f},scale=216:384,tile=8x2", "-frames:v", "1",
         str(proj / ".work" / "sheet.jpg")])

    home = pathlib.Path.home()
    model_src = home / ".rembg" / "models" / "u2net_human_seg" / "u2net_human_seg.onnx"
    model_dst = home / ".cache" / "hyperframes" / "background-removal" / "models" / "u2net_human_seg.onnx"
    model = "cached" if model_dst.exists() else "missing"
    if not model_dst.exists() and model_src.exists():
        model_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(model_src, model_dst)
        model = "copied from ~/.rembg"

    print(json.dumps({
        "project": str(proj), "footage": str(dst), "duration": dur, "fps": fps_i,
        "frames": info["frames"], "size": f"{info['w']}x{info['h']}",
        "reencoded": info["reencoded"], "matte_model": model,
        "audio": str(proj / ".work" / "audio.wav"), "sheet": str(proj / ".work" / "sheet.jpg"),
        "next": "cd into the project, start remove-background, transcribe, then rewrite T_BODY/T_CTA and CH in "
                "index.html; asset_lib.py plan + place write the user's assets into ILLUS",
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
