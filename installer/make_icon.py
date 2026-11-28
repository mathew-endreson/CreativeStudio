"""Draw the app icon source (desktop/app-icon.png, 1024 px) with Pillow: the CreativeStudio mark (two rounded bars,
the lower one an open "E", and the purple dot) on the light rounded tile, the same geometry as the UI's BrandMark in
desktop/src/brand.tsx (a 200-unit grid scaled by 5.12). Then `npm run tauri icon app-icon.png` in desktop/ writes
every size into src-tauri/icons/."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "desktop" / "app-icon.png"
S = 1024
K = S / 200  # the brand grid
TILE = (242, 242, 245, 255)
GLYPH = (42, 42, 46, 255)
DOT = (155, 61, 200, 255)

img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
rr = lambda x0, y0, x1, y1, r, fill: d.rounded_rectangle((x0 * K, y0 * K, x1 * K - 1, y1 * K - 1), radius=r * K, fill=fill)
rr(0, 0, 200, 200, 46, TILE)
rr(36, 36, 120, 70, 17, GLYPH)        # the top bar
d.ellipse(((152 - 18) * K, (53 - 18) * K, (152 + 18) * K, (53 + 18) * K), fill=DOT)
rr(36, 84, 164, 118, 17, GLYPH)       # the E: upper arm
rr(36, 132, 164, 166, 17, GLYPH)      # lower arm
rr(36, 84, 80, 166, 17, GLYPH)        # spine
img.save(OUT)
print(OUT)
