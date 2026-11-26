"""Fresh edits: one clean talking-head footage -> one ad, the skill's steps 1-10.

The app does the mechanical steps as jobs (step 1 new_project.py, step 2 the speaker cutout, the Whisper pass of
step 3), the user sets hook end / body / CTA on the timeline, and Claude does the judgment and the render headless
(stage `fresh`). The marker <project>/.work/fresh.json makes a HyperFrames project a fresh edit of the app."""
import json
import re
import time
from pathlib import Path

from . import config, darija, store
from .jobs import JobFailed
from .store import B, NotFound, jdump, jload

VIDEO = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts"}


def marker(slug):
    return config.HF / slug / ".work" / "fresh.json"


def load(slug):
    """The (project dir, pseudo product, {}) triple the stage runner expects."""
    f = jload(marker(slug))
    if not f:
        raise NotFound(slug)
    proj = config.HF / slug
    P = {"slug": slug, "name": f.get("name") or slug, "product_dir": str(Path(f["footage"]).parent),
         "ads_dir": str(out_dir(f)), "fresh": f}
    return proj, P, {}


def main_footage(proj):
    for p in sorted((proj / "assets" / "footage").glob("main.*")):
        if "cutout" not in p.name:
            return p
    return None


def out_dir(f):
    return Path(f["out_dir"]) if f.get("out_dir") else Path(f["footage"]).parent / "Edited Ads"


def out_path(f):
    """The skill's rule: `<footage name> - Edited.mp4` in the Edited Ads folder; ` v2` when that name holds an
    earlier edit that is not this project's own."""
    stem = Path(f["footage"]).stem
    base = out_dir(f) / f"{stem} - Edited.mp4"
    if f.get("output"):
        return Path(f["output"])
    n, p = 2, base
    while p.exists():
        p = base.with_name(f"{stem} - Edited v{n}.mp4")
        n += 1
    return p


def info(slug):
    f = jload(marker(slug))
    if not f:
        raise NotFound(slug)
    proj = config.HF / slug
    main = main_footage(proj)
    res = jload(proj / ".work" / "fresh_result.json")
    out = Path(res["output"]) if res and res.get("output") else None
    st = store.studio(proj)
    return {**f, "slug": slug, "dir": store.rel(proj), "main": main.name if main else None,
            "project": (proj / "index.html").exists(), "words": (proj / ".work" / "words.json").exists(),
            "darija": darija.state(proj / ".work" / "words.json"),
            "cutout": (proj / "assets" / "footage" / "main_cutout.webm").exists(),
            "sheet": (proj / ".work" / "sheet.jpg").exists(), "final_sheet": (proj / ".work" / "final_sheet.jpg").exists(),
            "result": res, "ad": bool(out and out.exists()), "ad_path": str(out) if out else None,
            "out_path": str(out_path(f)), "session_id": st.get("session_id"), "usage": store.usage(st),
            "snaps": sorted(p.name for p in (proj / ".work" / "snaps").glob("*.png")) if (proj / ".work" / "snaps").is_dir() else []}


def list_all():
    out = []
    for m in config.HF.glob("*/.work/fresh.json"):
        try:
            out.append(info(m.parents[1].name))
        except Exception as e:
            out.append({"slug": m.parents[1].name, "error": str(e)})
    return sorted(out, key=lambda x: x.get("created", ""), reverse=True)


def slug_for(footage, wanted=None):
    base = re.sub(r"[^a-z0-9]+", "-", (wanted or Path(footage).stem).lower()).strip("-") or "footage"
    base = re.sub(r"^[^a-z]+", "", base) or "footage"
    slug, n = base, 2
    while (config.HF / slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


def create(footage, slug=None, out_dir_=None, name=None, whisper_prompt=""):
    src = Path(footage).expanduser()
    if not src.is_file() or src.suffix.lower() not in VIDEO:
        raise ValueError(f"not a video file: {footage}")
    slug = slug_for(src, slug)
    proj = config.HF / slug
    (proj / ".work").mkdir(parents=True)
    f = {"slug": slug, "name": name or src.stem, "footage": str(src.resolve()), "out_dir": str(Path(out_dir_).expanduser()) if out_dir_ else None,
         "whisper_prompt": whisper_prompt.strip(), "marks": None, "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "duration": None, "fps": None, "frames": None}
    jdump(marker(slug), f)
    return slug


def set_marks(slug, marks):
    f = jload(marker(slug))
    if not f:
        raise NotFound(slug)
    dur = f.get("duration")
    m = marks.model_dump()
    if m["body_start"] < m["hook_end"]:
        raise ValueError("the body starts at the hook end or later")
    if not m["body_start"] < m["cta_start"]:
        raise ValueError("the CTA starts after the body")
    if dur and not m["cta_start"] < dur:
        raise ValueError(f"the CTA must start before the end ({dur} s)")
    f["marks"] = {k: round(v, 4) for k, v in m.items()}
    jdump(marker(slug), f)
    return info(slug)


def set_fields(slug, **kw):
    f = jload(marker(slug))
    if not f:
        raise NotFound(slug)
    f.update({k: v for k, v in kw.items() if v is not None})
    jdump(marker(slug), f)
    return info(slug)


# ------------------------------------------------------------------ the mechanical jobs

def init_job(ctx, job, spec):
    """Step 1: new_project.py (1080x1920 copy, index.html from the reference, 16 kHz wav, contact sheet)."""
    slug = job["slug"]
    f = jload(marker(slug))
    if (config.HF / slug / "index.html").exists():
        ctx.log("sys", "project exists already")
        return {"skipped": True}
    lines = []
    ctx.log("sys", f"$ new_project.py \"{f['footage']}\" {slug}")
    code = ctx.spawn([config.skill_python(), str(config.SCRIPTS / "new_project.py"), f["footage"], slug],
                     on_line=lambda s: (lines.append(s), ctx.log("out", s)))
    if code != 0:
        raise JobFailed(f"new_project.py exited with {code}")
    text = "\n".join(lines)
    try:
        j = json.loads(text[text.index("{"):])
    except (ValueError, IndexError):
        raise JobFailed("new_project.py printed no summary")
    f.update(duration=j.get("duration"), fps=j.get("fps"), frames=j.get("frames"), size=j.get("size"), reencoded=j.get("reencoded"))
    jdump(marker(slug), f)
    return {"duration": f["duration"], "fps": f["fps"]}


def transcribe_job(ctx, job, spec):
    slug = job["slug"]
    f = jload(marker(slug))
    proj = config.HF / slug
    cmd = [config.skill_python(), str(config.SCRIPTS / "transcribe.py"), str(proj / ".work" / "audio.wav"),
           "--out", str(proj / ".work" / "words.json")]
    if f.get("whisper_prompt"):
        cmd += ["--prompt", f["whisper_prompt"]]
    ctx.log("sys", "$ transcribe.py .work/audio.wav --out .work/words.json")
    if ctx.spawn(cmd) != 0 or not (proj / ".work" / "words.json").exists():
        raise JobFailed("transcription failed")
    return {"words": store.rel(proj / ".work" / "words.json")}


def cutout_job(ctx, job, spec):
    """Step 2: the speaker matte, about 2.3 frames a second on CPU."""
    slug = job["slug"]
    proj = config.HF / slug
    main = main_footage(proj)
    if not main:
        raise JobFailed("the project has no footage yet")
    out = proj / "assets" / "footage" / "main_cutout.webm"
    if out.exists():
        ctx.log("sys", "cutout exists already")
        return {"skipped": True}
    hf, err = store.skill(B.hyperframes)
    if err:
        raise JobFailed(err)
    B.ensure_matte_model()
    frames = (jload(marker(slug)) or {}).get("frames")
    if frames:                                              # the real size, for the ETA and the measured speed
        ctx.jobs.update(ctx.id, work=frames)
        ctx.job["work"] = frames
        ctx.progress(eta_s=ctx.jobs.estimate("cut", frames))
    tmp = out.with_name("main_cutout.part.webm")
    ctx.log("sys", f"$ hyperframes remove-background {main.name} -o {out.name} --quality best")
    code = ctx.spawn([*hf, "remove-background", str(main), "-o", str(tmp), "--quality", "best"], cwd=proj)
    if code != 0 or not tmp.exists():
        raise JobFailed(f"remove-background failed (exit {code})")
    tmp.replace(out)
    return {"cutout": store.rel(out)}
