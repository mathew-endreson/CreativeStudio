#!/usr/bin/env python3
"""Loudness-match a HyperFrames render and verify the delivery file.

    python finalize.py <raw render.mp4> "<output.mp4>" [--target -15] [--sheet sheet.jpg] [--at 1.5,9,20,28]

Measures the render's integrated loudness, applies the gain that lands it on
--target LUFS (default -15, like the other EBOX ads) behind a -1 dBFS limiter,
copies the video stream untouched, then reports size/duration/codec, the final
loudness and peak, any black frames, and writes a 4-frame sample sheet.
"""
import argparse
import json
import re
import subprocess


def ff(args):
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stderr


def loudness(path):
    err = ff(["-i", path, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"])
    summary = err[err.rfind("Summary:"):]
    i = float(re.search(r"I:\s+(-?[\d.]+) LUFS", summary).group(1))
    pk = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
    return i, (float(pk.group(1)) if pk and pk.group(1) != "-inf" else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("out")
    ap.add_argument("--target", type=float, default=-15.0)
    ap.add_argument("--sheet")
    ap.add_argument("--at", default="")
    a = ap.parse_args()

    i0, _ = loudness(a.raw)
    gain = max(-12.0, min(12.0, a.target - i0))
    # The limiter caps samples; the AAC encode can still overshoot between them by 0.5-1.5 dB
    # depending on the content. Start at -1.5 dBFS and lower the ceiling until the true peak is <= -1.
    limit = 0.84
    for _ in range(3):
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", a.raw,
                        "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy",
                        "-af", f"volume={gain:.2f}dB,alimiter=limit={limit:.3f}:level=disabled",
                        "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2",
                        "-movflags", "+faststart", a.out], check=True)
        i1, pk = loudness(a.out)
        if pk is None or pk <= -1.0:
            break
        limit *= 10 ** ((-1.1 - pk) / 20)
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_name,width,height,r_frame_rate",
         "-of", "json", a.out], capture_output=True, text=True).stdout)
    black = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)",
                       ff(["-i", a.out, "-vf", "blackdetect=d=0.1:pix_th=0.05", "-an", "-f", "null", "-"]))
    dur = float(probe["format"]["duration"])
    if a.sheet:
        times = [float(t) for t in a.at.split(",") if t] or [dur * f for f in (0.08, 0.35, 0.65, 0.93)]
        sel = "+".join(f"lt(prev_pts*TB\\,{t:.3f})*gte(pts*TB\\,{t:.3f})" for t in times)
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", a.out,
                        "-vf", f"select='{sel}',scale=270:480,tile={len(times)}x1",
                        "-fps_mode", "passthrough", "-frames:v", "1", a.sheet], check=True)
    v = next(s for s in probe["streams"] if s.get("width"))
    print(json.dumps({
        "out": a.out, "duration": round(dur, 3), "size_mb": round(int(probe["format"]["size"]) / 1e6, 2),
        "video": f"{v['codec_name']} {v['width']}x{v['height']} @ {v['r_frame_rate']}",
        "loudness_before": i0, "gain_db": round(gain, 2), "loudness_after": i1, "peak_dbfs": pk,
        "black_frames": black, "sheet": a.sheet,
    }, indent=1))


if __name__ == "__main__":
    main()
