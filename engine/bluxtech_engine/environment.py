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


def hf_cache():
    """HyperFrames' own cache (its Chrome, the cutout runtime and model, fonts)."""
    return Path(os.environ.get("HYPERFRAMES_CACHE_DIR") or (Path.home() / ".cache" / "hyperframes"))


def matte_model():
    return hf_cache() / "background-removal" / "models" / "u2net_human_seg.onnx"


def chrome_cached():
    """The headless Chrome HyperFrames renders with (`hyperframes browser ensure` downloads it, about 270 MB)."""
    d = hf_cache() / "chrome"
    return d.is_dir() and (any(d.rglob("chrome-headless-shell.exe")) or any(d.rglob("chrome.exe")))


def cutout_runtime_cached():
    """onnxruntime-node, which HyperFrames installs on the first cutout (about 210 MB)."""
    d = hf_cache() / "optional"
    return d.is_dir() and any(p.name.startswith("onnxruntime-node") for p in d.iterdir())


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
    add("chrome", "Chrome for rendering (HyperFrames)", chrome_cached(),
        "cached" if chrome_cached() else "downloaded by Setup (about 270 MB), or on the first render", required=False, fix="setup")
    add("cutout", "Cutout runtime (onnxruntime for HyperFrames)", cutout_runtime_cached(),
        "installed" if cutout_runtime_cached() else "installed by Setup (about 210 MB), or on the first cutout", required=False, fix="setup")
    runner = settings.runner()
    if runner == "sdk":
        key, cli = bool(settings.api_key()), config.bundled_claude()
        add("claude", "Claude (Agent SDK + your API key)", key and cli,
            ("API key set" if key else "no API key: add one in Settings") + ("" if cli else "; the bundled claude.exe is missing"))
    else:
        add("claude", "Claude Code CLI (your login)", config.claude_bin(),
            config.claude_bin() or "not found: install Claude Code and run `claude` once, or switch to the API key runner")
    lib_ok = (config.GPT_DIR / "library.json").exists()
    add("gpt", "Illustration library (the orange health pictures)", lib_ok,
        str(config.GPT_DIR) if lib_ok else "no library: ads get the jar and the discs only", required=False, fix="setup")
    codex = config.codex_bin()
    add("codex", "GPT drawing tool (the ChatGPT / Codex desktop app)", codex,
        codex or "not installed: new pictures are not drawn, the library is used as it is", required=False)
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
    # the illustration library, when this PC has no GPT asset tool of its own (replaced on every new app version)
    lib_src, lib_dst = res / "assets", config.ROOT / "assets"
    if config.GPT_DIR == lib_dst and (lib_src / "library.json").exists():
        stamp = lib_dst / ".bluxtech-version"
        if not lib_dst.exists() or not stamp.exists() or stamp.read_text(encoding="utf-8").strip() != config.VERSION:
            if lib_dst.exists():
                shutil.rmtree(lib_dst)
            shutil.copytree(lib_src, lib_dst)
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
    link_root_node_modules()


def link_root_node_modules():
    """`npx hyperframes ...` (what the skill and Claude's commands run from the workspace root) must resolve to the
    bundled HyperFrames in _hyperframes/node_modules: npx looks for node_modules/.bin next to the current folder and
    otherwise fetches the latest version from the registry. A junction <root>/node_modules -> _hyperframes/node_modules
    makes it find ours, offline, at the tested version. Both modes."""
    root_nm, nm = config.ROOT / "node_modules", config.HF / "node_modules"
    if not (nm / "hyperframes").is_dir():
        return
    if root_nm.is_junction() or root_nm.is_symlink():
        if root_nm.exists() and os.path.realpath(root_nm) == os.path.realpath(nm):
            return
        root_nm.rmdir()                                  # stale: points elsewhere or at a folder that is gone
    elif root_nm.exists():
        return                                           # the user's own node_modules: leave it alone
    _junction(root_nm, nm)


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
    node, hf = which("node"), hyperframes_cli()
    if node and hf and not chrome_cached():
        ctx.log("sys", "downloading the Chrome HyperFrames renders with (about 270 MB, once)")
        code = ctx.spawn([node, str(hf), "browser", "ensure"], cwd=config.HF)
        if code != 0:
            raise JobFailed("the Chrome download failed: check the connection and run Setup again")
        done["chrome"] = True
    if node and hf and not cutout_runtime_cached():
        # HyperFrames installs onnxruntime-node the first time it cuts something out: a 64 px picture does it here
        ctx.log("sys", "installing the cutout runtime (onnxruntime for HyperFrames, about 210 MB, once)")
        work = config.DATA / "setup"
        work.mkdir(parents=True, exist_ok=True)
        tiny = work / "tiny.png"
        code = ctx.spawn([config.skill_python(), "-c",
                          "from PIL import Image, ImageDraw; im = Image.new('RGB', (64, 64), 'white'); "
                          "ImageDraw.Draw(im).ellipse((16, 8, 48, 56), fill=(120, 20, 20)); "
                          f"im.save(r'{tiny}')"])
        if code == 0:
            code = ctx.spawn([node, str(hf), "remove-background", str(tiny), "-o", str(work / "tiny_cut.png")], cwd=config.HF)
        if code != 0 or not cutout_runtime_cached():
            raise JobFailed("installing the cutout runtime failed: check the connection and run Setup again")
        done["cutout"] = True
    ctx.log("sys", "setup finished: " + (", ".join(done) if done else "nothing was missing"))
    return {"installed": list(done), "check": check()}
