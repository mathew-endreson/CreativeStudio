"""Draw the app icon source (desktop/app-icon.png, 1024 px) with Pillow, then `npm run tauri icon app-icon.png`
in desktop/ writes every size into src-tauri/icons/. Replace the PNG with the real BluxTech logo when there is one."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "desktop" / "app-icon.png"
S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((0, 0, S - 1, S - 1), radius=220, fill=(194, 87, 12, 255))
# a soft highlight band
d.rounded_rectangle((60, 60, S - 61, S // 2), radius=180, fill=(226, 112, 32, 255))
d.rounded_rectangle((0, S // 2 - 90, S - 1, S - 1), radius=220, fill=(194, 87, 12, 255))
font = None
for name in ("seguibl.ttf", "segoeuib.ttf", "arialbd.ttf", "arial.ttf"):
    p = Path("C:/Windows/Fonts") / name
    if p.exists():
        font = ImageFont.truetype(str(p), 700)
        break
text = "B"
if font:
    box = d.textbbox((0, 0), text, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((S - w) / 2 - box[0], (S - h) / 2 - box[1] - 20), text, font=font, fill=(255, 255, 255, 255))
img.save(OUT)
print(OUT)
