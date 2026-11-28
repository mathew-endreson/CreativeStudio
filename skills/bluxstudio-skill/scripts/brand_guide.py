#!/usr/bin/env python3
"""brand_guide: the colours GPT draws a library's pictures in, per library folder.

The house style is the monochrome orange of `references/style-identity-guide.md`. A library folder may carry a
`brand.json` instead (CreativeStudio writes it from its Brand settings; a customer's PC, never the owner's GPT asset
studio folder):

    {"name": "Ocean blue", "preset": "ocean", "primary": "#1F6FEB", "accent": "#0B2A5B", "hue": "blue", "notes": ""}

`apply(folder)` renders what keeps GPT on style from it, into the folder:
    AGENTS.md                        the rules Codex reads in that folder (brand name, colour word)
    style/style-identity-guide.md    the house guide with the brand's palette and colour words
    style/refs/<look>-*.png          the four reference pictures recoloured onto the brand's ramp
    style/brand-ramp.json            the luminance ramp + hue band for finish_asset's palette lock
    style/.brand-stamp               what was rendered (apply() is a no-op until brand.json changes)
    style/.house/                    the folder's own AGENTS.md, guide and refs, kept aside once before the first
                                     render (the GPT asset studio's originals on the owner's PC); `house` puts them
                                     back byte for byte and removes the brand files
and `palette(folder)` gives asset_lib.concept_prompt the colour words and hexes for its prompt templates. Without a
brand.json nothing changes: the house orange, word for word.

    python brand_guide.py apply <folder> [--force]
    python brand_guide.py house <folder>
    python brand_guide.py show <folder>
    python brand_guide.py derive --primary "#1F6FEB" [--accent "#0B2A5B"]
    python brand_guide.py preview --primary "#1F6FEB" [--accent ...] --look flat --out blue.png [--size 360]
    python brand_guide.py presets

Needs the standard library; Pillow for the pictures.
"""
from __future__ import annotations

import argparse
import colorsys
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

VERSION = 1
SKILL_DIR = Path(__file__).resolve().parent.parent
GUIDE_TEMPLATE = SKILL_DIR / "references" / "style-identity-guide.md"
REFS_DIR = SKILL_DIR / "assets" / "refs"
REF_LOOKS = {"flat": "flat-person-coughing", "glossy": "glossy-lungs"}          # the preview picture per look
HOUSE_DIR = "style/.house"                 # the folder's own files, kept aside before the first brand (restore_house)
HOUSE_FILES = ("AGENTS.md", "style/style-identity-guide.md")

HOUSE = {"name": "House orange", "preset": "orange", "primary": "#FB7201", "accent": "#632302", "hue": "orange", "notes": ""}
PRESETS = [
    {"id": "orange", "name": "House orange", "primary": "#FB7201", "accent": "#632302"},
    {"id": "honey", "name": "Honey gold", "primary": "#E59B14", "accent": "#5A3400"},
    {"id": "forest", "name": "Forest green", "primary": "#2F9E5B", "accent": "#0D3B22"},
    {"id": "ocean", "name": "Ocean blue", "primary": "#1F6FEB", "accent": "#0B2A5B"},
    {"id": "royal", "name": "Royal purple", "primary": "#8E44AD", "accent": "#3A1452"},
    {"id": "rose", "name": "Rose", "primary": "#E05A7A", "accent": "#5E1226"},
    {"id": "teal", "name": "Teal", "primary": "#179C9C", "accent": "#073F3F"},
    {"id": "slate", "name": "Slate grey", "primary": "#6B7280", "accent": "#1F2937"},
]

# The house palette as the guide lists it, darkest to lightest (section 3), plus the flat look's "deeper orange".
ORANGE_ROLES = {
    "deep": ["#632302", "#8A2701"], "shadow": ["#A83301", "#CB4602"], "shade": ["#DA4F01", "#F16401"],
    "main": "#FB7201", "lit": ["#FC8603", "#FC9A25"], "gloss": ["#FCAE47", "#FBBE68", "#FBD299"],
    "highlight": ["#FBE4C6", "#FCF0E1"], "flatdeep": "#E85A01", "dark_end": "#3A1400", "light_end": "#FFF8EE",
}
# finish_asset.RAMP: luminance -> colour stops measured from the references
ORANGE_RAMP = [(0, (0x3A, 0x14, 0x00)), (46, (0x63, 0x23, 0x02)), (57, (0x8A, 0x27, 0x01)), (72, (0xA8, 0x33, 0x01)),
               (93, (0xCB, 0x46, 0x02)), (103, (0xDA, 0x4F, 0x01)), (123, (0xF1, 0x64, 0x01)), (135, (0xFB, 0x72, 0x01)),
               (150, (0xFC, 0x86, 0x03)), (166, (0xFC, 0x9A, 0x25)), (183, (0xFC, 0xAE, 0x47)), (197, (0xFB, 0xBE, 0x68)),
               (215, (0xFB, 0xD2, 0x99)), (231, (0xFB, 0xE4, 0xC6)), (241, (0xFC, 0xF0, 0xE1)), (255, (0xFF, 0xF8, 0xEE))]
ORANGE_HUE, ORANGE_BAND = 26.0, (14.0, 38.0)
ROLE_ORDER = [("deep", 0), ("deep", 1), ("shadow", 0), ("shadow", 1), ("shade", 0), ("shade", 1), ("main", None),
              ("lit", 0), ("lit", 1), ("gloss", 0), ("gloss", 1), ("gloss", 2), ("highlight", 0), ("highlight", 1)]
WHEEL = ["red", "orange", "yellow", "green", "teal", "blue", "purple", "pink"]
HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


# ---------------------------------------------------------------- colour maths

def parse_hex(s: str) -> tuple[int, int, int]:
    m = HEX_RE.match(str(s or "").strip())
    if not m:
        raise ValueError(f"not a colour: {s!r} (want #RRGGBB)")
    v = m.group(1)
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def to_hex(rgb) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def mix(a, b, t: float):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def luminance(rgb) -> float:
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def hsl(rgb):
    h, l, s = colorsys.rgb_to_hls(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)
    return h * 360, s, l


def hue_word(rgb) -> str:
    """The colour word the prompts use for this colour."""
    h, s, l = hsl(rgb)
    if s < 0.15 or l < 0.08 or l > 0.95:
        return "grey"
    if 15 <= h < 50 and l < 0.3:
        return "brown"
    if h < 15 or h >= 335:
        return "red"
    if h < 36:
        return "orange"
    if h < 65:
        return "gold" if l < 0.62 else "yellow"
    if h < 165:
        return "green"
    if h < 200:
        return "teal"
    if h < 255:
        return "blue"
    if h < 290:
        return "purple"
    return "pink"


def neighbours(word: str) -> tuple[str, str]:
    """The two hue words either side on the wheel: what a render must not drift into."""
    w = {"gold": "yellow", "brown": "orange", "grey": "orange"}.get(word, word)
    i = WHEEL.index(w) if w in WHEEL else 1
    return WHEEL[(i - 1) % len(WHEEL)], WHEEL[(i + 1) % len(WHEEL)]


def is_neutral(rgb) -> bool:
    return hsl(rgb)[1] < 0.15


# ---------------------------------------------------------------- the brand record

def normalize(b: dict | None) -> dict:
    """A complete brand record (the house orange when nothing is given); bad colours raise ValueError."""
    b = dict(b or {})
    out = dict(HOUSE)
    out["preset"] = str(b.get("preset") or ("orange" if not b.get("primary") else "custom"))[:24]
    out["primary"] = to_hex(parse_hex(b.get("primary") or HOUSE["primary"]))
    prim = parse_hex(out["primary"])
    if b.get("accent"):
        acc = parse_hex(b["accent"])
    else:
        acc = parse_hex(HOUSE["accent"]) if out["primary"] == HOUSE["primary"] else mix(prim, (0, 0, 0), 0.62)
    # the accent is the line work and the deepest hollows: it has to sit well below the shadows of the ramp
    floor = luminance(mix(prim, (0, 0, 0), 0.50)) - 2
    while luminance(acc) > floor and max(acc) > 2:
        acc = mix(acc, (0, 0, 0), 0.15)
    out["accent"] = to_hex(acc)
    name = str(b.get("name") or "").strip()
    out["name"] = (name or HOUSE["name"])[:60]
    hue = re.sub(r"[^a-z -]", "", str(b.get("hue") or "").strip().lower())[:20]
    out["hue"] = hue or hue_word(prim)
    out["notes"] = str(b.get("notes") or "").strip()[:1500]
    if b.get("updated"):
        out["updated"] = str(b["updated"])[:40]
    return out


def is_house(b: dict) -> bool:
    return b["primary"].upper() == HOUSE["primary"] and b["accent"].upper() == HOUSE["accent"] and b["hue"] == "orange"


def roles(b: dict) -> dict:
    """The guide's colour table for this brand: the measured orange for the house, shades and tints otherwise."""
    if is_house(b):
        return json.loads(json.dumps(ORANGE_ROLES))
    p, a, k, w = parse_hex(b["primary"]), parse_hex(b["accent"]), (0, 0, 0), (255, 255, 255)
    return {
        "deep": [to_hex(a), to_hex(mix(a, p, 0.15))],          # the accent is the line work, as #632302 is for orange
        "shadow": [to_hex(mix(p, k, 0.38)), to_hex(mix(p, k, 0.26))],
        "shade": [to_hex(mix(p, k, 0.18)), to_hex(mix(p, k, 0.08))],
        "main": to_hex(p),
        "lit": [to_hex(mix(p, w, 0.09)), to_hex(mix(p, w, 0.20))],
        "gloss": [to_hex(mix(p, w, 0.32)), to_hex(mix(p, w, 0.44)), to_hex(mix(p, w, 0.58))],
        "highlight": [to_hex(mix(p, w, 0.76)), to_hex(mix(p, w, 0.88))],
        "flatdeep": to_hex(mix(p, k, 0.12)),
        "dark_end": to_hex(mix(a, k, 0.55)),
        "light_end": to_hex(mix(p, w, 0.95)),
    }


def role_list(r: dict) -> list[str]:
    return [r[name] if i is None else r[name][i] for name, i in ROLE_ORDER]


def ramp(b: dict) -> list:
    """finish_asset's luminance stops for this brand: each stop keyed by its own luminance, strictly increasing."""
    if is_house(b):
        return [(k, tuple(c)) for k, c in ORANGE_RAMP]
    r = roles(b)
    cols = [parse_hex(h) for h in role_list(r)]
    stops = sorted((luminance(c), c) for c in cols)
    out, last = [(0, parse_hex(r["dark_end"]))], 0
    for lum, c in stops:
        key = max(int(round(lum)), last + 1)
        if key >= 255:
            break
        out.append((key, tuple(int(round(x)) for x in c)))
        last = key
    out.append((255, parse_hex(r["light_end"])))
    return out


def hue_info(b: dict):
    """(target hue, (low, high)) for the palette lock, or (None, None) for a neutral brand."""
    if is_house(b):
        return ORANGE_HUE, ORANGE_BAND
    p = parse_hex(b["primary"])
    if is_neutral(p):
        return None, None
    h = round(hsl(p)[0], 1)
    return h, (round(h - 12, 1), round(h + 12, 1))


def words(b: dict) -> dict:
    """The colour words of the prompts: the house guide's own for orange, the brand's hue otherwise."""
    hue = b["hue"]
    if is_house(b):
        return {"hue": "orange", "deep_word": "burnt orange", "dark_word": "brown-orange", "pale_word": "cream-white",
                "line_word": "dark brown", "pale_tint": "cream-orange", "streak": "cream"}
    acc_word = hue_word(parse_hex(b["accent"]))
    line = f"deep {hue}" if acc_word in (hue, "brown", "grey") or hue == "grey" else f"dark {acc_word}"
    return {"hue": hue, "deep_word": f"deep {hue}", "dark_word": f"dark {hue}", "pale_word": "soft white",
            "line_word": line, "pale_tint": f"pale {hue}", "streak": "pale"}


def palette(folder) -> dict:
    """What asset_lib.concept_prompt needs: words + hexes, for the brand in `folder` or the house orange."""
    b = normalize(load(folder) if folder else None)
    r = roles(b)
    return {**words(b), "main": r["main"], "inner": r["shadow"][1], "recess": r["shadow"][0], "line": r["deep"][0],
            "flatdeep": r["flatdeep"], "brand": None if is_house(b) else b}


def describe(folder) -> str:
    b = load(folder)
    if not b:
        return "house orange (no brand.json)"
    b = normalize(b)
    return f"{b['name']} ({b['hue']}: {b['primary']}, lines {b['accent']})"


def load(folder) -> dict | None:
    p = Path(folder) / "brand.json"
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------- rendering

def _colour_list(exclude: str) -> list[str]:
    base = ["red", "orange", "pink", "yellow", "green", "blue", "purple", "grey"]
    drop = {exclude, {"gold": "yellow", "brown": "orange"}.get(exclude, exclude)}
    return [c for c in base if c not in drop]


def render_guide(b: dict, template: str | None = None) -> str:
    """The house guide with this brand's palette and colour words (the house brand returns it unchanged)."""
    text = template if template is not None else GUIDE_TEMPLATE.read_text(encoding="utf-8-sig")
    if is_house(b) and not b.get("notes"):
        return text
    r, w = roles(b), words(b)
    hue, Hue = w["hue"], w["hue"].capitalize()
    if not is_house(b):
        for old, new in zip(role_list(ORANGE_ROLES) + [ORANGE_ROLES["flatdeep"]], role_list(r) + [r["flatdeep"]]):
            text = re.sub(re.escape(old), new, text, flags=re.I)
        target, band = hue_info(b)
        n1, n2 = neighbours(hue)
        others = _colour_list(hue)
        subs = [
            (r"Orange Health Illustrations: Visual Identity Guide", f"{b['name']}: Visual Identity Guide"),
            (r"the brand orange", f"the brand {hue}"),
            (r"burnt orange", w["deep_word"]),
            (r"brown-orange", w["dark_word"]),
            (r"cream-orange", w["pale_tint"]),
            (r"cream-white", w["pale_word"]),
            (r"cream (streaks|highlight)", w["streak"] + r" \1"),
            (r"dark[- ]brown", w["line_word"]),
            (r"muddy brown or pale yellow", "muddy or washed out"),
            (r"never black or grey", "never pure black" if hue == "grey" else "never black or grey"),
            (r"red, pink, yellow, green, blue, purple, grey or skin tones", ", ".join(others) + " or skin tones"),
            (r"drift into red or yellow", f"drift into {n1} or {n2}"),
            (r"red, pink, yellow, green, blue, purple, grey, black, white fill", ", ".join(others) + ", black, white fill"),
            (r"no red, yellow, grey, black or white areas", "no " + ", ".join(others) + ", black or white areas"),
            (r"\borange\b", hue),
            (r"\bOrange\b", Hue),
        ]
        if target is None:
            subs.insert(0, (r"Keep every colour between hue 14° and 38° at full saturation\.",
                            "Keep every colour neutral: no hue at all, only shades from near-black to near-white."))
            subs.insert(1, (r"median hue of 24–28°", "no measurable hue (a neutral grey)"))
        else:
            subs.insert(0, (r"hue 14° and 38°", f"hue {band[0]:.0f}° and {band[1]:.0f}°"))
            subs.insert(1, (r"24–28°", f"{target - 2:.0f}–{target + 2:.0f}°"))
        for pat, rep in subs:
            text = re.sub(pat, rep, text)
    head = [f"> **Brand: {b['name']}.** Main colour {b['primary']}, line work and deepest hollows {b['accent']}, "
            f"colour word “{hue}”. Rendered by CreativeStudio from the house guide: the words are the "
            f"house's, the colours are this brand's."]
    if b.get("notes"):
        head.append(">")
        head.append("> **Brand notes (follow them on every image):** " + " ".join(b["notes"].split()))
    title_end = text.find("\n", text.find("# ")) if text.startswith("#") else 0
    return text[:title_end + 1] + "\n" + "\n".join(head) + "\n" + text[title_end + 1:]


AGENTS_TEMPLATE = """# {name} asset studio

This folder is the GPT side of the {name} asset pipeline. Claude sends image
requests here through the local `gpt-assets` tool, and the user may also type
requests directly. Every request is for an illustration in one fixed style.

## Rules for every image request

1. Follow `style/style-identity-guide.md`. It is the only allowed style:
   monochrome {hue} health/anatomy illustrations, either glossy see-through
   gel organs (square) or soft matte silhouettes facing right (wide); one
   subject; transparent background; no text. The brand's colours are in
   section 3 of the guide: main {primary}, line work {accent}. No other hue.
{notes}2. Generate with the built-in `image_gen` tool. Do not use the image CLI
   fallback, an API key, or drawing with SVG/HTML/Python.
3. Use the matching images in `style/refs/` as style references (glossy:
   `glossy-*.png`, flat: `flat-*.png`). Match their colour, material and
   lighting, and draw only the requested subject.
4. Ask for a transparent background and keep the alpha channel.
5. If the request is only a word or two ("Human", "heart"), use section 7
   "Short requests" of the guide instead of asking questions.
6. If a request contains a ready-written prompt, use it exactly as written.
7. Save each final image as PNG in `generated/`, named `<look>-<subject>.png`
   (for example `generated/glossy-heart.png`). Never overwrite a file; add
   `-2`, `-3` instead.
8. Reply with the saved path(s) and the prompt you used.

`.gpt-assets/` holds request logs written by the tool, `library.json` is the
keyword index Claude keeps and `brand.json` the brand this folder is drawn
in. Leave them alone.
"""


def render_agents(b: dict) -> str:
    notes = ""
    if b.get("notes"):
        notes = "   Brand notes, to follow on every image: " + " ".join(b["notes"].split()) + "\n"
    return AGENTS_TEMPLATE.format(name=b["name"], hue=words(b)["hue"], primary=b["primary"], accent=b["accent"], notes=notes)


def _interp(x: float, xs: list, ys: list) -> float:
    if x <= xs[0]:
        return ys[0]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            t = (x - xs[i - 1]) / max(xs[i] - xs[i - 1], 1e-6)
            return ys[i - 1] + (ys[i] - ys[i - 1]) * t
    return ys[-1]


def recolor_image(im, b: dict):
    """A picture of the house set re-coloured onto this brand's ramp by luminance (alpha kept)."""
    from PIL import Image

    im = im.convert("RGBA")
    r, g, bl, a = im.split()
    lum = Image.merge("RGB", (r, g, bl)).convert("L", matrix=(0.2126, 0.7152, 0.0722, 0))
    stops = ramp(b)
    xs = [k for k, _ in stops]
    luts = [[int(round(_interp(i, xs, [c[ch] for _, c in stops]))) for i in range(256)] for ch in range(3)]
    return Image.merge("RGBA", (lum.point(luts[0]), lum.point(luts[1]), lum.point(luts[2]), a))


def preview(b: dict, look: str = "flat", size: int = 360):
    """The reference picture of a look in this brand's colours, as a PIL image (a thumbnail)."""
    from PIL import Image

    src = REFS_DIR / f"{REF_LOOKS.get(look, REF_LOOKS['flat'])}.webp"
    im = Image.open(src).convert("RGBA")
    im.thumbnail((size, size))
    return im if is_house(b) else recolor_image(im, b)


def stamp(b: dict) -> str:
    key = json.dumps({k: b.get(k) for k in ("name", "primary", "accent", "hue", "notes")}, sort_keys=True)
    try:
        tpl = GUIDE_TEMPLATE.stat().st_mtime_ns
    except OSError:
        tpl = 0
    return hashlib.sha1(f"{VERSION}|{tpl}|{key}".encode("utf-8")).hexdigest()


def backup_house(folder) -> bool:
    """Keep the folder's own AGENTS.md, guide and reference pictures aside before the first brand render (once; on
    the owner's PC these are the GPT asset studio's originals). Returns True when the copy was made now."""
    folder = Path(folder)
    dst = folder / HOUSE_DIR
    if dst.exists():
        return False
    found = [folder / f for f in HOUSE_FILES if (folder / f).is_file()] + sorted((folder / "style" / "refs").glob("*.png"))
    if not found:
        return False
    for src in found:
        out = dst / src.relative_to(folder)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)
    return True


def restore_house(folder) -> bool:
    """Back to the folder's own style: the files backup_house kept come back byte for byte, brand files the folder
    did not have before go (gpt_assets.ensure_gpt_project lays the house defaults down again when needed), and
    brand.json, the ramp and the stamp are removed. Returns True when a kept copy was restored."""
    folder = Path(folder)
    kept = folder / HOUSE_DIR
    had = set()
    if kept.is_dir():
        for p in kept.rglob("*"):
            if p.is_file():
                rel = p.relative_to(kept)
                out = folder / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, out)
                had.add(rel.as_posix())
    for f in list(HOUSE_FILES) + [f"style/refs/{p.stem}.png" for p in REFS_DIR.glob("*.webp")]:
        if f not in had:
            try:
                (folder / f).unlink()
            except FileNotFoundError:
                pass
    for name in ("brand.json", "style/brand-ramp.json", "style/.brand-stamp"):
        try:
            (folder / name).unlink()
        except FileNotFoundError:
            pass
    return bool(had)


def apply(folder, brand: dict | None = None, force: bool = False) -> bool:
    """Render the brand's files into the library folder. Returns True when something was (re)written."""
    folder = Path(folder)
    b = normalize(brand if brand is not None else load(folder))
    if brand is None and not (folder / "brand.json").is_file():
        return False
    style = folder / "style"
    mark = style / ".brand-stamp"
    want = stamp(b)
    if not force and mark.is_file() and mark.read_text(encoding="utf-8").strip() == want:
        return False
    backup_house(folder)
    (style / "refs").mkdir(parents=True, exist_ok=True)
    (folder / "generated").mkdir(exist_ok=True)
    (style / "style-identity-guide.md").write_text(render_guide(b), encoding="utf-8")
    (folder / "AGENTS.md").write_text(render_agents(b), encoding="utf-8")
    from PIL import Image

    for src in sorted(REFS_DIR.glob("*.webp")):
        dst = style / "refs" / f"{src.stem}.png"
        im = Image.open(src)
        (im.convert("RGBA") if is_house(b) else recolor_image(im, b)).save(dst)
    target, band = hue_info(b)
    (style / "brand-ramp.json").write_text(json.dumps({
        "version": VERSION, "brand": {k: b[k] for k in ("name", "preset", "primary", "accent", "hue")},
        "ramp": [[k, list(c)] for k, c in ramp(b)], "target_hue": target, "hue_band": list(band) if band else None,
        "roles": roles(b), "rendered": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }, indent=1), encoding="utf-8")
    mark.write_text(want, encoding="utf-8")
    return True


# ---------------------------------------------------------------- CLI

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("apply", help="render AGENTS.md, the guide, the refs and the ramp from <folder>/brand.json")
    a1.add_argument("folder")
    a1.add_argument("--force", action="store_true")
    a2 = sub.add_parser("show", help="the brand of a folder and its palette")
    a2.add_argument("folder")
    a5 = sub.add_parser("house", help="back to the folder's own style: restore what the first brand render kept aside")
    a5.add_argument("folder")
    a3 = sub.add_parser("derive", help="the palette for colours (no folder)")
    a3.add_argument("--primary", required=True)
    a3.add_argument("--accent")
    a3.add_argument("--name", default="")
    a4 = sub.add_parser("preview", help="a reference picture in these colours")
    a4.add_argument("--primary", required=True)
    a4.add_argument("--accent")
    a4.add_argument("--look", default="flat", choices=sorted(REF_LOOKS))
    a4.add_argument("--out", required=True)
    a4.add_argument("--size", type=int, default=360)
    sub.add_parser("presets", help="the preset list")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    if a.cmd == "apply":
        done = apply(a.folder, force=a.force)
        print(f"{'rendered' if done else 'up to date'}: {describe(a.folder)} in {a.folder}")
    elif a.cmd == "show":
        b = normalize(load(a.folder))
        print(json.dumps({"brand": b, "house": is_house(b), "roles": roles(b), "palette": palette(a.folder)}, indent=1))
    elif a.cmd == "house":
        kept = restore_house(a.folder)
        print(("restored the folder's own files" if kept else "no kept copy: brand files removed, house defaults return on the next draw") + f" in {a.folder}")
    elif a.cmd == "derive":
        b = normalize({"primary": a.primary, "accent": a.accent, "name": a.name})
        t, band = hue_info(b)
        print(json.dumps({"brand": b, "roles": roles(b), "ramp": ramp(b), "target_hue": t, "hue_band": band,
                          "words": words(b)}, indent=1))
    elif a.cmd == "preview":
        b = normalize({"primary": a.primary, "accent": a.accent})
        preview(b, a.look, a.size).save(a.out)
        print(a.out)
    elif a.cmd == "presets":
        print(json.dumps(PRESETS, indent=1))


if __name__ == "__main__":
    main()
