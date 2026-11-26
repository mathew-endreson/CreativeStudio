#!/usr/bin/env python3
"""Put new assets next to the reference set, on white and on dark, so you can
judge at a glance whether they belong to the same family.

Usage
  python contact_sheet.py SHEET.png NEW1.webp [NEW2.webp ...] [--refs DIR]

Each image gets two tiles (white | dark). References come first, labelled REF.
Open SHEET.png afterwards and look at it.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw

TILE = 300
PAD = 16


def tiles(path, label):
    im = Image.open(path).convert("RGBA")
    im.thumbnail((TILE - 2 * PAD, TILE - 2 * PAD - 18))
    out = []
    for bg, fg in [((255, 255, 255, 255), (90, 90, 90)), ((30, 30, 30, 255), (200, 200, 200))]:
        t = Image.new("RGBA", (TILE, TILE), bg)
        t.alpha_composite(im, ((TILE - im.width) // 2, 18 + (TILE - 18 - im.height) // 2))
        ImageDraw.Draw(t).text((8, 4), f"{label}  {Path(path).stem}"[:42], fill=fg)
        out.append(t)
    return out


def main():
    here = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser()
    p.add_argument("sheet")
    p.add_argument("images", nargs="+")
    p.add_argument("--refs", default=str(here / "assets" / "refs"))
    p.add_argument("--no-refs", action="store_true", help="only show the new images")
    args = p.parse_args()

    refs = [] if args.no_refs else sorted(Path(args.refs).glob("*.webp"))
    pairs = [tiles(r, "REF") for r in refs] + [tiles(i, "NEW") for i in args.images]
    cols = 2  # pairs per row -> 4 tiles per row
    rows = (len(pairs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 2 * TILE, rows * TILE), (128, 128, 128))
    for i, (light, dark) in enumerate(pairs):
        x = (i % cols) * 2 * TILE
        y = (i // cols) * TILE
        sheet.paste(light.convert("RGB"), (x, y))
        sheet.paste(dark.convert("RGB"), (x + TILE, y))
    Path(args.sheet).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.sheet)
    print(f"saved {args.sheet} ({len(refs)} refs, {len(args.images)} new)")


if __name__ == "__main__":
    main()
