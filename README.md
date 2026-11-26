# BluxTech Studio

A Windows desktop application around the `/camel-gpt` ad pipeline: talking-head footage in, finished Algerian-Darija
video ads out (captions, hook / body / CTA transitions, graphics behind the speaker, −15 LUFS renders), with accounts
and licensing in the cloud and every render on the user's own PC.

```
bluxtech-studio/
  engine/      Python 3.12: FastAPI + job queue + the Claude runners (the AI engine; drives the camel-gpt skill)
  desktop/     React + TypeScript UI (Vite, Tailwind) and the Tauri 2 shell (src-tauri/)
  supabase/    Postgres schema + row-level security, the `license` Edge Function (activation, device limit, license token)
  installer/   scripts that stage the runtime (Python, Node, HyperFrames, FFmpeg) and build the NSIS installer
  dev.ps1      run it from source
```

`ARCHITECTURE.md` explains how the pieces fit. The editing rules themselves live in the skill
(`../.claude/skills/camel-gpt`): the app never hard-codes a style rule, it runs the skill's scripts and sends Claude to
the skill for the judgment steps.

## Run it from source (dev)

Needs: Python 3.12 with the skill's packages (numpy, OpenCV, Pillow, faster-whisper), Node.js, FFmpeg on PATH, the
project root with `_hyperframes/` (HyperFrames installed) and `.claude/skills/camel-gpt`.

```powershell
cd bluxtech-studio
.\dev.ps1
```

`dev.ps1` makes `engine/.venv`, builds the UI once, starts the engine on http://127.0.0.1:8766 and opens the browser on
the engine's boot link. Without `desktop/supabase.config.json` the engine runs with licensing off (dev mode) and the
Claude runner defaults to your own Claude Code login (`claude.exe`).

For UI work: `python engine\run.py --no-auth` in one terminal, `npm run dev` in `desktop/` in another
(http://localhost:5173 proxies `/api`, `/media` and `/boot` to the engine).

Checks: `engine\.venv\Scripts\python engine\tests\smoke_test.py` boots an engine on a free port and probes every read
endpoint; `npm run build` in `desktop/` type-checks the UI; `deno check supabase/functions/license/index.ts` the Edge Function.

## The transcript

```
audio/video ─▶ ffmpeg ─▶ Whisper (listens, local) ─▶ Claude Code + darijadz skill (fixes Darija) ─▶ darija_lint (checks) ─▶ .txt / .srt / .json
```

Whisper (large-v3-turbo, on this PC) writes the word-timed draft; the `darija` stage (`engine/bluxtech_engine/darija.py`,
`engine/prompts/darija.md`) has Claude correct it with the `darijadz` skill (`.claude/skills/darijadz`, MIT) without
paraphrasing, then the app runs `darija_lint` and writes, beside each transcript: `<k>_transcript.txt`, `.srt`, `.json`
(segments with Whisper's text, the correction, unsure words, notes and lint), `<k>_words.whisper.json` (Whisper's own
words, kept) and a corrected `<k>_words.json` re-timed onto Whisper's word times, so the captions, the analysis and the
asset matcher read real Darija. A project's analysis waits for the correction; a fresh edit runs it beside the cutout.
"Redo a step → Correct the Darija again" (or "Correct again" in a transcript) redoes it from Whisper's copy.

## The two Claude runners (Settings)

| runner | what makes the Claude calls | for |
|---|---|---|
| `cli` | the `claude.exe` installed on the PC and its own claude.ai login | the owner's machine (how `/camel-gpt` runs by hand) |
| `sdk` | the Claude Agent SDK, whose pip package bundles the Claude Code runtime, with the user's Anthropic API key (sealed with Windows DPAPI) | the shipped product |

Anthropic does not allow third-party products to offer claude.ai logins, so an installed BluxTech Studio runs on
the `sdk` runner: either the customer enters their own API key in Settings, or your licensing backend hands one out
(the engine reads `ANTHROPIC_API_KEY` from the environment as a fallback). Each run has a budget and a turn limit
(Settings) and the usage per project is shown in the UI.

## Licensing (Supabase)

Supabase Auth (email + password) identifies the user; Postgres holds one `licenses` row per user and one
`license_devices` row per activated PC (`supabase/migrations/`); the `license` Edge Function (`supabase/functions/license`)
activates, re-checks and frees devices and signs the RS256 token the engine verifies offline.

1. Create a Supabase project (supabase.com/dashboard). In **Authentication → Sign In / Providers → Email**, keep Email
   enabled and **Confirm email** on.
2. **Authentication → Emails → Templates**: the app asks for a code, not a link, so put `{{ .Token }}` in
   **Confirm signup** and **Reset password** (for example `Your BluxTech Studio code: <b>{{ .Token }}</b>`). For real
   customers set up custom SMTP (**Authentication → Emails → SMTP Settings**): the built-in sender only allows a few
   emails an hour.
3. From `bluxtech-studio/` (the CLI runs with `npx`, no global install):
   ```
   npx supabase login
   npx supabase link --project-ref <your-ref>
   npx supabase db push                                   # tables, row-level security, SQL functions
   npx supabase secrets set --env-file supabase/keys/secrets.env
   npx supabase functions deploy license --no-verify-jwt
   ```
   Optional secrets: `TRIAL_DAYS` (7), `TRIAL_DEVICES` (1), `LICENSE_TOKEN_DAYS` (14).
4. Signing keys: `supabase/keys/license_private.pem` (never commit it, keep a backup) and its public half
   `desktop/license_public_key.pem`; `supabase/keys/secrets.env` holds the private key in base64 for step 3. To make a
   new pair: `openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out supabase/keys/license_private.pem`,
   `openssl rsa -in supabase/keys/license_private.pem -pubout -out desktop/license_public_key.pem`, then rewrite
   `secrets.env` as `LICENSE_SIGNING_KEY=<base64 of the pem on one line>`. Without a public key the engine trusts the payload (dev).
5. App config: copy `desktop/supabase.config.example.json` to `desktop/supabase.config.json` with the Project URL and the
   publishable key (**Project Settings → API Keys**). Both are public; never ship the secret key. The installer ships it
   as `<resources>/supabase.config.json`.
6. Grant licenses, in **SQL Editor**: `select grant_license('user@example.com', p_plan => 'pro', p_days => 365, p_devices => 2);`
   (`p_status => 'suspended'` suspends), or from `supabase/`: `node scripts/grant.mjs user@example.com --plan pro --days 365 --devices 2`
   with `SUPABASE_URL` and `SUPABASE_SECRET_KEY` set. The customer signs up in the app first; a new account gets a
   trial on its first activation.

Flow in the app: sign up (code from the email) or sign in → `license` `activate` (registers the device within the plan's
limit, returns status, plan, expiry and the token) → the engine stores it and works offline for 7 days → ads can be
produced. Settings → **Free this device** releases the slot (`deactivate`).

## Build the installer

On the build machine only: Node.js, Rust (`winget install Rustlang.Rustup`), the Visual Studio C++ Build Tools
(`winget install Microsoft.VisualStudio.2022.BuildTools --override "--wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"`),
and internet for the runtime downloads. The customer's PC needs none of these (WebView2 is bootstrapped by the installer).

```powershell
.\installer\build.ps1
```

It builds the UI, draws the icon set (replace `desktop/app-icon.png` with the real logo), stages
`desktop/src-tauri/resources/` (`installer/build_runtime.ps1`: embedded Python 3.12 with the engine's and the skill's
packages, portable Node 22 with HyperFrames 0.9.38, FFmpeg, the engine, both skills, the UI, the Supabase config, the
matte model; about 1.6 GB, see ARCHITECTURE.md) and runs `tauri build`. The result is
`desktop/src-tauri/target/release/bundle/nsis/BluxTech Studio_0.1.0_x64-setup.exe`. Downloads are cached in
`installer/downloads/`; a second run only refreshes the engine, the skills and the UI, then rebuilds the shell
(under 3 minutes) and the installer. To check the staged runtime without installing anything, start the engine
from it the way the shell does: `resources\python\python.exe -m bluxtech_engine --resources <resources> --workspace <tmp> --data <tmp> --port 8799 --no-auth`
from `resources\engine`, then open `http://127.0.0.1:8799/`.

First run on a customer PC: sign in, activate, then the **Setup** screen checks the machine and downloads what is
left (the Whisper model, about 1.6 GB; HyperFrames fetches its Chrome on the first render). The workspace is
`Documents\BluxTech Studio` (`_hyperframes/` projects, the skill copy); settings, license and the job log are in
`%LOCALAPPDATA%\com.bluxtech.studio\engine`, next to the WebView2 profile. The app itself installs per user into
`%LOCALAPPDATA%\BluxTech Studio` (in dev mode that same folder is the engine's data dir).

Run the installer from Explorer or a normal terminal. A process started from inside the Claude desktop app (an MSIX
package) gets that package's redirected AppData, so an install launched from there lands in
`AppData\Local\Packages\Claude_…\LocalCache\Local\` and is invisible to the shortcuts it creates.

## What is not done yet

- The installer (`BluxTech Studio_0.1.0_x64-setup.exe`, about 530 MB) has been built and installed on the
  development PC (silent install, shortcuts, uninstall entry, app launched from the installed copy: engine spawned,
  window opened, engine stopped with the window). It has not yet been tried on a clean PC without Node, Python or a
  Whisper cache, where the Setup screen has to download the Whisper model.
- Google / social sign-in (needs a deep-link flow); email + password only.
- Auto-update; a web account page for customers to manage their devices (the `license` function's `deactivate` action
  and the `license_devices` table exist).
- The fresh-edit and remix Claude stages (`fresh`, `graphics`, `fix`, `revise`) are wired and validated but their
  prompts have not yet been exercised end to end from the app; the analyze / propose stages come from Camel Studio
  where they ran on real batches.
