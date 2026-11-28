"""Where things are, for the two ways the engine runs.

dev        from this source tree (bluxtech-studio/engine): the workspace is the SH-101126 project root, with its
           .claude/skills/bluxstudio-skill, _hyperframes and batch folders; python, node and ffmpeg come from PATH; the UI
           is desktop/dist.
installed  started by the BluxTech Studio desktop app from its resources folder (--resources): the workspace is a
           folder the user owns (Documents\\BluxTech Studio by default), laid out like the project root by
           environment.init_workspace(); python, node, ffmpeg and HyperFrames come from the resources.

The engine owns only its database (settings, license, job queue, logs). Every result is a file in the workspace.
"""
import json
import os
import shutil
import sys
from pathlib import Path

APP_NAME = "CreativeStudio"   # the product's display name; folder names and the bundle identifier keep the old one
VERSION = "0.1.0"

PKG = Path(__file__).resolve().parent                # bluxtech_engine/
ENGINE = PKG.parent                                  # bluxtech-studio/engine  (or <resources>/engine)
STUDIO = ENGINE.parent                               # bluxtech-studio          (or <resources>)
PROMPTS = ENGINE / "prompts"

MODE = "dev"
ROOT = STUDIO.parent                                 # the workspace
RESOURCES = None
DATA = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "BluxTech Studio"
DIST = STUDIO / "desktop" / "dist"
AUTH_CONFIG = STUDIO / "desktop" / "supabase.config.json"
LICENSE_KEY = STUDIO / "desktop" / "license_public_key.pem"
HOST, PORT, AUTH = "127.0.0.1", 8766, True
HF = SKILL = SCRIPTS = BATCH = None
GPT_TOOL_DIR = Path.home() / "Documents" / "ChatGPT" / "asstets tool ebox"   # the GPT asset tool's own folder
GPT_DIR = GPT_TOOL_DIR                               # the illustration library in use (see init)


def _plain(p: Path) -> Path:
    """Without Windows' \\\\?\\ verbatim prefix (a canonicalized path from the desktop shell can carry it): a junction
    whose target has that prefix does not resolve, and PATH entries carrying it confuse some tools."""
    s = str(p)
    if s.startswith("\\\\?\\") and not s.startswith("\\\\?\\UNC\\"):
        return Path(s[4:])
    return p


def init(workspace=None, resources=None, port=None, auth=True, data=None):
    global MODE, ROOT, RESOURCES, DIST, AUTH_CONFIG, LICENSE_KEY, DATA, HF, SKILL, SCRIPTS, BATCH, PORT, AUTH
    if resources:
        MODE = "installed"
        RESOURCES = _plain(Path(resources).resolve())
        DIST = RESOURCES / "ui"
        AUTH_CONFIG = RESOURCES / "supabase.config.json"
        LICENSE_KEY = RESOURCES / "license_public_key.pem"
        ROOT = Path(workspace).resolve() if workspace else Path.home() / "Documents" / "BluxTech Studio"
        if not data:
            # beside the WebView2 profile, under Tauri's identifier: never inside the install dir, which is
            # %LOCALAPPDATA%\BluxTech Studio (the same name as the dev data dir above)
            DATA = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "com.bluxtech.studio" / "engine"
    else:
        MODE = "dev"
        ROOT = Path(workspace).resolve() if workspace else STUDIO.parent
    if data:
        DATA = Path(data).resolve()
    # the illustration library: the GPT asset tool's folder when this PC has it (the owner's machine), else the copy
    # the installer ships, laid into the workspace by environment.init_workspace (BLUXTECH_GPT_DIR overrides both)
    global GPT_DIR
    env_lib = os.environ.get("BLUXTECH_GPT_DIR")
    if env_lib:
        GPT_DIR = Path(env_lib)
    elif (GPT_TOOL_DIR / "library.json").exists():
        GPT_DIR = GPT_TOOL_DIR
    elif RESOURCES and (RESOURCES / "assets" / "library.json").exists():
        GPT_DIR = ROOT / "assets"
    HF = ROOT / "_hyperframes"
    SKILL = ROOT / ".claude" / "skills" / "bluxstudio-skill"
    SCRIPTS = SKILL / "scripts"
    BATCH = SCRIPTS / "batch.py"
    if port is not None:
        PORT = port
    AUTH = auth
    DATA.mkdir(parents=True, exist_ok=True)


def settings():
    """The shape camel-studio's modules expect: the Claude model/effort and the queue limits."""
    from . import settings as S
    return {"claude": {"model": S.get("model"), "effort": S.get("effort")},
            "limits": S.get("limits") or {"heavy": 1, "claude": 2, "light": 3}}


def tool_dirs():
    """Folders put first on PATH for every child process (the installed runtime)."""
    if not RESOURCES:
        return []
    return [p for p in (RESOURCES / "python", RESOURCES / "python" / "Scripts", RESOURCES / "node",
                        RESOURCES / "ffmpeg" / "bin") if p.is_dir()]


def skill_python():
    """The interpreter the skill's scripts run under. dev: the base Python this venv was made from (it has
    Whisper, OpenCV, numpy). installed: the embedded runtime, which is also what runs the engine."""
    env = os.environ.get("CAMEL_PYTHON")
    if env:
        return env
    if MODE == "installed":
        return sys.executable
    base = Path(sys.base_prefix) / ("python.exe" if os.name == "nt" else "bin/python3")
    return str(base) if base.exists() else sys.executable


def bundled_claude():
    """claude.exe shipped inside the Agent SDK package (no Claude Code install needed on the machine)."""
    try:
        import claude_agent_sdk
        p = Path(claude_agent_sdk.__file__).parent / "_bundled" / ("claude.exe" if os.name == "nt" else "claude")
        return str(p) if p.is_file() else None
    except ImportError:
        return None


def claude_bin():
    """The local claude CLI for the `cli` runner: the user's own Claude Code install, then the SDK's bundled copy."""
    home = Path.home()
    cands = [os.environ.get("CAMEL_CLAUDE"), shutil.which("claude"), shutil.which("claude.exe"),
             home / ".local" / "bin" / "claude.exe", home / ".local" / "bin" / "claude",
             Path(os.environ.get("APPDATA", "")) / "npm" / "claude.cmd",
             home / ".claude" / "local" / "claude.exe", bundled_claude()]
    for c in cands:
        if c and Path(c).is_file():
            return str(c)
    return None


def codex_bin():
    """The Codex CLI the skill draws new pictures with (the ChatGPT desktop app ships it), or None: then the ads use
    the library as it is and no drawing is asked for."""
    import re
    for key in ("GPT_ASSETS_CODEX", "CODEX_CLI_PATH"):           # the same search as the skill's gpt_assets.find_codex
        p = os.environ.get(key)
        if p and Path(p).is_file():
            return p
    cfg = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "config.toml"
    if cfg.is_file():
        m = re.search(r"""CODEX_CLI_PATH\s*=\s*['"]([^'"]+)['"]""", cfg.read_text(encoding="utf-8", errors="ignore"))
        if m and Path(m.group(1)).is_file():
            return m.group(1)
    try:
        apps = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "WindowsApps"
        hits = sorted(apps.glob("OpenAI.Codex_*/app/resources/codex.exe"), reverse=True)
        if hits:
            return str(hits[0])
    except OSError:
        pass
    return shutil.which("codex")


def child_env(extra=None):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1"}
    dirs = tool_dirs()
    if dirs:
        env["PATH"] = os.pathsep.join([str(d) for d in dirs] + [env.get("PATH", "")])
    # the skill's asset_lib.py / gpt_assets.py read the library from here (their default is the GPT tool's folder)
    env.setdefault("GPT_ASSETS_PROJECT", str(GPT_DIR))
    env.setdefault("CAMEL_GPT_LIBRARY", str(GPT_DIR / "library.json"))
    if extra:
        env.update(extra)
    return env


def auth_config():
    """The public Supabase config {url, publishableKey} the UI signs in with, or None = licensing off.
    The file may name the key publishableKey or anonKey (the legacy name)."""
    p = Path(AUTH_CONFIG)
    if not p.exists():
        return None
    try:
        cfg = json.loads(p.read_text(encoding="utf-8-sig"))
    except ValueError:
        return None
    url, key = str(cfg.get("url") or "").rstrip("/"), cfg.get("publishableKey") or cfg.get("anonKey")
    return {"url": url, "publishableKey": key} if url.startswith("https://") and key else None
