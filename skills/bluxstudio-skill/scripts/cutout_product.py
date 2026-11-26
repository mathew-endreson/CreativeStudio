#!/usr/bin/env python3
"""Cut a product off a plain studio background -> RGBA PNG cropped to the product.

    python cutout_product.py <photo.jpg> <out.png> [--preview preview.jpg] [--symmetric]

Use it to turn a product photo the user hands over into an asset (a transparent cut-out
for the upload folder; assets/jar.png is the EBOX DZ 500 g jar made this way). GrabCut seeded by a rough box plus the
near-white border; --symmetric rebuilds every row as a span mirrored about the
product's vertical axis, which fixes white labels melting into a white backdrop
(use it for jars and bottles shot straight on).
"""
import argparse

import cv2
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("out")
ap.add_argument("--preview")
ap.add_argument("--symmetric", action="store_true")
a = ap.parse_args()

img = cv2.imread(a.src)
h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
ys, xs = np.where(gray < 235)
x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
pad = 12
bx, by = max(0, x0 - pad), max(0, y0 - pad)
rect = (bx, by, min(w, x1 + pad) - bx, min(h, y1 + pad) - by)

mask = np.zeros((h, w), np.uint8)
bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
cv2.grabCut(img, mask, rect, bgd, fgd, 8, cv2.GC_INIT_WITH_RECT)
flood = np.zeros((h + 2, w + 2), np.uint8)
for seed in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
    cv2.floodFill(img.copy(), flood, seed, (0, 0, 0), (6, 6, 6), (6, 6, 6),
                  cv2.FLOODFILL_FIXED_RANGE | cv2.FLOODFILL_MASK_ONLY | (255 << 8))
mask[(flood[1:-1, 1:-1] > 0) & (mask != cv2.GC_FGD)] = cv2.GC_BGD
cv2.grabCut(img, mask, None, bgd, fgd, 4, cv2.GC_INIT_WITH_MASK)

fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
n, lab, stats, _ = cv2.connectedComponentsWithStats(fg)
fg = np.where(lab == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA])), 255, 0).astype(np.uint8)
cnts, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
fg = np.zeros_like(fg)
cv2.drawContours(fg, cnts, -1, 255, -1)

if a.symmetric:
    rows = [y for y in range(h) if fg[y].any()]
    L = {y: int(np.argmax(fg[y] > 0)) for y in rows}
    R = {y: int(w - 1 - np.argmax(fg[y][::-1] > 0)) for y in rows}
    c = float(np.median([(L[y] + R[y]) / 2 for y in rows]))
    hw = np.array([max(c - L[y], R[y] - c) for y in rows])
    hw = np.array([np.median(hw[max(0, i - 3):i + 4]) for i in range(len(hw))])
    fg = np.zeros_like(fg)
    for y, half in zip(rows, hw):
        fg[y, int(round(c - half)):int(round(c + half)) + 1] = 255

fg = cv2.erode(fg, np.ones((3, 3), np.uint8), 1)
alpha = cv2.GaussianBlur(fg, (5, 5), 0)
ys, xs = np.where(alpha > 8)
rgba = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
rgba[:, :, 3] = alpha
crop = rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
cv2.imwrite(a.out, crop)
print("cutout", crop.shape[1], "x", crop.shape[0], "->", a.out)

if a.preview:
    al = crop[:, :, 3:4].astype(np.float32) / 255

    def comp(bg):
        base = np.zeros_like(crop[:, :, :3], dtype=np.float32) + np.array(bg, np.float32)
        return (crop[:, :, :3] * al + base * (1 - al)).astype(np.uint8)

    cv2.imwrite(a.preview, np.hstack([comp((30, 25, 20)), comp((120, 170, 200))]))
