# BluxTech Studio

A Windows desktop application around the `/bluxstudio-skill` ad pipeline: talking-head footage in, finished Algerian-Darija
video ads out (captions, hook / body / CTA transitions, the product's own pictures animated in front of the speaker, −15 LUFS renders), with accounts
and licensing in the cloud and every render on the user's own PC.

```
bluxtech-studio/
  engine/      Python 3.12: FastAPI + job queue + the Claude runners (the AI engine; drives the bluxstudio-skill)
  desktop/     React + TypeScript UI (Vite, Tailwind) and the Tauri 2 shell (src-tauri/)
  supabase/    Postgres schema + row-level security, the `license` Edge Function (activation, device limit, license token)
  installer/   scripts that stage the runtime (Python, Node, HyperFrames, FFmpeg) and build the NSIS installer
  dev.ps1      run it from source
```

`ARCHITECTURE.md` explains how the pieces fit. The editing rules themselves live in the skill
(`../.claude/skills/bluxstudio-skill`): the app never hard-codes a style rule, it runs the skill's scripts and sends Claude to
the skill for the judgment steps.

## Run it from source (dev)

Needs: Python 3.12 with the skill's packages (numpy, OpenCV, Pillow, faster-whisper), Node.js, FFmpeg on PATH, the
project root with `_hyperframes/` (HyperFrames installed) and `.claude/skills/bluxstudio-skill`.

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
| `cli` | the `claude.exe` installed on the PC and its own claude.ai login | the owner's machine (how `/bluxstudio-skill` runs by hand) |
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
2. Emails: the app asks for a code, not a link (a desktop app cannot receive a link's redirect), so the
   **Confirm signup** and **Reset password** templates must contain `{{ .Token }}` (`supabase/templates/*.html`,
   subjects in `supabase/config.toml`). The deploy script below applies them, **but a free-tier project on Supabase's
   default email provider refuses template changes**: then the sign-up email carries a link, which still confirms
   the account once opened (the user then signs in), while password reset from the app needs a code and does not work
   until a custom SMTP provider is set (**Project Settings → Authentication → SMTP**; also lifts the built-in sender's
   few-emails-an-hour limit). Set SMTP, run the script again, done.
3. From `bluxtech-studio/` (the CLI runs with `npx`, no global install; on a PowerShell with scripts disabled use
   `npx.cmd`), sign in once, then deploy everything with one script. It needs no database password: the schema goes
   through the Management API, the CLI does the secret and the function.
   ```
   npx supabase login
   .\installer\deploy_supabase.ps1 -ProjectRef <your-ref>
   ```
   (Manually: `npx supabase link --project-ref <ref>`, `npx supabase db push`, `npx supabase secrets set --env-file
   supabase/keys/secrets.env`, `npx supabase functions deploy license --no-verify-jwt`; the CLI asks `--yes` for each
   hosted change when it does not run in a terminal.) Optional secrets: `TRIAL_DAYS` (7), `TRIAL_DEVICES` (1),
   `LICENSE_TOKEN_DAYS` (14).
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

Flow in the app: sign up (code or link from the email) or sign in → `license` `activate` (registers the device within
the plan's limit, returns status, plan, expiry and the token) → the engine stores it and works offline for 7 days →
ads can be produced. Settings → **Free this device** releases the slot (`deactivate`). The engine verifies the token
with 5 minutes of clock leeway, so a PC whose clock runs a little behind is not locked out.

Verified on 2026-11-26 against a live project: trial on first activation, signed token accepted by the engine's
verifier, second device refused on a 1-device trial, re-check, deactivation, and row-level security (own license
readable, not writable, invisible to anonymous callers).

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

### Build it in GitHub Actions instead

`.github/workflows/installer.yml` builds the same installer on a GitHub-hosted Windows runner (Node, Python, Rust
and MSVC are preinstalled there; the runtime downloads are cached between runs). Two ways to start it:

- **Actions → installer → Run workflow**: the installer is kept as a workflow artifact for 90 days.
- **Push a tag** such as `v0.1.0`: the build runs and attaches the installer to a GitHub release of that tag.

The repo must hold what the build PC otherwise provides: `assets-library/` (the illustration library, copied from
the GPT asset tool's folder; refresh it when pictures are added), `installer/vcredist/` (the VC++ runtime DLLs),
`desktop/supabase.config.json` and `desktop/license_public_key.pem` (public values). A CI build has no matte model,
so the installed app's Setup screen fetches it with its first cutout warm-up (170 MB) instead of shipping it. A run
takes about 40 minutes, most of it the NSIS compression; the installer is about 530 MB.

First run on a customer PC: sign in, activate, then the **Setup** screen checks the machine and downloads what is
left (the Whisper model, about 1.6 GB; HyperFrames fetches its Chrome on the first render). The workspace is
`Documents\BluxTech Studio` (`_hyperframes/` projects, the skill copy); settings, license and the job log are in
`%LOCALAPPDATA%\com.bluxtech.studio\engine`, next to the WebView2 profile. The app itself installs per user into
`%LOCALAPPDATA%\BluxTech Studio` (in dev mode that same folder is the engine's data dir).

Run the installer from Explorer or a normal terminal. A process started from inside the Claude desktop app (an MSIX
package) gets that package's redirected AppData, so an install launched from there lands in
`AppData\Local\Packages\Claude_…\LocalCache\Local\` and is invisible to the shortcuts it creates.

## Updates

Installed copies update themselves through the Tauri updater: at startup (if the customer leaves the automatic
check on) and on **Settings → Updates → Check for updates**, the app reads the release channel's `latest.json`
(the newest GitHub release of this repository), shows the version and notes, and only downloads after the customer
says so. The download is verified against the public key built into the app (`plugins.updater.pubkey` in
`desktop/src-tauri/tauri.conf.json`), the engine is stopped, the installer runs passively and the app reopens.
A running task is never cut short: with tasks in flight the app offers to install when they finish. Projects,
pictures, settings, the API key and the license live outside the install folder and survive every update. A run
against a developer's engine (`BLUXTECH_ENGINE_URL`) never updates; `BLUXTECH_UPDATES=off` switches it off anywhere.

**Signing key (once).** `npm run tauri signer generate -- -w ~\.tauri\bluxtech-studio.key -p <password>` in
`desktop/` (or any password manager-worthy place outside the repository; `--ci` skips the prompts). Keep the key
and its password: without them no further update can be signed, and customers would be stuck on the last version.
The public key goes into `tauri.conf.json`; the private key is never committed (`~\.tauri\` is outside the repo,
and `installer\build.ps1` reads it from there for local builds).

**GitHub secrets (once).** Settings → Secrets and variables → Actions → New repository secret:

| secret | value |
|---|---|
| `TAURI_SIGNING_PRIVATE_KEY` | the full content of `~\.tauri\bluxtech-studio.key` |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | the password given at generation |

**Releasing a version.** `.\installer\bump_version.ps1 0.1.1` sets the version in `desktop/src-tauri/tauri.conf.json`,
`desktop/src-tauri/Cargo.toml` and `desktop/package.json` (all three must agree: the workflow refuses a tag that
does not match). Write the customer notes in `installer/RELEASE_NOTES.md`, commit, push to `main`, then tag and
push the tag:

```
git tag -a v0.1.1 -m "BluxTech Studio 0.1.1"
git push origin v0.1.1
```

The workflow builds the signed installer, `*.sig` and `latest.json` and attaches them to the GitHub release of that
tag. A tag with a hyphen (`v0.1.1-rc1`) makes a pre-release, which the release channel never serves: use it to
rehearse. Existing installations then find the new version at their next check.

**Rehearsing an update without publishing.** `installer\build.ps1 -LocalTest` builds with the overlay
`desktop/src-tauri/tauri.localtest.conf.json`, which lets an operator override endpoint use `http://127.0.0.1`
(signatures are still verified; production builds refuse plain http). Then `installer\make_update_manifest.ps1
-BaseUrl http://127.0.0.1:8777` writes a manifest for a local server, and the file
`%LOCALAPPDATA%\com.bluxtech.studio\updater.json` with `{"endpoint": "http://127.0.0.1:8777/latest.json"}` points
the installed copy at it (Settings shows "rehearsal channel"). Delete that file afterwards.

## Install on another PC (customers)

What the PC needs: Windows 10 or 11, 64-bit, about 6 GB free, internet for the first run, and 8 GB of RAM or more
(the cutout holds about 1.5 GB). Nothing else: the installer carries Python, Node, HyperFrames, FFmpeg, the Visual
C++ runtime, the skills, the illustration library and the license key.

1. Send `BluxTech Studio_0.1.0_x64-setup.exe` (about 530 MB). It is not code-signed yet, so Windows SmartScreen
   shows "Windows protected your PC" the first time: **More info → Run anyway**. (A code-signing certificate removes
   that screen; see below.) The install is per user, no administrator rights, under `%LOCALAPPDATA%\BluxTech Studio`,
   with a Desktop and a Start Menu shortcut. If the Edge WebView2 runtime is missing the installer downloads it.
2. First start: sign up (the email carries a link, open it, then sign in) or sign in, then **Activate**. A new account
   gets a trial; sales grant the real license (Licensing above).
3. The **Set up this PC** screen then lists what is missing and **Run setup** fetches it once: the Whisper model
   (1.6 GB), the Chrome that HyperFrames renders with (270 MB) and the cutout runtime (210 MB). The matte model and
   the illustration library ship with the installer and are laid into the workspace automatically.
4. The editing steps run on Claude through an Anthropic API key: the Setup screen asks for it (or Settings → Claude
   later). The key is sealed to the Windows user with DPAPI. Without a key the app opens but no edit can start.
5. Work lands in `Documents\BluxTech Studio` (projects, cutouts, renders; the finished ads in each project's own Ads
   folder); settings, license and the job log in `%LOCALAPPDATA%\com.bluxtech.studio\engine`. Uninstalling from
   Apps & Features leaves both in place.

Known limits on a customer PC: no ChatGPT / Codex drawing tool, so the ads use the shipped library as it is (new
pictures are not drawn; the drawing cap is forced to 0); the illustration library is the copy made at build time
(`installer/build_runtime.ps1` takes it from the build PC's GPT asset folder), so rebuild the installer after adding
pictures. Code signing: a certificate (an OV/EV certificate, or Azure Trusted Signing) and `bundle.windows.certificateThumbprint`
or `signCommand` in `tauri.conf.json` make the installer and the exe signed, which is what removes the SmartScreen
screen for customers.

## What is not done yet

- The installer has been built and installed on the development PC, and each first-run piece a clean PC needs was
  exercised separately on 2026-11-26: the Visual C++ runtime beside the embedded Python (static import scan of all
  310 native modules, then real imports), the Whisper download into an empty cache (1.5 GB), HyperFrames' Chrome
  download and its cutout-runtime install into an empty cache, and the illustration-library fallback without the
  GPT tool. What is still missing is one run of the installer on a truly clean Windows machine (Windows Sandbox is
  not enabled on the build PC); the first customer install is that test.
- A fresh edit ran end to end from the app on 2026-11-26 (Footage 03: 31 s, 14 captions, 12 beats, −15.2 LUFS, 13
  minutes, about $3.50 of Claude usage with the `cli` runner). The remix stages (`graphics`, `fix`, `revise`) are
  wired the same way but have not been run from the app yet.
- Google / social sign-in (needs a deep-link flow); email + password only.
- Auto-update; a web account page for customers to manage their devices (the `license` function's `deactivate` action
  and the `license_devices` table exist).
- The fresh-edit and remix Claude stages (`fresh`, `graphics`, `fix`, `revise`) are wired and validated but their
  prompts have not yet been exercised end to end from the app; the analyze / propose stages come from Camel Studio
  where they ran on real batches.
