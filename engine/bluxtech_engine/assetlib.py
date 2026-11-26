"""The pictures the user uploads for a product or a fresh edit, as the bluxstudio-skill uses them (since Nov 26 2026):
a folder of transparent PNG / WebP cut-outs with its keyword index `library.json`, written by
`asset_lib.py index <folder>` and `setmany` (references/asset-library.md). A product keeps them in `<slug>_src/img/`
with `"asset_lib": "img/library.json"` in product.json; `batch.py build` places from that library.

The engine only indexes the folder and reads the index. The keywords are Claude's: the graphics and fresh stages
look at every new picture and write them."""
from pathlib import Path

from . import config
from .store import jload

PRODUCT_LIB = "img/library.json"          # relative to <slug>_src, as remix.md writes it
FRESH_FOLDER = "uploads"                  # a fresh edit's default asset folder, inside its project


def product_lib(d, P):
    """The library.json `batch.py build` places from: product.json `asset_lib` (relative to <slug>_src), else the
    GPT asset studio's (what asset_lib.py uses without --lib)."""
    if P.get("asset_lib"):
        return Path(d) / P["asset_lib"]
    return config.GPT_DIR / "library.json"


def product_folder(d, P):
    """The product's upload folder: the folder of its asset_lib, <slug>_src/img by default."""
    return (Path(d) / (P.get("asset_lib") or PRODUCT_LIB)).parent


def assets(lib):
    data = jload(Path(lib)) or {}
    return [e for e in (data.get("assets") or []) if isinstance(e, dict) and e.get("id")] if isinstance(data, dict) else []


def entries(lib):
    return {e["id"]: e for e in assets(lib)}


def unusable(e):
    """'' when asset_lib.py place can show the picture, else why not (asset_lib.usable + a file that is gone)."""
    if e.get("missing"):
        return "the file is gone"
    if e.get("opaque"):
        return "no transparent background (NO-ALPHA): needs a PNG / WebP cut-out"
    if e.get("empty"):
        return "the picture is fully transparent"
    return ""


def tagged(e):
    return bool(e.get("tagged_by"))


def file_of(lib, e):
    p = Path(e.get("file") or "")
    return p if p.is_absolute() else Path(lib).parent / p


def counts(lib):
    a = assets(lib)
    live = [e for e in a if not e.get("missing")]
    return {"pictures": len(live), "usable": sum(not unusable(e) for e in live),
            "untagged": sum(not tagged(e) and not unusable(e) for e in live)}


def describe(lib, limit=80):
    """One line per picture for a prompt: id, file, motion / concept, and its keywords or what is wrong with it."""
    rows = []
    for e in assets(lib)[:limit]:
        if e.get("missing"):
            continue
        kw = e.get("keywords") or {}
        words = "، ".join((kw.get("darija") or [])[:6])
        other = ", ".join((kw.get("fr") or [])[:3] + (kw.get("en") or [])[:3])
        shown = "; ".join(x for x in (words, other) if x)
        why = unusable(e)
        if why:
            state = f"NOT USABLE: {why}"
        elif not tagged(e):
            state = f"NO KEYWORDS YET (from its file name: {shown or '-'})"
        else:
            state = f"keywords: {shown or '-'}"
        extra = "".join(f", {k} {e[k]}" for k in ("motion", "concept") if e.get(k))
        rows.append(f"- `{e['id']}` ({e.get('file')}{extra}): {state}")
    more = len(assets(lib)) - limit
    if more > 0:
        rows.append(f"- … and {more} more (`asset_lib.py --lib <lib> list`)")
    return "\n".join(rows)


def public(lib):
    """The library for the UI: every picture with its keywords and whether it can be shown."""
    out = []
    for e in assets(lib):
        out.append({"id": e["id"], "file": e.get("file"), "source": e.get("source"), "motion": e.get("motion") or "",
                    "concept": e.get("concept") or "", "keywords": e.get("keywords") or {}, "tagged": tagged(e),
                    "missing": bool(e.get("missing")), "problem": unusable(e)})
    return out


def index_cmd(folder):
    """`asset_lib.py index <folder>`: (re)index the folder into <folder>/library.json. New files are added (the
    file name as a first keyword), files that are gone are flagged; keywords already written are kept."""
    return [config.skill_python(), str(config.SCRIPTS / "asset_lib.py"), "index", str(folder)]
