#!/usr/bin/env python3
"""gpt-assets (bluxstudio-skill edition): make house-style illustrations (orange, or the colours of the
library folder's brand.json, see brand_guide.py) with the ChatGPT / Codex desktop app and file them, with
their keywords, in the asset library.

The Codex desktop app ships a `codex` command-line program that is signed in
with the user's ChatGPT account and has a built-in `image_gen` tool (no API
key needed). This script drives it non-interactively (`codex exec`):

  python gpt_assets.py generate --name glossy-kidneys --look glossy --prompt-file p.txt
  python gpt_assets.py generate --name flat-person-headache --look flat --subject "person with a headache"
  python gpt_assets.py status     check the connection to the app and the library
  python gpt_assets.py serve      local MCP server over stdio (optional)

Every request runs inside the GPT project folder (default:
~/Documents/ChatGPT/asstets tool ebox), whose AGENTS.md and style/ copy keep GPT
on style. GPT saves the PNG to generated/ AND returns keywords for it (Algerian
Darija, Arabic, French, English), a motion hint and an on-screen label; the
image is then registered in library.json in that folder (see asset_lib.py),
which is how /bluxstudio-skill finds it again from what a speaker says.
With --dest the old orange-health-assets behaviour also runs: raw copy in
<dest>/_raw/ and a finished, palette-locked WebP in <dest>/.

Needs the Python standard library and Pillow (numpy + scipy for --dest finishing).
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
FINISH_SCRIPT = SKILL_DIR / "scripts" / "finish_asset.py"
REFS_DIR = SKILL_DIR / "assets" / "refs"
CODEX_HOME = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
DEFAULT_GPT_PROJECT = Path.home() / "Documents" / "ChatGPT" / "asstets tool ebox"
TIMEOUT_S = int(os.environ.get("GPT_ASSETS_TIMEOUT", "900"))
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
IMAGE_EXT = {".png", ".webp", ".jpg", ".jpeg"}
SERVER_NAME, SERVER_VERSION = "gpt-assets", "2.0.0"

LOOKS = {
    "glossy": {
        "canvas": "square",
        "aspect": "square, 1:1 (1024x1024)",
        "refs": ["glossy-lungs", "glossy-bronchial-tree"],
    },
    "flat": {
        "canvas": "wide",
        "aspect": "landscape, 3:2 (1536x1024)",
        "refs": ["flat-throat-crosssection", "flat-person-coughing"],
    },
}

KEYWORD_RULES = """Keywords are how Claude finds an illustration later: a script matches them against a Whisper
transcript of an Algerian speaker (Darija mixed with French) and shows the image as B-roll behind
him when the word is said. Write:
- subject: one short English sentence describing the image.
- motion: "breathe" (lungs, airways, throat, breathing), "shake" (a person coughing, sneezing or in
  pain) or "shine" (organs, objects, calm people).
- label: a 1-3 word on-screen label in Arabic script with the key word in <em>...</em>,
  e.g. "وجع <em>الكرش</em>".
- keywords.darija: 10-25 words or short phrases an Algerian would SAY for this subject, in Arabic
  script the way Whisper writes Algerian Darija: definite and bare forms, possessive and verb forms,
  common spellings (for a stomach: الكرش، كرشي، المعدة، معدتي، يوجعني كرشي), and French medical
  words in Arabic script (لاستوما). Most specific first.
- keywords.ar: 5-15 Modern Standard Arabic words or phrases.
- keywords.fr: 3-10 French words or phrases, Latin script.
- keywords.en: 3-8 English words.
Only words that point at THIS subject. Never a generic word on its own (وجع، مرض، صحة، الجسم، دوا،
عسل، طبيعي، douleur, santé, maladie): put it in a phrase instead (وجع الراس). No duplicates."""

_STR_LIST = {"type": "array", "items": {"type": "string"}}
KW_SCHEMA = {
    "type": "object",
    "properties": {"darija": _STR_LIST, "ar": _STR_LIST, "fr": _STR_LIST, "en": _STR_LIST},
    "required": ["darija", "ar", "fr", "en"],
    "additionalProperties": False,
}
KEYWORD_PROPS = {
    "subject": {"type": "string"},
    "motion": {"type": "string", "enum": ["breathe", "shake", "shine"]},
    "label": {"type": "string"},
    "keywords": KW_SCHEMA,
}
RESULT_SCHEMA = {
    "type": "object",
    "properties": {"files": _STR_LIST, "note": {"type": "string"}, "prompt": {"type": "string"}, **KEYWORD_PROPS},
    "required": ["files", "note", "prompt", *KEYWORD_PROPS.keys()],
    "additionalProperties": False,
}

AGENTS_MD = """# EBOX DZ asset studio

This folder is the GPT side of the EBOX DZ asset pipeline. Claude sends image
requests here through the local `gpt-assets` tool, and the user may also type
requests directly. Every request is for an illustration in one fixed style.

## Rules for every image request

1. Follow `style/style-identity-guide.md`. It is the only allowed style:
   monochrome orange health/anatomy illustrations, either glossy see-through
   gel organs (square) or soft matte silhouettes facing right (wide); one
   subject; transparent background; no text.
2. Generate with the built-in `image_gen` tool. Do not use the image CLI
   fallback, an API key, or drawing with SVG/HTML/Python.
3. Use the matching images in `style/refs/` as style references (glossy:
   `glossy-*.png`, flat: `flat-*.png`). Match their colour, material and
   lighting, and draw only the requested subject.
4. Ask for a transparent background and keep the alpha channel.
5. If the request is only a word or two ("Human", "heart"), use section 7
   "Short requests" of the guide instead of asking questions.
6. If a request contains a ready-written prompt, use it exactly as written.
7. Save each final image as PNG in `generated/`, named `<look>-<subject>.png`
   (for example `generated/glossy-heart.png`). Never overwrite a file; add
   `-2`, `-3` instead.
8. Reply with the saved path(s) and the prompt you used.

`.gpt-assets/` holds request logs written by the tool and `library.json` is
the keyword index Claude keeps. Leave both alone.
"""


# ---------------------------------------------------------------- helpers

def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "asset"


def run_text(cmd: list[str], timeout: int = 60) -> str:
    try:
        # stdin=DEVNULL matters in `serve` mode: a child that inherits the MCP
        # stdin pipe (which the server is blocked reading) hangs at startup on
        # Windows.
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, creationflags=NO_WINDOW,
                           stdin=subprocess.DEVNULL)
        return (r.stdout + r.stderr).strip()
    except Exception as exc:  # noqa: BLE001 - report anything to the caller
        return f"error: {exc}"


def find_codex() -> str | None:
    """The Codex CLI: env override, the path the desktop app records in its
    config, the app package itself, then PATH."""
    for key in ("GPT_ASSETS_CODEX", "CODEX_CLI_PATH"):
        p = os.environ.get(key)
        if p and Path(p).is_file():
            return p
    cfg = CODEX_HOME / "config.toml"
    if cfg.is_file():
        m = re.search(r"""CODEX_CLI_PATH\s*=\s*['"]([^'"]+)['"]""",
                      cfg.read_text(encoding="utf-8", errors="ignore"))
        if m and Path(m.group(1)).is_file():
            return m.group(1)
    apps = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "WindowsApps"
    try:
        hits = sorted(apps.glob("OpenAI.Codex_*/app/resources/codex.exe"), reverse=True)
        if hits:
            return str(hits[0])
    except OSError:
        pass
    return shutil.which("codex")


def find_guide() -> Path | None:
    candidates = [SKILL_DIR / "references" / "style-identity-guide.md",
                  Path.cwd() / "style-identity-guide.md"]
    return next((p for p in candidates if p.is_file()), None)


def gpt_project_dir(override: str | None = None) -> Path:
    return Path(override or os.environ.get("GPT_ASSETS_PROJECT") or DEFAULT_GPT_PROJECT)


def free_stem(dest: Path, base: str) -> str:
    """First of base, base-2, base-3 ... unused both as asset and as raw."""
    k = 1
    while True:
        stem = base if k == 1 else f"{base}-{k}"
        if not (dest / f"{stem}.webp").exists() and not any((dest / "_raw").glob(f"{stem}.*")):
            return stem
        k += 1


def free_generated(project: Path, base: str, suffix: str = ".png") -> Path:
    k = 1
    while True:
        p = project / "generated" / (f"{base}{suffix}" if k == 1 else f"{base}-{k}{suffix}")
        if not p.exists():
            return p
        k += 1


def tail(path: Path, lines: int = 12) -> str:
    try:
        rows = path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    except OSError:
        return "(no log)"
    return "\n".join(r if len(r) <= 400 else r[:400] + " ..." for r in rows)


def preview_b64(path: str | Path, size: int = 300) -> str:
    """The image on white and on dark side by side, as base64 PNG."""
    from PIL import Image

    im = Image.open(path).convert("RGBA")
    im.thumbnail((size - 16, size - 16))
    sheet = Image.new("RGB", (size * 2, size), (255, 255, 255))
    off = ((size - im.width) // 2, (size - im.height) // 2)
    for x, bg in ((0, (255, 255, 255, 255)), (size, (30, 30, 30, 255))):
        tile = Image.new("RGBA", (size, size), bg)
        tile.alpha_composite(im, off)
        sheet.paste(tile.convert("RGB"), (x, 0))
    buf = io.BytesIO()
    sheet.save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ---------------------------------------------------------------- GPT project

def ensure_gpt_project(project: Path) -> None:
    """Folder layout, style guide + references for the GPT side. Never overwrites
    what is already there: the folder is shared with the 9owa orange-health-assets
    tool and the user's own edits."""
    from PIL import Image

    (project / "generated").mkdir(parents=True, exist_ok=True)
    refs_out = project / "style" / "refs"
    refs_out.mkdir(parents=True, exist_ok=True)
    guide = find_guide()
    if guide and not (project / "style" / "style-identity-guide.md").exists():
        shutil.copyfile(guide, project / "style" / "style-identity-guide.md")
    for src in REFS_DIR.glob("*.webp"):
        dst = refs_out / f"{src.stem}.png"
        if not dst.exists():
            Image.open(src).save(dst)
    agents = project / "AGENTS.md"
    if not agents.exists():
        agents.write_text(AGENTS_MD, encoding="utf-8")
    if (project / "brand.json").is_file():
        # a library drawn in its own brand (CreativeStudio's Library on a customer PC): AGENTS.md, the guide,
        # the refs and the palette lock's ramp come from brand.json and are rendered again when it changes
        import brand_guide
        brand_guide.apply(project)


def build_request(name: str, look: str, prompt: str, variants: int, project: Path, subject: str = ""):
    spec = LOOKS[look]
    targets = [project / "generated" / (f"{name}.png" if variants == 1 else f"{name}-v{i}.png")
               for i in range(1, variants + 1)]
    if prompt.strip():
        what = ["Use this prompt exactly as written:", "<<<", prompt.strip(), ">>>"]
    else:
        what = [f'This is a short request: "{subject.strip()}". Write the prompt yourself from section 7 '
                f'("Short requests") and the section 10 template for the {look} look in '
                "style/style-identity-guide.md, keeping every fixed word of the template, then use it."]
    text = "\n".join([
        "Image request from Claude (gpt-assets tool, bluxstudio-skill). Follow AGENTS.md and "
        "style/style-identity-guide.md in this folder.",
        "",
        f"Make {variants} image(s): one call to the built-in image_gen tool per image. "
        "Do not use the image CLI fallback, an API key, or SVG/HTML/Python drawing.",
        "The attached images are style references only: match their colour, material, "
        "lighting and level of detail, but draw only the subject described in the prompt.",
        f"Format: {spec['aspect']}, transparent background (keep the alpha channel).",
        *what,
        "",
        "Save the result(s) as PNG to:",
        *[f"- {t}" for t in targets],
        "Never overwrite an existing file (add -2, -3 instead) and do not change any other files.",
        "",
        "Then write keywords for the image you made.",
        KEYWORD_RULES,
        "",
        'End with JSON only: {"files": ["<absolute path>", ...], "note": "<one short sentence>", '
        '"prompt": "<the exact prompt you used>", "subject": "...", "motion": "...", "label": "...", '
        '"keywords": {"darija": [...], "ar": [...], "fr": [...], "en": [...]}}',
    ])
    return text, targets


def run_codex(codex: str, project: Path, request: str, refs: list[Path], workdir: Path,
              on_start=None, on_tick=None, schema: dict | None = None, sandbox: str = "workspace-write"):
    schema_file = workdir / "result-schema.json"
    schema_file.write_text(json.dumps(schema or RESULT_SCHEMA), encoding="utf-8")
    last = workdir / "last-message.json"
    log = workdir / "codex-events.jsonl"
    cmd = [codex, "exec", "-C", str(project), "--skip-git-repo-check",
           "-s", sandbox, "-c", 'model_reasoning_effort="low"',
           "--output-schema", str(schema_file), "-o", str(last), "--json"]
    for ref in refs:
        cmd += ["-i", str(ref)]
    started = time.time()
    with open(log, "wb") as logf:
        # The prompt goes in on stdin (no positional argument), so the
        # multi-value -i option can't swallow it.
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=logf,
                                stderr=subprocess.STDOUT, cwd=str(project),
                                creationflags=NO_WINDOW)
        if on_start:
            on_start(proc)
        try:
            proc.stdin.write(request.encode("utf-8"))
            proc.stdin.close()
        except OSError:
            pass
        while True:
            try:
                rc = proc.wait(timeout=10)
                break
            except subprocess.TimeoutExpired:
                elapsed = time.time() - started
                if on_tick:
                    on_tick(elapsed)
                if elapsed > TIMEOUT_S:
                    proc.kill()
                    proc.wait()
                    raise RuntimeError(f"GPT did not finish within {TIMEOUT_S}s. Log: {log}")
    return rc, last, log


def collect(targets: list[Path], last: Path, project: Path, since: float):
    """Images this run produced (what GPT reported, the requested paths, and as
    a last resort any new image in the project or in Codex's own folder), plus
    GPT's JSON answer."""
    data, candidates = {}, []
    try:
        data = json.loads(last.read_text(encoding="utf-8-sig"))
        candidates += [Path(p) for p in data.get("files", [])]
    except (OSError, ValueError, AttributeError):
        data = {}
    candidates += targets
    found: list[Path] = []
    for p in candidates:
        try:
            if (p.suffix.lower() in IMAGE_EXT and p.is_file()
                    and p.stat().st_mtime >= since - 2
                    and all(p.resolve() != q.resolve() for q in found)):
                found.append(p)
        except OSError:
            continue
    if not found:
        for root in (project / "generated", CODEX_HOME / "generated_images"):
            if root.is_dir():
                new = [p for p in root.rglob("*")
                       if p.suffix.lower() in IMAGE_EXT and p.is_file()
                       and p.stat().st_mtime >= since - 2]
                found += sorted(new, key=lambda p: p.stat().st_mtime)
            if found:
                break
    return found, data if isinstance(data, dict) else {}


def place(found: list[Path], name: str, look: str, dest: Path, finish: bool):
    (dest / "_raw").mkdir(parents=True, exist_ok=True)
    items = []
    for i, src in enumerate(found, 1):
        stem = free_stem(dest, name if len(found) == 1 else f"{name}-v{i}")
        raw = dest / "_raw" / f"{stem}{src.suffix.lower()}"
        shutil.copy2(src, raw)
        item = {"raw": str(raw), "gpt_file": str(src)}
        if finish:
            out = dest / f"{stem}.webp"
            # stdin=DEVNULL: see run_text (an inherited MCP stdin hangs the child).
            r = subprocess.run([sys.executable, str(FINISH_SCRIPT), str(raw), str(out),
                                "--canvas", LOOKS[look]["canvas"]],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", creationflags=NO_WINDOW,
                               stdin=subprocess.DEVNULL, timeout=600)
            item["asset"] = str(out) if out.exists() else None
            item["report"] = (r.stdout + r.stderr).strip()
        items.append(item)
    return items


def generate(name: str, look: str, prompt: str = "", dest: str | None = None, variants: int = 1,
             finish: bool | None = None, gpt_project: str | None = None, on_start=None, on_tick=None,
             subject: str = "", extra_keywords: dict | None = None, register: bool = True):
    if look not in LOOKS:
        raise ValueError("look must be 'glossy' or 'flat'")
    if not (prompt or "").strip() and not (subject or "").strip():
        raise ValueError("give a prompt or a subject")
    codex = find_codex()
    if not codex:
        raise RuntimeError("Codex CLI not found. Install or open the ChatGPT Codex desktop "
                           "app, or set CODEX_CLI_PATH to its codex.exe.")
    name = slug(name)
    variants = max(1, min(int(variants or 1), 4))
    project = gpt_project_dir(gpt_project)
    ensure_gpt_project(project)
    refs = [project / "style" / "refs" / f"{r}.png" for r in LOOKS[look]["refs"]]
    refs = [r for r in refs if r.is_file()]
    request, targets = build_request(name, look, prompt or "", variants, project, subject or "")
    workdir = project / ".gpt-assets" / f"{time.strftime('%Y%m%d-%H%M%S')}-{name}"
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "request.txt").write_text(request, encoding="utf-8")

    since = time.time()
    rc, last, log = run_codex(codex, project, request, refs, workdir, on_start, on_tick)
    found, data = collect(targets, last, project, since)
    if not found:
        raise RuntimeError(f"GPT finished (exit code {rc}) but saved no image.\n"
                           f"Last log lines:\n{tail(log)}\nFull log: {log}")
    # keep every library image inside the GPT project's generated/ folder
    kept = []
    for f in found:
        try:
            f.resolve().relative_to((project / "generated").resolve())
            kept.append(f)
        except ValueError:
            dst = free_generated(project, name, ".png")
            from PIL import Image
            Image.open(f).save(dst)
            kept.append(dst)
    res = {
        "name": name, "look": look, "files": [str(f) for f in kept], "items": [],
        "gpt_note": str(data.get("note", "")), "gpt_exit_code": rc, "seconds": round(time.time() - since),
        "log": str(log), "gpt_project": str(project), "prompt": data.get("prompt") or prompt,
        "keywords": data.get("keywords") or {},
    }
    if register:
        import asset_lib  # same folder; imported late (it imports this module)
        res["library_ids"] = asset_lib.register_generated(kept, name, look, prompt or "", data, extra_keywords)
        res["library"] = str(asset_lib.lib_path())
    if dest:
        res["items"] = place(kept, name, look, Path(dest), True if finish is None else finish)
        res["dest"] = str(dest)
    return res


def summarize(res: dict) -> str:
    lines = [f"GPT made {len(res['files'])} image(s) in {res['seconds']} s:"]
    lines += [f"- {f}" for f in res["files"]]
    if res.get("library_ids"):
        kw = res.get("keywords") or {}
        lines.append(f"Library: {', '.join(res['library_ids'])} -> {res.get('library')}")
        lines.append("Keywords: " + " | ".join(f"{k}: {len(kw.get(k, []))}" for k in ("darija", "ar", "fr", "en")))
        if kw.get("darija"):
            lines.append("  darija: " + "، ".join(kw["darija"][:12]))
    for it in res.get("items", []):
        lines.append(f"- asset: {it.get('asset') or '(not finished)'}")
        lines.append(f"  raw:   {it['raw']}")
        if it.get("report"):
            lines += ["  " + row for row in it["report"].splitlines()]
    if res.get("gpt_note"):
        lines.append(f"GPT note: {res['gpt_note']}")
    lines.append(f"Prompt: {res.get('prompt', '')}")
    lines.append(f"Request log: {res['log']}")
    return "\n".join(lines)


def status() -> dict:
    codex = find_codex()
    project = gpt_project_dir()
    info: dict = {"codex_cli": codex or "NOT FOUND"}
    if codex:
        info["codex_version"] = run_text([codex, "--version"])
        info["login"] = run_text([codex, "login", "status"])
        m = re.search(r"^image_generation\s+\S+\s+(\w+)",
                      run_text([codex, "features", "list"]), re.M)
        info["image_generation_enabled"] = m.group(1) if m else "unknown"
    cfg = CODEX_HOME / "config.toml"
    cfg_text = cfg.read_text(encoding="utf-8", errors="ignore").lower() if cfg.is_file() else ""
    info["gpt_project"] = str(project)
    info["gpt_project_exists"] = project.is_dir()
    info["gpt_project_trusted_in_codex"] = str(project).lower() in cfg_text
    import brand_guide
    info["brand"] = brand_guide.describe(project)
    own_guide = project / "style" / "style-identity-guide.md"
    info["style_guide"] = str(own_guide if (project / "brand.json").is_file() and own_guide.is_file()
                              else find_guide() or "NOT FOUND")
    lib = project / "library.json"
    if lib.is_file():
        try:
            assets = json.loads(lib.read_text(encoding="utf-8-sig")).get("assets", [])
            info["library"] = (f"{lib} ({len(assets)} assets, "
                               f"{sum(1 for a in assets if a.get('tagged_by'))} with keywords)")
        except ValueError:
            info["library"] = f"{lib} (unreadable)"
    else:
        info["library"] = f"{lib} (not created yet: run asset_lib.py sync)"
    return info


# ---------------------------------------------------------------- MCP server (optional)

TOOLS = [
    {
        "name": "generate_asset",
        "description": (
            "Generate one house-style illustration (the library folder's brand colours, orange by default) with "
            "the user's ChatGPT/Codex desktop app (built-in image_gen, "
            "signed in with their ChatGPT account, no API key). GPT also writes its keywords (Algerian Darija, "
            "Arabic, French, English) and the image is filed in the bluxstudio-skill asset library. Takes 1-4 minutes. "
            "Never overwrites: existing names get -2, -3."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "kebab-case file name without extension, "
                         "starting with the look, e.g. glossy-kidneys or flat-person-headache"},
                "look": {"type": "string", "enum": ["glossy", "flat"],
                         "description": "glossy = organs/objects, square; flat = people, heads, "
                         "symptoms, cross-sections, wide, facing right"},
                "prompt": {"type": "string", "description": "the full image prompt from the style guide template"},
                "subject": {"type": "string", "description": "instead of a prompt: a short subject; GPT writes "
                            "the prompt from the guide"},
                "dest_dir": {"type": "string", "description": "optional folder for a raw copy + finished WebP"},
                "variants": {"type": "integer", "minimum": 1, "maximum": 4, "default": 1},
            },
            "required": ["name", "look"],
        },
    },
    {
        "name": "gpt_status",
        "description": "Check the connection to the ChatGPT/Codex desktop app and the asset library.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


class Server:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.procs: dict = {}

    def send(self, msg: dict) -> None:
        data = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
        with self.lock:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()

    def result(self, mid, result: dict) -> None:
        self.send({"jsonrpc": "2.0", "id": mid, "result": result})

    def error(self, mid, code: int, message: str) -> None:
        self.send({"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}})

    def serve(self) -> None:
        try:
            for raw in sys.stdin.buffer:
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except ValueError:
                    self.error(None, -32700, "parse error")
                    continue
                for m in (msg if isinstance(msg, list) else [msg]):
                    if isinstance(m, dict):
                        self.dispatch(m)
        finally:
            for proc in list(self.procs.values()):
                try:
                    proc.kill()
                except OSError:
                    pass

    def dispatch(self, msg: dict) -> None:
        method, mid = msg.get("method"), msg.get("id")
        params = msg.get("params") or {}
        if method is None:
            return
        if mid is None:
            if method == "notifications/cancelled":
                proc = self.procs.get(params.get("requestId"))
                if proc:
                    proc.kill()
            return
        if method == "initialize":
            self.result(mid, {
                "protocolVersion": params.get("protocolVersion") or "2025-06-18",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": "Generates house-style illustrations (with keywords) through the user's "
                                "ChatGPT/Codex desktop app and files them in the bluxstudio-skill asset library.",
            })
        elif method == "ping":
            self.result(mid, {})
        elif method == "tools/list":
            self.result(mid, {"tools": TOOLS})
        elif method == "tools/call":
            threading.Thread(target=self.call_tool, args=(mid, params), daemon=True).start()
        elif method == "resources/list":
            self.result(mid, {"resources": []})
        elif method == "prompts/list":
            self.result(mid, {"prompts": []})
        else:
            self.error(mid, -32601, f"method not found: {method}")

    def call_tool(self, mid, params: dict) -> None:
        name, args = params.get("name"), params.get("arguments") or {}
        token = (params.get("_meta") or {}).get("progressToken")
        try:
            if name == "gpt_status":
                self.result(mid, {"content": [{"type": "text", "text": json.dumps(status(), indent=2)}]})
            elif name == "generate_asset":
                ticks = [0]

                def on_tick(elapsed: float) -> None:
                    if token is not None:
                        ticks[0] += 1
                        self.send({"jsonrpc": "2.0", "method": "notifications/progress",
                                   "params": {"progressToken": token, "progress": ticks[0],
                                              "message": f"GPT is generating ({int(elapsed)} s)"}})

                def on_start(proc) -> None:
                    self.procs[mid] = proc

                res = generate(args.get("name", ""), args.get("look", ""), args.get("prompt", ""),
                               args.get("dest_dir"), args.get("variants", 1), None,
                               on_start=on_start, on_tick=on_tick, subject=args.get("subject", ""))
                content = [{"type": "text", "text": summarize(res)}]
                for f in res["files"]:
                    try:
                        content.append({"type": "image", "data": preview_b64(f), "mimeType": "image/png"})
                    except Exception:  # noqa: BLE001 - a preview is optional
                        pass
                self.result(mid, {"content": content})
            else:
                self.error(mid, -32602, f"unknown tool: {name}")
        except Exception as exc:  # noqa: BLE001 - report as a tool error
            self.result(mid, {"content": [{"type": "text", "text": f"Error: {exc}"}], "isError": True})
        finally:
            self.procs.pop(mid, None)


# ---------------------------------------------------------------- CLI

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve", help="run as a local MCP server over stdio")
    sub.add_parser("status", help="check the connection to the Codex app")
    g = sub.add_parser("generate", help="make one asset (and file it in the library)")
    g.add_argument("--name", required=True, help="e.g. glossy-kidneys")
    g.add_argument("--look", required=True, choices=sorted(LOOKS))
    src = g.add_mutually_exclusive_group(required=True)
    src.add_argument("--prompt")
    src.add_argument("--prompt-file")
    src.add_argument("--subject", help="short subject; GPT writes the prompt from the guide")
    g.add_argument("--dest", help="also save a raw copy + finished WebP here (orange-health-assets behaviour)")
    g.add_argument("--variants", type=int, default=1)
    g.add_argument("--no-finish", action="store_true", help="with --dest: only save the raw image")
    g.add_argument("--no-library", action="store_true", help="do not file it in library.json")
    g.add_argument("--gpt-project", help="GPT project folder (default: Documents/ChatGPT/asstets tool ebox)")
    a = ap.parse_args()

    if a.cmd == "serve":
        Server().serve()
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    if a.cmd == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False))
        return
    prompt = a.prompt if a.prompt is not None else (
        Path(a.prompt_file).read_text(encoding="utf-8-sig") if a.prompt_file else "")

    def tick(elapsed: float) -> None:
        print(f"  ... GPT working ({int(elapsed)} s)", file=sys.stderr, flush=True)

    res = generate(a.name, a.look, prompt, a.dest, a.variants, not a.no_finish, a.gpt_project,
                   on_tick=tick, subject=a.subject or "", register=not a.no_library)
    print(summarize(res))


if __name__ == "__main__":
    main()
