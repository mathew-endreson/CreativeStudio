#!/usr/bin/env python3
"""Find the burned-in titles and cards in the top of a finished ad: when they are on screen and where.

    python remix_title_scan.py 1 2 3 4 5 6 8      -> writes remix_titles.json  {"V1": [[t0, t1, x0, y0, x1, y1], ...]}
                                                     (the camel honey ads in Desktop/New Footage, orange titles)
    python remix_title_scan.py --files t1=<a.mp4> t2=<b.mp4> [--kinds orange green white] [--out titles.json]
                                                  -> {"t1": [[t0, t1, x0, y0, x1, y1, kind], ...]}

Kinds (HSV on OpenCV's 0-180 hue scale, counted at 270x480):
  orange  hue 8-22, S > 150, V > 170 in the band y 120-640 (skin, jars and the table never get that saturated
          there). A title is ~20k px at full size (~1.3k here); warm background and skin stay under ~300.
  green   hue 40-80, S > 140, V > 150 in y 0-760: the Tanafous title boxes.
  white   S < 30, V > 225 in y 0-760: white cards (comment screenshots, product cards).
In warm, orange-lit shoots the lower edge of an orange box reads too low: check those frames by eye.
batch.py scan calls scan_titles() for every source of a batch.
"""
import json, pathlib, subprocess, sys
import cv2, numpy as np

FPS, S = 10, 4  # sample rate, downscale factor (270x480)
KINDS = {   # band (y0, y1 at full size), pixel threshold at 270x480, percentile trim, shortest window
    "orange": {"band": (120, 640), "thr": 700, "pct": (3, 97), "min": 0.3,
               "mask": lambda h: (h[..., 0] >= 8) & (h[..., 0] <= 22) & (h[..., 1] > 150) & (h[..., 2] > 170)},
    "green": {"band": (0, 760), "thr": 500, "pct": (2, 98), "min": 0.2,
              "mask": lambda h: (h[..., 0] >= 40) & (h[..., 0] <= 80) & (h[..., 1] > 140) & (h[..., 2] > 150)},
    "white": {"band": (0, 760), "thr": 2500, "pct": (2, 98), "min": 0.2,
              "mask": lambda h: (h[..., 1] < 30) & (h[..., 2] > 225)},
}


def scan_titles(path, kinds=("orange",)):
    """[[t0, t1, x0, y0, x1, y1, kind], ...] sorted by time, boxes in 1080x1920 pixels."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"fps={FPS},scale=270:480", "-f", "rawvideo",
                          "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, 480, 270, 3)
    res = []
    for kind in kinds:
        K = KINDS[kind]
        y_a, y_b = K["band"][0] // S, K["band"][1] // S
        hits = []
        for k, im in enumerate(fr):
            m = K["mask"](cv2.cvtColor(im[y_a:y_b], cv2.COLOR_BGR2HSV))
            if m.sum() > K["thr"]:
                ys, xs = np.nonzero(m)
                x0, x1 = np.percentile(xs, K["pct"])
                y0, y1 = np.percentile(ys, K["pct"])
                hits.append((k / FPS, x0 * S, (y0 + y_a) * S, x1 * S, (y1 + y_a) * S))
        wins = []
        for t, x0, y0, x1, y1 in hits:
            if wins and t - wins[-1][1] <= 0.25:
                w = wins[-1]
                wins[-1] = [w[0], t, min(w[2], x0), min(w[3], y0), max(w[4], x1), max(w[5], y1)]
            else:
                wins.append([t, t, x0, y0, x1, y1])
        res += [[round(w[0] - 0.1, 2), round(w[1] + 0.15, 2), *[int(v) for v in w[2:]], kind]
                for w in wins if w[1] - w[0] >= K["min"]]
    res.sort(key=lambda r: (r[0], r[1]))
    return res


def main():
    a = sys.argv[1:]
    if "--files" in a:
        def opt(name):
            if name not in a:
                return []
            i = a.index(name) + 1
            j = next((k for k in range(i, len(a)) if a[k].startswith("--")), len(a))
            return a[i:j]
        kinds = opt("--kinds") or list(KINDS)
        out = {}
        for item in opt("--files"):
            k, _, f = item.partition("=")
            out[k] = scan_titles(f, kinds)
            print(k)
            for r in out[k]:
                print("   ", r)
        if opt("--out"):
            pathlib.Path(opt("--out")[0]).write_text(json.dumps(out, indent=1), encoding="utf-8")
        return
    NF = pathlib.Path(r"C:\Users\EL ASSLI\Desktop\New Footage")
    H = pathlib.Path(__file__).resolve().parent
    out = {}
    for i in [int(x) for x in a]:
        f = next(NF.glob(f"*- V{i} -*.mp4"))
        out[f"V{i}"] = [w[:6] for w in scan_titles(f, ("orange",))]
        print(f"V{i}:", out[f"V{i}"])
    (H / "remix_titles.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
