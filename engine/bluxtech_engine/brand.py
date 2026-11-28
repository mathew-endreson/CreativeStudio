"""The brand guide of this PC's picture library: the colours GPT draws new pictures in (since Nov 28 2026).

Each PC chooses its own (Settings → Brand): a preset or its own colours, a name, optional notes. It is kept locally in
the library folder as `brand.json` (so the skill's scripts see it beside the pictures) and mirrored in the engine's
settings so a re-created library folder gets it back. The skill's `brand_guide.py` renders from it what keeps GPT on
style: AGENTS.md, the style guide, the four reference pictures re-coloured, and the palette lock's ramp. On the
owner's PC the library is the GPT asset studio's own folder: its original files are kept aside (style/.house) the
first time a brand is saved, and choosing the house orange again puts them back byte for byte."""
import io
import sys
import time
from functools import lru_cache

from . import config, settings
from .store import jdump

if str(config.SCRIPTS) not in sys.path:
    sys.path.insert(0, str(config.SCRIPTS))
import brand_guide as BG  # noqa: E402  (the skill's brand_guide.py: stdlib at import)

log = None                                   # set by app.py to its logger, optional


def folder():
    return config.GPT_DIR


def studio():
    """True on the owner's PC, where the library is the GPT asset studio's own folder (its originals are kept)."""
    return config.GPT_DIR == config.GPT_TOOL_DIR


def managed():
    """The brand can be changed on every PC (kept for the UI's `managed` field)."""
    return True


def current():
    return BG.normalize(BG.load(folder()))


def info():
    b = current()
    return {"managed": managed(), "studio": studio(), "dir": str(folder()), "brand": b, "house": BG.is_house(b),
            "presets": BG.PRESETS, "roles": BG.roles(b), "words": BG.words(b),
            "applied": (folder() / "style" / ".brand-stamp").is_file(), "house_kept": (folder() / BG.HOUSE_DIR).is_dir(),
            "guide": str(folder() / "style" / "style-identity-guide.md")}


def derive(primary, accent=None):
    """The palette the UI previews for colours not saved yet."""
    b = BG.normalize({"primary": primary, "accent": accent})
    target, band = BG.hue_info(b)
    return {"brand": b, "roles": BG.roles(b), "words": BG.words(b), "target_hue": target, "hue_band": band}


def save(data):
    """A brand: brand.json + the rendered files (the folder's own files kept aside first). The house orange: the kept
    files come back and the brand files go, so the folder is as it was before any brand."""
    b = BG.normalize(data)
    folder().mkdir(parents=True, exist_ok=True)
    if BG.is_house(b):
        BG.restore_house(folder())
        settings.delete("brand")
        return info()
    b["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    jdump(folder() / "brand.json", b)
    settings.set("brand", b)
    BG.apply(folder(), b, force=True)
    return info()


def restore():
    """At start: a library folder without its brand.json gets the one the settings remember, and a brand.json whose
    files are stale (new app version, edited by hand) is rendered again."""
    f = folder() / "brand.json"
    try:
        if not f.is_file():
            remembered = settings.get("brand")
            if not remembered or BG.is_house(BG.normalize(remembered)):
                return
            folder().mkdir(parents=True, exist_ok=True)
            jdump(f, BG.normalize(remembered))
        BG.apply(folder())
    except Exception as e:  # noqa: BLE001 - a brand that fails to render must not stop the engine
        if log:
            log.warning("brand: %s", e)


@lru_cache(maxsize=64)
def preview_png(primary, accent, look, size):
    """A reference picture in these colours, as PNG bytes (cached: the UI asks while the user picks)."""
    b = BG.normalize({"primary": primary, "accent": accent or None})
    im = BG.preview(b, look, max(64, min(int(size or 360), 720)))
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()
