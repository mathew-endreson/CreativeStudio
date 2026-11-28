"""The picture library of this PC: pictures every ad may show in front of the speaker, beyond each project's own.

On the owner's PC it is the GPT asset studio's folder (config.GPT_TOOL_DIR); on any other PC it is the app's own
folder in the workspace (<workspace>/assets), empty until the user adds pictures in the Library screen. Nothing is
shipped with the installer any more (Nov 28 2026). Uploads are prepared like a project's pictures (a packshot or an
offer photo is cut out, an illustration is copied when it has a transparent background and cut out otherwise),
placed in <library>/generated, the folder `asset_lib.py index` scans for a studio-layout library, and indexed.
The keywords are Claude's: the next edit looks at every picture that has none yet."""
import shutil
from pathlib import Path

from . import assetlib, config
from .jobs import JobFailed
from .products import IMAGE, MAX_PICTURE_BYTES, _stem, has_alpha
from .store import jdump, jload


def folder():
    return config.GPT_DIR


def lib_file():
    return config.GPT_DIR / "library.json"


def studio():
    """True on the owner's PC, where the library is the GPT asset studio's own folder."""
    return config.GPT_DIR == config.GPT_TOOL_DIR


def info():
    lib = lib_file()
    data = jload(lib) or {}
    return {"dir": str(folder()), "updated": data.get("updated") if isinstance(data, dict) else None,
            "assets": assetlib.public(lib), "counts": assetlib.counts(lib), "exists": lib.exists(),
            "studio": studio(), "own": not studio()}


def stage(files):
    """Check the pictures the user gives before a job copies them: real files, picture types, a size limit."""
    out = []
    for f in files:
        p = Path(f.file).expanduser()
        if not p.is_file():
            raise ValueError(f"file not found: {f.file}")
        if p.suffix.lower() not in IMAGE:
            raise ValueError(f"not a picture: {p.name} (PNG, WebP, JPEG, TIFF, HEIC or RW2)")
        size = p.stat().st_size
        if size > MAX_PICTURE_BYTES:
            raise ValueError(f"too large: {p.name} is {size // 2**20} MB, the limit is {MAX_PICTURE_BYTES // 2**20} MB")
        if size == 0:
            raise ValueError(f"empty file: {p.name}")
        out.append({"file": str(p), "tag": f.tag, "label": f.label, "note": f.note})
    return out


def pictures_job(ctx, job, spec):
    """Prepare the given pictures into the library's generated/ folder, then index the library."""
    py, S = config.skill_python(), config.SCRIPTS
    dest = folder() / "generated"
    dest.mkdir(parents=True, exist_ok=True)
    made = []
    for i, pic in enumerate(spec.get("files") or []):
        src = Path(pic["file"])
        tag = pic.get("tag") or "illustration"
        stem = _stem(pic.get("label") or src.stem, f"picture{i + 1}")
        if not src.exists():
            ctx.log("error", f"missing: {src}")
            continue
        if src.suffix.lower() == ".rw2":
            work = config.DATA / "work"
            work.mkdir(parents=True, exist_ok=True)
            jpg = work / f"{src.stem}.jpg"
            ctx.log("sys", f"$ rw2_preview.py {src.name}")
            if ctx.spawn([py, str(S / "rw2_preview.py"), str(src), str(jpg)]) != 0:
                ctx.log("error", f"rw2_preview failed on {src.name}")
                continue
            src = jpg
        keep = tag == "illustration" and src.suffix.lower() in (".png", ".webp") and has_alpha(src)
        out = dest / f"{stem}{src.suffix.lower() if keep else '.png'}"
        n = 2
        while out.exists():                                  # never overwrite a picture already there
            out = dest / f"{stem}-{n}{out.suffix}"
            n += 1
        if tag == "packshot":
            ctx.log("sys", f"$ cutout_product.py {src.name} --symmetric")
            code = ctx.spawn([py, str(S / "cutout_product.py"), str(src), str(out), "--symmetric"])
        elif tag == "offer":
            ctx.log("sys", f"$ offer_cutout.py {src.name}")
            code = ctx.spawn([py, str(S / "offer_cutout.py"), str(src), str(out)])
        elif keep:
            shutil.copy2(src, out)
            code = 0
        else:
            ctx.log("sys", f"$ cutout_product.py {src.name} (no transparent background)")
            code = ctx.spawn([py, str(S / "cutout_product.py"), str(src), str(out)])
        if code != 0 or not out.exists():
            ctx.log("error", f"{tag} {src.name}: exit {code}")
            continue
        made.append(out.name)
    ctx.log("sys", f"$ asset_lib.py index {folder()}")
    if ctx.spawn(assetlib.index_cmd(folder())) != 0:
        raise JobFailed("asset_lib.py index failed")
    n = assetlib.counts(lib_file())
    ctx.log("sys", f"{n['pictures']} picture(s) in the library, {n['usable']} usable, {n['untagged']} without keywords yet; "
                   f"new: {', '.join(made) or 'none'}")
    return {"pictures": n["pictures"], "usable": n["usable"], "untagged": n["untagged"], "new": made}


def remove(pid):
    """Take one picture out of the library: its entry, and its file when the file sits inside the library folder."""
    lib = lib_file()
    data = jload(lib) or {}
    assets = data.get("assets") or []
    entry = next((e for e in assets if e.get("id") == pid), None)
    if entry is None:
        raise ValueError(f"no picture {pid}")
    f = assetlib.file_of(lib, entry)
    root = folder().resolve()
    if f.exists() and root in f.resolve().parents:
        f.unlink()
    data["assets"] = [e for e in assets if e.get("id") != pid]
    jdump(lib, data)
