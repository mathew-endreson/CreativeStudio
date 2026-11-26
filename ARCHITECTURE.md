# BluxTech Studio: architecture

```
┌────────────────────────── Windows desktop application ──────────────────────────┐
│  Tauri 2 shell (desktop/src-tauri, Rust)                                        │
│    starts the engine from <resources>, reads BLUXTECH_READY {port, token},      │
│    opens the window on http://127.0.0.1:<port>/boot/<token>, kills it on exit   │
│                                                                                 │
│  UI (desktop/src, React + TypeScript, served BY the engine)                     │
│    Login · Activate · Setup · Projects · Analysis · Possible ads ·              │
│    Build & results · Fresh edit (video timeline) · Library · Settings · Jobs    │
├──────────────────────────── local AI engine ────────────────────────────────────┤
│  engine/bluxtech_engine (Python 3.12, FastAPI, 127.0.0.1 only)                  │
│    security.py   boot token -> HttpOnly cookie; /api and /media need it          │
│    jobs.py       SQLite job queue: heavy (1) · claude (2, one per product) ·     │
│                  light (3); live logs over SSE; cancel kills the process tree    │
│    stages.py     the judgment steps = prompt template + output file + schema     │
│      analyze · amend · propose (from Camel Studio)                               │
│      graphics · fix · revise · fresh (stages_more.py)                            │
│    claude_runner  `cli`: claude.exe -p --output-format stream-json (own login)   │
│    agent_runner   `sdk`: Claude Agent SDK (bundled runtime) + API key (DPAPI)    │
│    products.py / fresh.py   products from a folder, build queue, results,        │
│                             fresh edits (one footage -> one ad)                  │
│    license.py · settings.py · environment.py                                     │
├──────────────────────────── media engine ───────────────────────────────────────┤
│  .claude/skills/bluxstudio-skill/scripts  (the skill: the only place with style rules) │
│    batch.py prepare/transcribe/scan/cut/build/check/render · new_project.py ·    │
│    transcribe.py (faster-whisper) · asset_lib.py (GPT library) · finalize.py    │
│  FFmpeg/FFprobe · HyperFrames (Node, Chrome) · Whisper · u2net matte             │
├──────────────────────────── local storage ──────────────────────────────────────┤
│  workspace (Documents\BluxTech Studio, or the project root in dev)              │
│    _hyperframes/<slug>_src  product batch: product.json, analysis.json,          │
│                             proposals.json, mixes.json, beats_<slug>_src.json    │
│    _hyperframes/<mix id>    one HyperFrames project per ad (+ .work reports)     │
│    _hyperframes/<slug>      a fresh edit (.work/fresh.json marker)               │
│    <product>/Ads            the finished MP4s                                    │
│  %LOCALAPPDATA%\com.bluxtech.studio\engine   engine.db (settings, license, device │
│    (dev: %LOCALAPPDATA%\BluxTech Studio)     id, sealed API key) · studio.db (jobs,│
│                                              logs) · thumbs                       │
└─────────────────────────────────────────────────────────────────────────────────┘
                 │ HTTPS                                   │ HTTPS
   ┌─────────────┴──────────────┐             ┌────────────┴─────────────┐
   │ Supabase                    │             │ Claude service            │
   │  Auth (email + password)    │             │  model inference only     │
   │  Postgres licenses,         │             │  (API key, or the owner's │
   │   license_devices (RLS)     │             │   Claude Code login)      │
   │  Edge Function `license`:   │             └───────────────────────────┘
   │   activate/check/deactivate │
   │  (RS256 license token)      │
   └─────────────────────────────┘
```

## Why the engine serves the UI

The UI is plain HTML served by the engine on a random localhost port, and the Tauri window simply opens that URL.
Every URL in the UI stays relative (`/api/...`, `/media/...`, SSE streams, `<video>` sources), the boot cookie rides
on all of them, and the same build runs in a browser for development. The Tauri capability `main` grants that
origin the Tauri API it needs (the native file pickers); everything else (open in Explorer, folder listing,
thumbnails) goes through the engine.

The look is DaVinci Resolve's graphite workspace built from liquid glass: a slim title bar with the page name in the
middle, a glass Libraries sidebar, and Resolve's page bar along the bottom (Projects, Fresh edit, Assets, Settings,
the active one lit amber, the one strong colour). All of it lives in three files: `desktop/src/index.css` (the
tokens, the `.glass*` classes, the `.backdrop` gradient floor that `index.html` draws behind the app, and the
reduced-transparency / reduced-motion fallbacks), `ui.tsx` (every primitive is a piece of glass) and `App.tsx`
(the shell). Page files only compose the primitives, so a restyle never touches them.

## A judgment step, end to end

1. The UI queues a job (`POST /api/products/{slug}/build`, `/fix`, `/revise`, `/api/fresh/{slug}/run` ...).
2. `claude_runner.run_stage` renders `prompts/<stage>.md` with the stage's context (paths, times, the mixes, the
   library, the output path and the JSON schema), picks the runner from Settings, and runs one session turn with only
   the tools the stage lists (`Read/Write/Edit/Glob/Grep`, `python`, `ffmpeg/ffprobe`, `npx hyperframes`), permission
   mode `acceptEdits`, no prompts (anything else is refused).
3. The stage's output file is validated against its pydantic schema plus the rules the app can check (times inside
   the source, beats inside body segments, the rendered file's length and loudness ...). Invalid: the same session is
   resumed with the problems, at most twice.
4. The app's mechanical follow-up runs as more jobs (`batch.py build`, `check`, `render`), each waiting for the one
   before. Usage (turns, tokens, cost) is recorded per project in `studio.json`.

## The two pipelines

**Remix (a product with finished ads):** New project → `prepare` / `transcribe` / `scan` → **analyze** (Claude:
hook end, body, CTA, offer groups, busy windows, liftable lines) → **propose** (Claude: pairings that read as one
argument) → the user ticks → `pictures` (the product's pictures in `<slug>_src/img`, indexed by `asset_lib.py
index` into `img/library.json`) → **graphics** (Claude: keywords for new pictures, then the animated assets in source
time; MISSING ideas are reported, GPT draws only on request) → `build` (joins, map_beats, place, remix_broll; no
speaker cutout since the assets sit in front of him) → `check` (lint + snapshots) → `render` (+ finalize −15 LUFS) →
Results, with **fix** (placement warnings) and **revise** (free-text feedback, same file name).

**Fresh edit (one clean footage):** `new_project.py` → transcript → cutout (for the particles and the route behind
him) → the user marks hook end / body / CTA on the timeline → **fresh** (Claude: SKILL.md steps 3–10: the ad's asset
folder indexed, keywords, `plan --lib`, `place --lib`, the render) → the ad in `Edited Ads`.

## Security model

- The engine binds 127.0.0.1 and needs the per-launch boot token (cookie) on `/api` and `/media`; the UI's static
  files are public on localhost only.
- The license is decided by the `license` Edge Function and cached locally with a 7-day offline grace; a shipped public key
  makes the engine verify the function's RS256 token, so a hand-written license file does not unlock it. All desktop
  licensing is ultimately client-side; the function is the authority for device counts and expiry.
- The Anthropic API key is sealed with DPAPI for the Windows user (never returned by the API, never logged).
- Claude runs with a fixed tool list and without permission prompts; the system prompt forbids deleting footage,
  projects, finished ads or the GPT library (the skill's guardrails).

## Installed layout (what `installer/build_runtime.ps1` stages)

```
<install dir>\resources\
  python\        embedded CPython 3.12 + pip + the engine's and the skill's packages (also runs the skill's scripts
                 and Claude's own `python ...` commands: it is first on PATH for every child process), with the
                 Visual C++ 2022 runtime DLLs beside python.exe (installer\vcredist: onnxruntime, ctranslate2 and
                 OpenCV import msvcp140*.dll, which a clean PC does not have)
  node\          portable Node.js 22            hyperframes\node_modules   HyperFrames 0.9.38
  ffmpeg\bin\    ffmpeg.exe, ffprobe.exe        models\                    u2net_human_seg.onnx (optional)
  engine\        bluxtech_engine + prompts      skill\bluxstudio-skill, skill\darijadz   the skills (copied into the workspace)
  assets\        the illustration library (library.json, generated\, style\), copied into the workspace as
                 <workspace>\assets on a PC without the GPT asset tool; the skill reads it through GPT_ASSETS_PROJECT
                 and CAMEL_GPT_LIBRARY, which the engine sets for every child process
  ui\            the built UI                   supabase.config.json, license_public_key.pem
```

About 1.6 GB staged, of which the Claude Code runtime bundled in the Agent SDK is 385 MB, the embedded Python with
its packages about 600 MB, FFmpeg 210 MB, the matte model 170 MB, Node 90 MB, HyperFrames 105 MB and the library 40 MB.

What the first run still fetches, through the Setup screen's job (all verified from an empty cache): the Whisper
model (1.5 GB, `faster_whisper.download_model`, about 2.5 min on a fast line), HyperFrames' Chrome
(`hyperframes browser ensure`, 270 MB) and the cutout runtime, which HyperFrames installs the first time it cuts
something out (210 MB; Setup cuts out a 64 px picture to trigger it). The matte model is copied from `models\`.
Without the Codex drawing tool the engine forces the drawing cap to 0 and the prompts skip the fill step.

The embeddable Python ships a `python312._pth`, which puts it in isolated mode: nothing from another Python on the
customer's PC leaks in, but a normal Python's first `sys.path` entry (the script's folder, or the current folder for
`python -m`) is dropped too. `installer/runtime/_bluxtech_paths.py`, loaded from a `.pth` in site-packages, puts that
entry back, because the engine starts with `python -m bluxtech_engine` and the skill's scripts import their siblings
(`batch.py` → `transcribe`, `map_beats`; `asset_lib` → `gpt_assets`). The `._pth` also lists `..\engine` outright.

PyInstaller was considered and not used: the skill's scripts, and the commands Claude runs, need a real `python`
on PATH with numpy/OpenCV/Whisper, so a freezer that bundles only the engine would leave them without an interpreter.
