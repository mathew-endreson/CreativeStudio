#!/usr/bin/env python3
"""Upright, white-balance and cut out an offer packshot shot on a light backdrop.

    python offer_cutout.py <src.jpg> <out.png> [--rotate cw|ccw|none] [--crop l,t,r,b] [--preview p.jpg]

--crop is in fractions of the rotated image (drops tape / backdrop edges before cutting).
The backdrop is estimated from the border, scaled to near-white, then GrabCut (seeded by a
difference-from-backdrop mask) separates the products; the clear plastic bag keeps a soft edge.
Output: RGBA PNG cropped to the products, max 1400 px tall.
"""
import argparse
import cv2
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("out")
ap.add_argument("--rotate", default="cw")
ap.add_argument("--crop", default="0,0,0,0")
ap.add_argument("--preview")
ap.add_argument("--hull-x", type=float, default=None,
                help="replace the mask right of this x fraction by its convex hull (clean pouch shape for a clear bag)")
ap.add_argument("--smooth", type=int, default=0, help="round ragged outlines: closing + blur radius in px")
ap.add_argument("--smooth-boxes", default="", help="limit smoothing to these fractional boxes 'x0,y0,x1,y1;...' (keeps jars sharp)")
a = ap.parse_args()

img = cv2.imread(a.src)
if a.rotate == "cw":
    img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
elif a.rotate == "ccw":
    img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
s = 1600 / max(img.shape[:2])
img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
h, w = img.shape[:2]
l, t, r, b = (float(v) for v in a.crop.split(","))
img = img[int(t * h):h - int(b * h), int(l * w):w - int(r * w)]
h, w = img.shape[:2]

# white balance + exposure from the backdrop (border median)
border = np.concatenate([img[:20].reshape(-1, 3), img[-20:].reshape(-1, 3), img[:, :20].reshape(-1, 3), img[:, -20:].reshape(-1, 3)])
bg = np.median(border, axis=0)
img = np.clip(img.astype(np.float32) * (242.0 / np.maximum(bg, 1)), 0, 255)
# gentle contrast so the products don't look washed out
img = np.clip((img - 128) * 1.12 + 128 + 4, 0, 255).astype(np.uint8)

diff = np.abs(img.astype(np.int16) - np.array([244, 244, 244])).max(axis=2)
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
fg_hint = ((diff > 28) | (hsv[..., 1] > 40)).astype(np.uint8)
fg_hint = cv2.morphologyEx(fg_hint, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
ys, xs = np.nonzero(fg_hint)
x0, x1 = np.percentile(xs, [0.5, 99.5]).astype(int)
y0, y1 = np.percentile(ys, [0.5, 99.5]).astype(int)
pad = 25
rect = (max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad) - max(0, x0 - pad), min(h, y1 + pad) - max(0, y0 - pad))

mask = np.full((h, w), cv2.GC_BGD, np.uint8)
rx, ry, rw, rh = rect
mask[ry:ry + rh, rx:rx + rw] = cv2.GC_PR_BGD
mask[(fg_hint > 0)] = cv2.GC_PR_FGD
core = cv2.erode(fg_hint, np.ones((31, 31), np.uint8))
mask[(core > 0) & (diff > 45)] = cv2.GC_FGD
bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
cv2.grabCut(img, mask, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

# keep big blobs only, fill holes
n, lab, stats, _ = cv2.connectedComponentsWithStats(fg)
keep = np.zeros_like(fg)
for i in range(1, n):
    if stats[i, cv2.CC_STAT_AREA] > 0.01 * w * h:
        keep[lab == i] = 255
cnts, _ = cv2.findContours(keep, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
fg = np.zeros_like(keep)
cv2.drawContours(fg, cnts, -1, 255, -1)
fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
if a.smooth:
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (a.smooth * 2 + 1, a.smooth * 2 + 1))
    sm = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, k)
    sm = np.where(cv2.GaussianBlur(sm, (0, 0), a.smooth / 2) > 127, 255, 0).astype(np.uint8)
    if a.smooth_boxes:
        region = np.zeros_like(fg)
        for bx in a.smooth_boxes.split(";"):
            bx0, by0, bx1, by1 = (float(v) for v in bx.split(","))
            region[int(by0 * h):int(by1 * h), int(bx0 * w):int(bx1 * w)] = 1
        fg = np.where(region > 0, sm, fg).astype(np.uint8)
    else:
        fg = sm
if a.hull_x is not None:
    xs_cut = int(a.hull_x * w)
    part = np.zeros_like(fg)
    part[:, xs_cut:] = fg[:, xs_cut:]
    pts = cv2.findNonZero(part)
    if pts is not None:
        hull = cv2.convexHull(pts)
        region = np.zeros_like(fg)
        cv2.fillConvexPoly(region, hull, 255)
        region[:, :xs_cut] = 0
        fg = np.maximum(fg, region)
alpha =cv2.GaussianBlur(cv2.erode(fg, np.ones((3, 3), np.uint8)), (5, 5), 0)

ys, xs = np.nonzero(alpha > 8)
rgba = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
rgba[..., 3] = alpha
crop = rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
if crop.shape[0] > 1400:
    k = 1400 / crop.shape[0]
    crop = cv2.resize(crop, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
cv2.imwrite(a.out, crop)
print(a.out, crop.shape[1], "x", crop.shape[0])
if a.preview:
    al = crop[..., 3:4].astype(np.float32) / 255
    def comp(c):
        base = np.zeros_like(crop[..., :3], dtype=np.float32) + np.array(c, np.float32)
        return (crop[..., :3] * al + base * (1 - al)).astype(np.uint8)
    pv = np.hstack([comp((40, 32, 26)), comp((110, 150, 120))])
    k = 700 / pv.shape[0]
    cv2.imwrite(a.preview, cv2.resize(pv, None, fx=k, fy=k))
