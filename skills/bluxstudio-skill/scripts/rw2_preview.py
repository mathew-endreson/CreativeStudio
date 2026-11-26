#!/usr/bin/env python3
"""Pull the embedded JPEG preview out of a Panasonic .RW2 (no RAW decoder needed).

    python rw2_preview.py <photo.RW2> <out.jpg>

Scans for every JPEG stream (FFD8FF ... FFD9) inside the file and keeps the largest one that opens,
applying its EXIF rotation.
"""
import io, sys
from PIL import Image, ImageOps

src, out = sys.argv[1], sys.argv[2]
data = open(src, "rb").read()
best = None
pos = 0
while True:
    s = data.find(b"\xff\xd8\xff", pos)
    if s < 0:
        break
    e = data.find(b"\xff\xd9", s)
    while e > 0:
        try:
            im = Image.open(io.BytesIO(data[s:e + 2]))
            im.load()
            if best is None or im.width * im.height > best.width * best.height:
                best = im
            break
        except Exception:
            e = data.find(b"\xff\xd9", e + 2)
    pos = s + 3
if best is None:
    raise SystemExit("no embedded JPEG found")
best = ImageOps.exif_transpose(best)
best.save(out, quality=95)
print(f"{out}: {best.width}x{best.height}")
