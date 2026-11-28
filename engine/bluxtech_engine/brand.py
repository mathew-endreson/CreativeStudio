"""The brand guide of this PC's picture library: the colours GPT draws new pictures in (since Nov 28 2026).

Each PC chooses its own (Settings → Brand): a preset or its own colours, a name, optional notes. It is kept locally in
the library folder as `brand.json` (so the skill's scripts see it beside the pictures) and mirrored in the engine's
settings so a re-created library folder gets it back. The skill's `brand_guide.py` renders from it what keeps GPT on
style: AGENTS.md, the style guide, the four reference pictures re-coloured, and the palette lock's ramp. On the
owner's PC the library is the GPT asset studio's own folder, which keeps its own files: the brand is read-only there."""
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


def managed():
    """True when the brand may be changed here: the library is the app's own folder, not the GPT asset studio."""
    return config.GPT_DIR != config.GPT_TOOL_DIR


def current():
    return BG.normalize(BG.load(folder()))


def info():
    b = current()
    return {"managed": managed(), "dir": str(folder()), "brand": b, "house": BG.is_house(b), "presets": BG.PRESETS,
            "roles": BG.roles(b), "words": BG.words(b), "applied": (folder() / "style" / ".brand-stamp").is_file(),
            "guide": str(folder() / "style" / "style-identity-guide.md")}


def derive(primary, accent=None):
    """The palette the UI previews for colours not saved yet."""
    b = BG.normalize({"primary": primary, "accent": accent})
    target, band = BG.hue_info(b)
    return {"brand": b, "roles": BG.roles(b), "words": BG.words(b), "target_hue": target, "hue_band": band}


def save(data):
    if not managed():
        raise PermissionError("this PC draws in the GPT asset studio's own style; the brand applies to the app's own library")
    b = BG.normalize(data)
    b["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    folder().mkdir(parents=True, exist_ok=True)
    jdump(folder() / "brand.json", b)
    settings.set("brand", b)
    BG.apply(folder(), b, force=True)
    return info()


def restore():
    """At start: a library folder without its brand.json gets the one the settings remember, and a brand.json whose
    files are stale (new app version, edited by hand) is rendered again. Never touches the GPT asset studio."""
    if not managed():
        return
    f = folder() / "brand.json"
    try:
        if not f.is_file():
            remembered = settings.get("brand")
            if not remembered:
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
