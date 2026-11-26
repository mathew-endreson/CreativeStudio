"""What BluxTech Studio adds to camel-studio's store: products created from a folder, the build of ticked
proposals, the results of every mix (reports, snapshots, the ad), and small file helpers for the UI."""
import hashlib
import json
import os
import re
import subprocess
import time
import unicodedata
from pathlib import Path

from . import assetlib, config, store
from .jobs import JobFailed
from .store import B, NotFound, jdump, jload

VIDEO = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts"}
MAX_PICTURE_BYTES = 80 * 2**20          # one uploaded picture at most (a RAW photo is about 25 MB)
IMAGE = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".rw2", ".heic"}


# ------------------------------------------------------------------ files

def probe(path):
    """ffprobe, the fields the UI shows. Never raises: a file ffprobe cannot read comes back with what we know."""
    out = {"duration": None, "fps": None, "w": None, "h": None, "audio_rate": None, "video": False, "audio": False}
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, env=config.child_env())
        j = json.loads(r.stdout or "{}")
    except Exception:
        return out
    for s in j.get("streams", []):
        if s.get("codec_type") == "video" and not out["video"]:
            out["video"] = True
            out["w"], out["h"] = s.get("width"), s.get("height")
            num, _, den = (s.get("r_frame_rate") or "0/1").partition("/")
            try:
                out["fps"] = round(float(num) / float(den or 1), 3)
            except (ValueError, ZeroDivisionError):
                pass
        elif s.get("codec_type") == "audio" and not out["audio"]:
            out["audio"] = True
            out["audio_rate"] = int(s.get("sample_rate") or 0) or None
    try:
        out["duration"] = round(float(j.get("format", {}).get("duration")), 3)
    except (TypeError, ValueError):
        pass
    return out


def list_folder(path):
    p = Path(path).expanduser()
    if not p.is_dir():
        raise NotFound(f"folder {path}")
    out = []
    for f in sorted(p.iterdir(), key=lambda x: (x.is_dir(), x.name.lower())):
        if f.name.startswith(".") or f.name.startswith("~$"):
            continue
        if f.is_dir():
            out.append({"name": f.name, "path": str(f), "kind": "folder"})
            continue
        ext = f.suffix.lower()
        kind = "video" if ext in VIDEO else "image" if ext in IMAGE else "other"
        e = {"name": f.name, "path": str(f), "kind": kind, "size": f.stat().st_size}
        if kind == "video":
            e.update(probe(f))
        out.append(e)
    return {"path": str(p), "parent": str(p.parent) if p.parent != p else None, "entries": out}


def thumb(path, w=160):
    """One frame (or the image itself scaled) as a small JPEG, kept under DATA/thumbs."""
    src = Path(path)
    if not src.is_file():
        raise NotFound(path)
    key = hashlib.sha1(f"{src.resolve()}|{src.stat().st_mtime_ns}|{w}".encode("utf-8")).hexdigest()[:24]
    out = config.DATA / "thumbs" / "files" / f"{key}.jpg"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".tmp.jpg")
        cmd = ["ffmpeg", "-v", "error", "-y"]
        if src.suffix.lower() in VIDEO:
            cmd += ["-ss", "1", "-i", str(src), "-frames:v", "1"]
        else:
            cmd += ["-i", str(src), "-frames:v", "1"]
        cmd += ["-vf", f"scale={w}:-2", "-q:v", "4", str(tmp)]
        subprocess.run(cmd, capture_output=True, timeout=60, env=config.child_env())
        if not tmp.exists():
            raise NotFound(f"no picture for {src.name}")
        os.replace(tmp, out)
    return out


def reveal(path):
    """Show a file or folder in Explorer."""
    p = Path(path)
    if not p.exists():
        raise NotFound(path)
    if os.name == "nt":
        subprocess.Popen(["explorer", "/select," + str(p)] if p.is_file() else ["explorer", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p.parent if p.is_file() else p)])


# ------------------------------------------------------------------ a new product

def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "product"


def create_product(spec):
    """Write _hyperframes/<slug>_src/product.json for a folder of finished ads (and the product's pictures, which
    the pictures job puts into <slug>_src/img, the product's asset folder)."""
    slug = slugify(spec.slug or spec.name)
    if not B.ID_RE.match(slug):
        raise ValueError(f"'{slug}' is not a valid slug (letters, digits, dashes)")
    d = config.HF / f"{slug}_src"
    if d.exists():
        raise ValueError(f"a product '{slug}' already exists")
    pdir = Path(spec.product_dir).expanduser()
    if not pdir.is_dir():
        raise ValueError(f"product folder not found: {spec.product_dir}")
    sources, pictures, n = {}, [], 0
    for s in spec.sources:
        f = Path(s.file)
        full = f if f.is_absolute() else pdir / f
        if not full.exists():
            raise ValueError(f"file not found: {s.file}")
        rel = str(full.relative_to(pdir)) if full.is_relative_to(pdir) else str(full)
        if s.tag in ("finished_ad", "source"):
            n += 1
            key = re.sub(r"[^a-z0-9]+", "", (s.label or "").lower()) or f"s{n}"
            while key in sources:
                key += "x"
            sources[key] = {"file": rel, "tag": s.tag, "label": s.label or key.upper(), **({"note": s.note} if s.note else {})}
        elif s.tag in ("packshot", "offer", "illustration"):
            pictures.append({"file": str(full), "tag": s.tag, "label": s.label, "note": s.note})
    if not sources:
        raise ValueError("tag at least one video as a finished ad or raw footage")
    P = {"slug": slug, "name": spec.name.strip(), "name_ar": spec.name_ar.strip(), "whisper_prompt": spec.whisper_prompt.strip(),
         "product_dir": str(pdir), "ads_dir": str(Path(spec.ads_dir).expanduser()) if spec.ads_dir else str(pdir / "Ads"),
         "name_pattern": spec.name_pattern, "id_prefix": slug, "fps": 30, "sources": sources,
         "beats_file": f"beats_{slug}_src.json", "project_assets": [], "place": True, "gpt_cap": spec.gpt_cap,
         "asset_lib": assetlib.PRODUCT_LIB, **({"asset_bottom": spec.asset_bottom} if spec.asset_bottom else {}),
         "offers": [o.model_dump() for o in spec.offers], "duplicates": list(spec.duplicates),
         "pictures": pictures, "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "created_by": "bluxtech-studio"}
    (d / "work").mkdir(parents=True)
    (d / "img").mkdir()
    jdump(d / "product.json", P)
    jdump(d / "mixes.json", {})
    return slug, pictures


def _stem(text, fallback):
    return re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
                  .lower()).strip("-") or fallback


def _rel(d, p):
    try:
        return Path(p).resolve().relative_to(Path(d).resolve()).as_posix()
    except ValueError:
        return str(p)


def has_alpha(path):
    """A transparent background (asset_lib.py's own test: >= 2 % of the pixels see-through). Unknown -> True:
    asset_lib.py index flags it NO-ALPHA anyway."""
    try:
        import numpy as np
        from PIL import Image
        with Image.open(path) as im:
            if "A" not in im.getbands() and "transparency" not in im.info:
                return False
            a = np.asarray(im.convert("RGBA"))[..., 3]
        return bool((a < 250).mean() >= 0.02)
    except Exception:
        return True


def pictures_job(ctx, job, spec):
    """The product's pictures -> its asset folder (<slug>_src/img), indexed for the skill's asset_lib.py.

    Each picture the user gave (product.json `pictures`, once): a white-background packshot is cut out with
    cutout_product.py --symmetric (the jar), an offer photo with offer_cutout.py, any other picture copied as it is
    when it has a transparent background, else cut out with cutout_product.py (RAW files go through rw2_preview.py
    first). Then `asset_lib.py index` writes the folder's library.json, and product.json gets `asset_lib` (and
    `place`, so batch.py build places the pictures). The keywords are Claude's: the graphics stage looks at every
    picture that has none yet. Remixes need no project assets or cutouts any more (Nov 26 2026)."""
    d, P, _ = store.product(job["slug"])
    py, S = config.skill_python(), config.SCRIPTS
    if not P.get("asset_lib"):
        P["asset_lib"] = assetlib.PRODUCT_LIB
    folder = assetlib.product_folder(d, P)
    folder.mkdir(parents=True, exist_ok=True)
    pics = P.get("pictures", [])
    packshots = sum(p.get("tag") == "packshot" for p in pics)
    made = []
    for i, pic in enumerate(pics):
        if pic.get("done") and (d / pic["done"]).exists():
            continue
        src = Path(pic["file"])
        tag = pic.get("tag") or "illustration"
        stem = _stem(pic.get("label") or src.stem, f"pic{i + 1}")
        if tag == "packshot":
            out = folder / ("jar.png" if packshots == 1 else f"jar-{stem}.png")
        elif tag == "offer":
            out = folder / f"offer-{stem}.png"
        else:
            keep = src.suffix.lower() in (".png", ".webp") and src.exists() and has_alpha(src)
            out = folder / f"{stem}{src.suffix.lower() if keep else '.png'}"
        if out.exists() and not pic.get("done"):
            if any(q is not pic and q.get("done") == _rel(d, out) for q in pics):
                # another upload already made a file of that name: never overwrite it, number this one
                n = 2
                while (folder / f"{out.stem}-{n}{out.suffix}").exists():
                    n += 1
                out = folder / f"{out.stem}-{n}{out.suffix}"
            else:
                pic["done"] = _rel(d, out)     # made by an earlier run of this job
                continue
        if not src.exists():
            ctx.log("error", f"missing: {src}")
            continue
        if src.suffix.lower() == ".rw2":
            jpg = d / "work" / f"{src.stem}.jpg"            # not in the asset folder: a JPG there is listed NO-ALPHA
            ctx.log("sys", f"$ rw2_preview.py {src.name}")
            if ctx.spawn([py, str(S / "rw2_preview.py"), str(src), str(jpg)]) != 0:
                ctx.log("error", f"rw2_preview failed on {src.name}")
                continue
            src = jpg
        if tag == "packshot":
            ctx.log("sys", f"$ cutout_product.py {src.name} --symmetric")
            code = ctx.spawn([py, str(S / "cutout_product.py"), str(src), str(out), "--symmetric"])
        elif tag == "offer":
            ctx.log("sys", f"$ offer_cutout.py {src.name}")
            code = ctx.spawn([py, str(S / "offer_cutout.py"), str(src), str(out)])
        elif out.suffix.lower() == src.suffix.lower() and src.suffix.lower() in (".png", ".webp"):
            import shutil
            shutil.copy2(src, out)
            code = 0
        else:
            ctx.log("sys", f"$ cutout_product.py {src.name} (no transparent background)")
            code = ctx.spawn([py, str(S / "cutout_product.py"), str(src), str(out)])
        if code != 0 or not out.exists():
            ctx.log("error", f"{tag} {src.name}: exit {code}")
            continue
        pic["done"] = _rel(d, out)
        made.append(out.name)
    jdump(d / "product.json", P)
    ctx.log("sys", f"$ asset_lib.py index {store.rel(folder)}")
    if ctx.spawn(assetlib.index_cmd(folder)) != 0:
        raise JobFailed("asset_lib.py index failed")
    d, P, _ = store.product(job["slug"])                    # re-read, in case the user changed it meanwhile
    if not P.get("asset_lib") or P.get("place") is not True:
        P["asset_lib"] = P.get("asset_lib") or assetlib.PRODUCT_LIB
        P["place"] = True                                   # asset beats need asset_lib.py place at build
        jdump(d / "product.json", P)
    lib = assetlib.product_lib(d, P)
    n = assetlib.counts(lib)
    ctx.log("sys", f"{n['pictures']} picture(s) in {store.rel(folder)}, {n['usable']} usable, {n['untagged']} without "
                   f"keywords yet; new: {', '.join(made) or 'none'}")
    return {"pictures": n["pictures"], "usable": n["usable"], "untagged": n["untagged"], "new": made}


# ------------------------------------------------------------------ build: proposals -> mixes

def commit_proposals(slug, ids):
    """The ticked proposals become mixes (mixes.json), with the fields batch.py builds from."""
    d, P, M = store.product(slug)
    data = store.proposals(d)
    done = []
    for ad in data["ads"]:
        if ad["id"] not in ids or ad.get("status") == "rejected":
            continue
        if ad["id"] not in M:
            M[ad["id"]] = {"name": ad["name"], "file_name": ad["file_name"],
                           "segs": [{k: s.get(k) for k in ("src", "a0", "a1", "v0", "v1", "text")} for s in ad["segs"]],
                           "body": ad["body"], "cta": ad.get("cta"), "hook_beats": bool(ad.get("hook_beats")),
                           "angle": ad.get("angle", ""), "from_proposal": True}
        ad["status"], ad["picked"] = "accepted", True
        done.append(ad["id"])
    if not done:
        raise ValueError("none of these proposals can be built (rejected, or unknown)")
    jdump(d / "mixes.json", M)
    jdump(d / "proposals.json", data)
    return done


# ------------------------------------------------------------------ results

def beat_lines(spec, notes=None, mid=None):
    """The built mix's assets for the UI. `label` = the words he says on it (graphics_notes.json), or for a beat
    from before Nov 26 2026 its old label; a beat with no picture was dropped by remix_broll.py."""
    said = [n for n in (notes or {}).get("beats", []) if isinstance(n, dict) and n.get("mix") == mid]
    out = []
    for b in spec.get("beats", []):
        words = " ".join(re.sub(r"<[^>]+>", "", l.get("html", "")) for l in b.get("labels", []) if isinstance(l, dict))
        if b.get("lib"):
            near = [n for n in said if n.get("graphic") == b["lib"] and isinstance(n.get("t"), (int, float))
                    and b.get("in", 0) - 1 <= n["t"] <= b.get("out", 0) + 1]
            if near:
                words = min(near, key=lambda n: abs(n["t"] - b.get("in", 0))).get("words") or words
        out.append({"in": b.get("in"), "out": b.get("out"), "side": b.get("side") or "C",
                    "graphic": b.get("lib") or b.get("kind"), "label": words.strip(),
                    "check": b.get("check") or ("" if b.get("img") else "dropped: no picture (old disc / jar style)")})
    return out


def result(d, P, M, mid):
    proj = config.HF / mid
    st = B.mix_state(d, P, M, mid)
    build = jload(proj / ".work" / "build.json")
    check = jload(proj / ".work" / "check.json")
    report = jload(proj / ".work" / "final_report.json")
    beats = jload(proj / ".work" / "beats.json")
    rev = jload(proj / ".work" / "revision.json")
    notes = jload(d / "work" / "graphics_notes.json") or {}
    return {**st, "angle": M[mid].get("angle", ""), "segs": M[mid].get("segs", []), "body": M[mid].get("body", []),
            "cta": M[mid].get("cta"), "build": build, "check": check, "report": report,
            "beats": beat_lines(beats, notes, mid) if beats else [], "revision": rev,
            "gpt_drawings": notes.get("gpt_drawings", []), "unsure": notes.get("unsure", []),
            "missing": notes.get("missing", []),
            "snaps": [f for f in (check or {}).get("files", []) if f.endswith((".png", ".jpg"))],
            "sheets": [n for n in ("final_sheet.jpg", "joins_sheet.jpg") if (proj / ".work" / n).exists()],
            "warnings": list((build or {}).get("place_warnings", []))}


# ------------------------------------------------------------------ the product's pictures (its asset folder)

def pictures(slug):
    """The product's asset folder and library for the UI: every picture with its keywords and whether it can be
    shown, the pictures given that are not processed yet, and asset_bottom."""
    d, P, _ = store.product(slug)
    lib = assetlib.product_lib(d, P)
    own = bool(P.get("asset_lib"))
    return {"dir": str(assetlib.product_folder(d, P)) if own else None, "lib": str(lib), "own_library": own,
            "assets": assetlib.public(lib), "counts": assetlib.counts(lib), "asset_bottom": P.get("asset_bottom"),
            "pending": [p for p in P.get("pictures", []) if not p.get("done")]}


def add_pictures(slug, spec):
    """More pictures for a product (and its asset_bottom). Returns whether the pictures job has work to do."""
    d, P, _ = store.product(slug)
    pdir = Path(P.get("product_dir") or d)
    pics = P.setdefault("pictures", [])
    known = {str(Path(p["file"])).lower() for p in pics}
    added = 0
    for f in spec.files:
        full = Path(f.file).expanduser()
        full = full if full.is_absolute() else pdir / full
        if not full.is_file():
            raise ValueError(f"file not found: {f.file}")
        if full.suffix.lower() not in IMAGE:
            raise ValueError(f"not a picture: {full.name} (PNG, WebP, JPEG, TIFF, HEIC or RW2)")
        if full.stat().st_size > MAX_PICTURE_BYTES:
            raise ValueError(f"too large: {full.name} is {full.stat().st_size // 2**20} MB, the limit is {MAX_PICTURE_BYTES // 2**20} MB")
        if full.stat().st_size == 0:
            raise ValueError(f"empty file: {full.name}")
        if str(full).lower() in known:
            continue
        pics.append({"file": str(full), "tag": f.tag, "label": f.label, "note": f.note})
        known.add(str(full).lower())
        added += 1
    if spec.clear_asset_bottom:
        P.pop("asset_bottom", None)
    elif spec.asset_bottom:
        P["asset_bottom"] = spec.asset_bottom
    P["asset_lib"] = P.get("asset_lib") or assetlib.PRODUCT_LIB
    jdump(d / "product.json", P)
    return added


def remove_picture(slug, pid):
    """Take one picture out of the product's library and folder (only a file inside that folder is deleted), and
    forget the upload it came from so the pictures job does not make it again."""
    d, P, _ = store.product(slug)
    if not P.get("asset_lib"):
        raise ValueError("this product has no picture folder of its own")
    lib = assetlib.product_lib(d, P)
    data = jload(lib) or {}
    assets = data.get("assets") or []
    entry = next((e for e in assets if e.get("id") == pid), None)
    if entry is None:
        raise ValueError(f"no picture {pid}")
    f = assetlib.file_of(lib, entry)
    folder = assetlib.product_folder(d, P).resolve()
    if f.exists() and folder in f.resolve().parents:
        f.unlink()
    data["assets"] = [e for e in assets if e.get("id") != pid]
    jdump(lib, data)
    gone = _rel(d, f)
    P["pictures"] = [p for p in P.get("pictures", []) if p.get("done") != gone]
    jdump(d / "product.json", P)


def picture_file(slug, name):
    """A file of the product's asset folder (its thumbnails in the UI)."""
    d, P, _ = store.product(slug)
    folder = assetlib.product_folder(d, P)
    p = folder / name
    if Path(name).name != name or p.suffix.lower() not in (".png", ".webp", ".jpg", ".jpeg") or not p.is_file():
        raise NotFound(name)
    return p


def results(slug):
    d, P, M = store.product(slug)
    return {"mixes": [result(d, P, M, mid) for mid in M], "ads_dir": P.get("ads_dir")}


def ad_file(slug, mid):
    d, P, M = store.product(slug)
    if mid not in M:
        raise NotFound(mid)
    p = B.ad_path(P, M[mid])
    if not p or not p.exists():
        raise NotFound(f"{mid}: no ad yet")
    return p


def work_file(mid, name):
    p = config.HF / mid / ".work" / name
    if Path(name).name != name or not p.exists():
        raise NotFound(name)
    return p


def snap_file(mid, name):
    p = config.HF / mid / ".work" / "snaps" / name
    if Path(name).name != name or not p.exists():
        raise NotFound(name)
    return p
