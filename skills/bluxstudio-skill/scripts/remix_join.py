"""Join hook (0 -> hook_end of video A) + body (body_start -> end of video B) into one clip.

    python nf_join.py <A.mp4> <hook_end> <B.mp4> <body_start> <out.mp4> [hook_video_end]

30 fps, 1 s keyframes (HyperFrames seeks cleanly), CRF 14, 20 ms audio fades at the
join so there is no click. Prints the join time and total duration.
hook_video_end: when the hook's own flash starts before its last word ends, end the
picture there and hold that frame until hook_end (the camel whip + blur hides the hold).
"""
import subprocess, sys

a, ha, b, bs, out = sys.argv[1], float(sys.argv[2]), sys.argv[3], float(sys.argv[4]), sys.argv[5]
hv = float(sys.argv[6]) if len(sys.argv) > 6 else ha
hold = max(0.0, ha - hv)
bd = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", b],
                          capture_output=True, text=True).stdout)
body_len = bd - bs - 1 / 30  # drop the very last frame to avoid a short tail
v0 = (f"[0:v]trim=0:{hv:.3f},setpts=PTS-STARTPTS,fps=30,tpad=stop_mode=clone:stop_duration={hold:.3f},trim=0:{ha:.3f}[v0];"
      if hold > 0 else f"[0:v]trim=0:{ha:.3f},setpts=PTS-STARTPTS,fps=30[v0];")
g = (v0 +
     f"[1:v]trim={bs:.3f}:{bs + body_len:.3f},setpts=PTS-STARTPTS,fps=30[v1];"
     f"[0:a]atrim=0:{ha:.3f},asetpts=PTS-STARTPTS,afade=t=out:st={ha - 0.02:.3f}:d=0.02[a0];"
     f"[1:a]atrim={bs:.3f}:{bs + body_len:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02[a1];"
     f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]")
subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", a, "-i", b, "-filter_complex", g,
                "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-g", "30",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2",
                "-movflags", "+faststart", out], check=True)
print(f"join at {ha:.3f}s  body {bs:.3f}->{bd:.3f}  total {ha + body_len:.3f}s -> {out}")
