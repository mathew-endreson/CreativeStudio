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

from . import config, store
from .jobs import JobFailed
from .store import B, NotFound, jdump, jload

VIDEO = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts"}
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
    """Write _hyperframes/<slug>_src/product.json for a folder of finished ads (and the product's pictures)."""
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
         "offers": [o.model_dump() for o in spec.offers], "duplicates": list(spec.duplicates),
         "pictures": pictures, "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "created_by": "bluxtech-studio"}
    (d / "work").mkdir(parents=True)
    (d / "img").mkdir()
    jdump(d / "product.json", P)
    jdump(d / "mixes.json", {})
    return slug, pictures


def pictures_job(ctx, job, spec):
    """The product's own pictures: a white-background packshot through cutout_product.py --symmetric (it becomes
    the project's jar), offer photos through offer_cutout.py (RAW files through rw2_preview.py first), illustrations
    copied as they are. Each becomes a project asset copied into every mix."""
    d, P, _ = store.product(job["slug"])
    py, S = config.skill_python(), config.SCRIPTS
    assets = {a["to"]: a for a in P.get("project_assets", [])}
    made = []
    for i, pic in enumerate(P.get("pictures", [])):
        src = Path(pic["file"])
        if not src.exists():
            ctx.log("error", f"missing: {src}")
            continue
        if src.suffix.lower() == ".rw2":
            jpg = d / "img" / f"{src.stem}.jpg"
            ctx.log("sys", f"$ rw2_preview.py {src.name}")
            if ctx.spawn([py, str(S / "rw2_preview.py"), str(src), str(jpg)]) != 0:
                ctx.log("error", f"rw2_preview failed on {src.name}")
                continue
            src = jpg
        if pic["tag"] == "packshot":
            out, to = d / "img" / "jar.png", "assets/img/jar.png"
            ctx.log("sys", f"$ cutout_product.py {src.name} --symmetric")
            code = ctx.spawn([py, str(S / "cutout_product.py"), str(src), str(out), "--symmetric"])
        elif pic["tag"] == "offer":
            stem = re.sub(r"[^a-z0-9]+", "-", (pic.get("label") or src.stem).lower()).strip("-") or f"offer{i}"
            out, to = d / "img" / f"offer-{stem}.png", f"assets/img/offer-{stem}.png"
            ctx.log("sys", f"$ offer_cutout.py {src.name}")
            code = ctx.spawn([py, str(S / "offer_cutout.py"), str(src), str(out)])
        else:
            stem = re.sub(r"[^a-z0-9]+", "-", (pic.get("label") or src.stem).lower()).strip("-") or f"pic{i}"
            out, to = d / "img" / f"{stem}{src.suffix.lower()}", f"assets/img/{stem}{src.suffix.lower()}"
            import shutil
            shutil.copy2(src, out)
            code = 0
        if code != 0 or not out.exists():
            ctx.log("error", f"{pic['tag']} {src.name}: exit {code}")
            continue
        assets[to] = {"from": f"img/{out.name}", "to": to, "tag": pic["tag"], "label": pic.get("label", "")}
        made.append(to)
    P["project_assets"] = list(assets.values())
    jdump(d / "product.json", P)
    ctx.log("sys", f"project assets: {', '.join(made) or 'none'}")
    return {"assets": made}


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


def cut_work(slug, ids):
    """Frames the cutouts of these mixes still need (for the ETA)."""
    d, P, M = store.product(slug)
    plan, _ = store.skill(B.plan_cuts, d, P, M, ids, all_gfx=True)
    return sum(p["frames"] for p in plan or []), plan or []


# ------------------------------------------------------------------ results

def beat_lines(spec):
    out = []
    for b in spec.get("beats", []):
        words = " ".join(re.sub(r"<[^>]+>", "", l.get("html", "")) for l in b.get("labels", []))
        out.append({"in": b.get("in"), "out": b.get("out"), "side": b.get("side"), "graphic": b.get("lib") or b.get("kind"),
                    "label": words.strip(), "check": b.get("check")})
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
            "beats": beat_lines(beats) if beats else [], "revision": rev,
            "gpt_drawings": notes.get("gpt_drawings", []), "unsure": notes.get("unsure", []),
            "snaps": [f for f in (check or {}).get("files", []) if f.endswith((".png", ".jpg"))],
            "sheets": [n for n in ("final_sheet.jpg", "joins_sheet.jpg") if (proj / ".work" / n).exists()],
            "warnings": (build or {}).get("place_warnings", []) + (build or {}).get("no_cutout", [])}


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
