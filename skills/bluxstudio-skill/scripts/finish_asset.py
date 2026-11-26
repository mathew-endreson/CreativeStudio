#!/usr/bin/env python3
"""Turn a raw image into a finished asset in the house orange style.

Pipeline
  1. background -> transparent (colour-to-alpha against the detected
     background colour, flood-filled from the borders so light highlights
     inside the subject stay opaque; neutral grey haze/shadows are dropped)
  2. palette lock: every pixel is re-coloured by its luminance onto the
     orange ramp measured from the reference images, so hue drift
     (red, yellow, pink, brown) from the generator disappears
  3. trim to the subject and centre it on the standard canvas
     (square 1254x1254 for organs/objects, wide 1536x1024 for people/heads)
  4. zero the RGB of fully transparent pixels and save WebP (+ optional PNG)
  5. print a style report you can check against the reference numbers

Usage
  python finish_asset.py RAW_IMAGE OUT.webp [--canvas square|wide]
         [--fill 0.88] [--bg auto|remove|keep] [--method flood|rembg]
         [--strength 1.0] [--match-brightness] [--mirror] [--png]

Needs: numpy, pillow, scipy (rembg only for --method rembg).
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

# Luminance -> colour stops. Measured from the four reference images: the
# median colour of all opaque pixels in each 16-level luminance band, plus
# a dark and a light end stop. Each stop's own luminance equals its key, so
# mapping an on-palette pixel returns (almost) the same pixel.
RAMP = [
    (0, (0x3A, 0x14, 0x00)),
    (46, (0x63, 0x23, 0x02)),
    (57, (0x8A, 0x27, 0x01)),
    (72, (0xA8, 0x33, 0x01)),
    (93, (0xCB, 0x46, 0x02)),
    (103, (0xDA, 0x4F, 0x01)),
    (123, (0xF1, 0x64, 0x01)),
    (135, (0xFB, 0x72, 0x01)),
    (150, (0xFC, 0x86, 0x03)),
    (166, (0xFC, 0x9A, 0x25)),
    (183, (0xFC, 0xAE, 0x47)),
    (197, (0xFB, 0xBE, 0x68)),
    (215, (0xFB, 0xD2, 0x99)),
    (231, (0xFB, 0xE4, 0xC6)),
    (241, (0xFC, 0xF0, 0xE1)),
    (255, (0xFF, 0xF8, 0xEE)),
]
CANVASES = {"square": (1254, 1254), "wide": (1536, 1024)}
LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
TARGET_MEDIAN_LUM = 133  # median luminance of opaque pixels across the references


def saturation(rgb):
    mx = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    return (mx - mn) / np.maximum(mx, 1)


def remove_background_flood(rgb, low=0.35, band=2, gray_cutoff=0.22):
    """Colour-to-alpha against the border colour, limited to the exterior."""
    border = np.concatenate([
        rgb[:3].reshape(-1, 3), rgb[-3:].reshape(-1, 3),
        rgb[:, :3].reshape(-1, 3), rgb[:, -3:].reshape(-1, 3),
    ])
    bg = np.median(border, axis=0)
    # JPEG/noise tolerance: differences this small are still background.
    tol = np.maximum(5.0, 3 * border.std(axis=0))

    diff = rgb - bg
    mag = np.maximum(np.abs(diff) - tol, 0)
    # A channel already near 255 (white background) has no room to get
    # brighter, so "brighter than bg" there is noise, not signal.
    up_room = 255 - bg - tol
    up = np.where((diff > 0) & (up_room >= 24), mag / np.maximum(up_room, 1), 0)
    down = np.where(diff < 0, mag / np.maximum(bg - tol, 1), 0)
    alpha = np.clip(np.maximum(up, down).max(axis=-1), 0, 1)
    alpha = np.where(alpha < 0.04, 0, alpha)

    fg = np.clip(bg + diff / np.maximum(alpha, 1e-3)[..., None], 0, 255)
    neutral = saturation(fg) < gray_cutoff

    # The exterior is whatever is reachable from the image border through
    # background-like pixels: nearly-background colour, or neutral haze.
    passable = (alpha < low) | (neutral & (alpha < 0.9))
    labels, _ = ndimage.label(passable)
    edge = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    exterior = np.isin(labels, edge[edge != 0])
    # Include the anti-aliased rim so edges are un-blended, not haloed.
    exterior |= ndimage.binary_dilation(exterior, iterations=band)

    a = np.where(exterior, alpha, 1.0)
    a = np.where(exterior & neutral, 0.0, a)
    out_rgb = np.where(exterior[..., None], fg, rgb)
    return out_rgb, a, bg


def remove_background_rembg(img):
    try:
        from rembg import remove
    except ImportError:
        sys.exit("rembg is not installed; use --method flood")
    cut = remove(img.convert("RGB")).convert("RGBA")
    arr = np.asarray(cut).astype(np.float32)
    return arr[..., :3], arr[..., 3] / 255.0


TARGET_HUE = 26.0  # median hue of the references, degrees
HUE_BAND = (14.0, 38.0)


def rgb_to_hsv(rgb):
    x = rgb / 255.0
    mx, mn = x.max(-1), x.min(-1)
    d = np.maximum(mx - mn, 1e-6)
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    return h, s, mx


def hsv_to_rgb(h, s, v):
    h = (h % 360) / 60
    i = np.floor(h).astype(int) % 6
    f = h - np.floor(h)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], -1) * 255


def normalize_hue(rgb, alpha):
    """Rotate hues so the subject's median hue matches the references, then
    clamp into the orange band. Keeps saturation and value, so a red-drifted
    render becomes orange without getting darker."""
    h, s, v = rgb_to_hsv(rgb)
    chroma = (alpha > 0.5) & (s > 0.35) & (v > 0.2)
    if not chroma.any():
        return rgb
    hh = np.where(h > 180, h - 360, h)  # reds near 360 count as slightly negative
    shift = TARGET_HUE - np.median(hh[chroma])
    hh = np.clip(hh + shift, *HUE_BAND)
    return hsv_to_rgb(hh, s, v)


def palette_lock(rgb, alpha, strength, match_brightness):
    rgb = normalize_hue(rgb, alpha)
    lum = rgb @ LUMA
    if match_brightness:
        opaque = alpha > 0.8
        if opaque.any():
            lum = np.clip(lum + (TARGET_MEDIAN_LUM - np.median(lum[opaque])), 0, 255)
    xs = np.array([s[0] for s in RAMP], np.float32)
    cols = np.array([s[1] for s in RAMP], np.float32)
    mapped = np.stack([np.interp(lum, xs, cols[:, c]) for c in range(3)], axis=-1)
    return rgb * (1 - strength) + mapped * strength


def frame(rgba, canvas, fill):
    a = rgba[..., 3]
    ys, xs = np.nonzero(a > 8)
    if len(xs) == 0:
        sys.exit("Nothing left after background removal - try --method rembg or --bg keep")
    crop = rgba[ys.min(): ys.max() + 1, xs.min(): xs.max() + 1]
    W, H = canvas
    ch, cw = crop.shape[:2]
    scale = min(W * fill / cw, H * fill / ch)
    size = (max(1, round(cw * scale)), max(1, round(ch * scale)))
    im = Image.fromarray(np.clip(crop, 0, 255).astype(np.uint8), "RGBA")
    # Resize premultiplied so transparent pixels don't bleed colour into edges.
    im = im.convert("RGBa").resize(size, Image.LANCZOS).convert("RGBA")
    out = Image.new("RGBA", canvas, (0, 0, 0, 0))
    out.alpha_composite(im, ((W - size[0]) // 2, (H - size[1]) // 2))
    return out


def report(img):
    arr = np.asarray(img).astype(np.float32)
    a = arr[..., 3]
    rgb = arr[..., :3]
    H, W = a.shape
    ys, xs = np.nonzero(a > 8)
    opaque = a > 200
    px = rgb[opaque] / 255.0
    mx, mn = px.max(1), px.min(1)
    d = np.maximum(mx - mn, 1e-6)
    r, g, b = px[:, 0], px[:, 1], px[:, 2]
    hue = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    sat = (mx - mn) / np.maximum(mx, 1e-6)
    chroma = (sat > 0.35) & (mx > 0.2)
    on_pal = ((hue >= 10) & (hue <= 40))[chroma].mean() if chroma.any() else 0
    lum = (rgb[opaque] @ LUMA)
    print(f"canvas            {W}x{H}")
    print(f"subject box       {(xs.max()-xs.min())/W:.0%} wide x {(ys.max()-ys.min())/H:.0%} tall "
          f"(refs: 85-93% of the limiting side)")
    print(f"opaque coverage   {opaque.mean():.0%} of canvas")
    print(f"median hue        {np.median(hue[chroma]):.0f} deg (refs 24-28)")
    print(f"on-palette pixels {on_pal:.1%} (want >= 97%)")
    print(f"median luminance  {np.median(lum):.0f} (refs 120-140; below = too dark, above = washed out)")
    print(f"semi-transparent  {((a > 10) & (a < 245)).mean():.1%} (refs <= 3%; much higher = halo/haze left)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input")
    p.add_argument("output", help="output path, .webp recommended")
    p.add_argument("--canvas", default="square", help="square | wide | WIDTHxHEIGHT")
    p.add_argument("--fill", type=float, default=0.88, help="fraction of the limiting canvas side the subject fills")
    p.add_argument("--bg", default="auto", choices=["auto", "remove", "keep"],
                   help="auto: remove only if the input has no transparency")
    p.add_argument("--method", default="flood", choices=["flood", "rembg"])
    p.add_argument("--strength", type=float, default=1.0, help="palette lock strength 0..1 (0 = off)")
    p.add_argument("--match-brightness", action="store_true",
                   help="shift luminance so the median matches the references")
    p.add_argument("--png", action="store_true", help="also write a PNG next to the output")
    p.add_argument("--mirror", action="store_true", help="flip horizontally (mode B subjects must face right)")
    args = p.parse_args()

    if args.canvas in CANVASES:
        canvas = CANVASES[args.canvas]
    else:
        w, h = args.canvas.lower().split("x")
        canvas = (int(w), int(h))

    src = Image.open(args.input)
    src.load()
    if args.mirror:
        src = src.transpose(Image.FLIP_LEFT_RIGHT)
    rgba = np.asarray(src.convert("RGBA")).astype(np.float32)
    has_alpha = (rgba[..., 3] < 250).mean() > 0.02

    if args.bg == "keep" or (args.bg == "auto" and has_alpha):
        rgb, alpha = rgba[..., :3], rgba[..., 3] / 255.0
        print("background        kept (input already transparent)")
    elif args.method == "rembg":
        rgb, alpha = remove_background_rembg(src)
        print("background        removed with rembg")
    else:
        rgb, alpha, bg = remove_background_flood(rgba[..., :3])
        print(f"background        removed (detected colour #{int(bg[0]):02X}{int(bg[1]):02X}{int(bg[2]):02X})")

    # GPT renders leave the subject at alpha ~253 and scatter alpha 1-5 noise
    # around it; snap both ends so solid is solid and empty is empty.
    alpha = np.where(alpha >= 0.97, 1.0, np.where(alpha <= 0.02, 0.0, alpha))

    if args.strength > 0:
        rgb = palette_lock(rgb, alpha, args.strength, args.match_brightness)

    out = np.dstack([np.clip(rgb, 0, 255), np.clip(alpha * 255, 0, 255)])
    img = frame(out, canvas, args.fill)

    arr = np.asarray(img).copy()
    arr[arr[..., 3] == 0, :3] = 0
    img = Image.fromarray(arr, "RGBA")

    dst = Path(args.output)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.suffix.lower() == ".png":
        img.save(dst, optimize=True)
    else:
        img.save(dst, "WEBP", quality=92, method=6)
    if args.png and dst.suffix.lower() != ".png":
        img.save(dst.with_suffix(".png"), optimize=True)
    print(f"saved             {dst}")
    report(img)


if __name__ == "__main__":
    main()
