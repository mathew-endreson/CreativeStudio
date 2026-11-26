"""What the pipeline needs on this machine, and the workspace layout.

check() is read-only and feeds the Setup screen. init_workspace() lays the skill and the HyperFrames install out
in the workspace (installed mode only; a dev workspace is the project root and is never touched). setup_job() is the
slow part the Setup screen queues: the Whisper model, the matte model, HyperFrames when it is not bundled."""
import os
import shutil
import subprocess
from pathlib import Path

from . import config, settings
from .jobs import JobFailed

WHISPER_MODEL = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
HYPERFRAMES_VERSION = "0.9.38"


def which(name):
    for d in config.tool_dirs():
        for ext in ("", ".exe", ".cmd"):
            p = d / (name + ext)
            if p.is_file():
                return str(p)
    return shutil.which(name)


def hyperframes_cli():
    js = config.HF / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
    return js if js.exists() else None


def whisper_cached():
    hub = Path(os.environ.get("HF_HOME") or (Path.home() / ".cache" / "huggingface")) / "hub"
    d = hub / ("models--" + WHISPER_MODEL.replace("/", "--"))
    return d.is_dir() and any(d.rglob("model.bin"))


def matte_model():
    return Path.home() / ".cache" / "hyperframes" / "background-removal" / "models" / "u2net_human_seg.onnx"


def python_ok():
    py = config.skill_python()
    try:
        r = subprocess.run([py, "-c", "import numpy, cv2, PIL, faster_whisper; print('ok')"], capture_output=True,
                           text=True, timeout=90, env=config.child_env())
        return (r.returncode == 0 and "ok" in r.stdout), (r.stderr or r.stdout).strip()[-300:] or py
    except Exception as e:
        return False, f"{py}: {e}"


def check():
    items = []

    def add(id_, label, ok, detail="", required=True, fix=None):
        items.append({"id": id_, "label": label, "ok": bool(ok), "detail": str(detail), "required": required, "fix": fix})

    ok, det = python_ok()
    add("python", "Python with numpy, OpenCV, Pillow and faster-whisper", ok, det)
    add("ffmpeg", "FFmpeg", which("ffmpeg"), which("ffmpeg") or "not found on PATH")
    add("ffprobe", "FFprobe", which("ffprobe"), which("ffprobe") or "not found on PATH")
    add("node", "Node.js", which("node"), which("node") or "not found on PATH (HyperFrames needs it)")
    add("hyperframes", "HyperFrames renderer", hyperframes_cli(), str(hyperframes_cli() or config.HF / "node_modules"), fix="setup")
    add("skill", "camel-gpt skill", (config.SKILL / "SKILL.md").exists(), str(config.SKILL), fix="setup")
    dz = config.ROOT / ".claude" / "skills" / "darijadz"
    add("darijadz", "darijadz skill (Claude corrects Whisper's Darija, darija_lint checks it)",
        (dz / "scripts" / "darija_lint.py").exists(), str(dz), required=False, fix="setup")
    add("whisper", "Whisper model (large-v3-turbo)", whisper_cached(),
        "cached" if whisper_cached() else "downloaded by Setup, or on the first transcription", required=False, fix="setup")
    add("matte", "Speaker matte model (u2net)", matte_model().exists(),
        str(matte_model()) if matte_model().exists() else "HyperFrames downloads it on the first cutout", required=False, fix="setup")
    runner = settings.runner()
    if runner == "sdk":
        key, cli = bool(settings.api_key()), config.bundled_claude()
        add("claude", "Claude (Agent SDK + your API key)", key and cli,
            ("API key set" if key else "no API key: add one in Settings") + ("" if cli else "; the bundled claude.exe is missing"))
    else:
        add("claude", "Claude Code CLI (your login)", config.claude_bin(),
            config.claude_bin() or "not found: install Claude Code and run `claude` once, or switch to the API key runner")
    add("gpt", "GPT asset tool (ChatGPT / Codex app)", (config.GPT_DIR / "library.json").exists(), str(config.GPT_DIR), required=False)
    add("workspace", "Workspace", config.ROOT.is_dir() and os.access(config.ROOT, os.W_OK), str(config.ROOT))
    free = shutil.disk_usage(config.ROOT).free // 2 ** 30 if config.ROOT.exists() else 0
    add("disk", "Free disk space", free >= 10, f"{free} GB free (cutouts and renders need room)", required=False)
    return {"ok": all(i["ok"] for i in items if i["required"]), "items": items, "mode": config.MODE,
            "workspace": str(config.ROOT), "runner": runner, "resources": str(config.RESOURCES or "")}


def _junction(link: Path, target: Path):
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link, target_is_directory=True)


def init_workspace():
    """installed mode: the workspace laid out like the project root. The skill is ours (replaced on every new app
    version); _hyperframes holds the user's work and is only ever added to."""
    if config.MODE != "installed":
        return
    res = config.RESOURCES
    config.ROOT.mkdir(parents=True, exist_ok=True)
    config.HF.mkdir(exist_ok=True)
    (config.ROOT / "Projects").mkdir(exist_ok=True)
    for name in ("camel-gpt", "darijadz"):
        skill_src, dst = res / "skill" / name, config.ROOT / ".claude" / "skills" / name
        stamp = dst / ".bluxtech-version"
        if skill_src.is_dir():
            ours = stamp.exists()
            if not dst.exists() or (ours and stamp.read_text(encoding="utf-8").strip() != config.VERSION):
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(skill_src, dst)
                stamp.write_text(config.VERSION, encoding="utf-8")
    hf_src = res / "hyperframes"
    nm = config.HF / "node_modules"
    src = hf_src / "node_modules"
    if src.is_dir():
        if nm.is_junction() or nm.is_symlink():
            # ours: point it again when the install moved or its target is gone (a real folder is left alone)
            if not nm.exists() or os.path.realpath(nm) != os.path.realpath(src):
                nm.rmdir()
        if not nm.exists():
            _junction(nm, src)
    for name in ("hyperframes.json", "package.json"):
        if (hf_src / name).exists() and not (config.HF / name).exists():
            shutil.copy2(hf_src / name, config.HF / name)


def setup_job(ctx, job, spec):
    """The Setup screen's job: whatever check() still reports missing that a download can fix."""
    init_workspace()
    done = {}
    if not hyperframes_cli():
        npm = which("npm")
        if not npm:
            raise JobFailed("HyperFrames is not installed and npm was not found: install Node.js, then run Setup again")
        ctx.log("sys", f"installing hyperframes@{HYPERFRAMES_VERSION} into {config.HF}")
        if not (config.HF / "package.json").exists():
            (config.HF / "package.json").write_text('{"name": "_hyperframes", "private": true}', encoding="utf-8")
        code = ctx.spawn([npm, "install", "--no-audit", "--no-fund", f"hyperframes@{HYPERFRAMES_VERSION}"], cwd=config.HF)
        if code != 0:
            raise JobFailed(f"npm install hyperframes failed (exit {code})")
        done["hyperframes"] = True
    if not whisper_cached():
        ctx.log("sys", f"downloading the Whisper model {WHISPER_MODEL} (about 1.6 GB, once)")
        code = ctx.spawn([config.skill_python(), "-c",
                          f"from faster_whisper import download_model; print(download_model('{WHISPER_MODEL}'))"])
        if code != 0:
            raise JobFailed("the Whisper model download failed: check the connection and run Setup again")
        done["whisper"] = True
    m = matte_model()
    if not m.exists():
        src = (config.RESOURCES / "models" / "u2net_human_seg.onnx") if config.RESOURCES else None
        if src and src.exists():
            m.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, m)
            done["matte"] = True
            ctx.log("sys", f"matte model copied to {m}")
        else:
            ctx.log("sys", "no bundled matte model: HyperFrames downloads it on the first cutout")
    ctx.log("sys", "setup finished: " + (", ".join(done) if done else "nothing was missing"))
    return {"installed": list(done), "check": check()}
