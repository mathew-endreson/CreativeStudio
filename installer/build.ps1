# One command to a Windows installer:  .\installer\build.ps1
# Needs on the build machine: Node.js, Rust (rustup, MSVC toolchain) and the Visual Studio C++ Build Tools,
# python on PATH (for make_icon.py), internet for the runtime downloads. The customer's PC needs none of these.
param(
  [switch]$SkipRuntime,
  [switch]$LocalTest,        # rehearsal build: lets an operator override endpoint use http://127.0.0.1 (never for customers)
  [string]$Tag = ""          # the GitHub release tag the update manifest should point at (default v<version>)
)
$ErrorActionPreference = "Stop"
$studio = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$desktop = Join-Path $studio "desktop"

# ---- updater signing. The build makes a signed update artifact (bundle.createUpdaterArtifacts), so it needs the
# private key: on CI from the TAURI_SIGNING_PRIVATE_KEY / _PASSWORD secrets, on the build PC from the key pair that
# `tauri signer generate` wrote outside the repository (~\.tauri\bluxtech-studio.key + .password). Never commit it.
if (-not $env:TAURI_SIGNING_PRIVATE_KEY) {
  $keyFile = Join-Path $env:USERPROFILE ".tauri\bluxtech-studio.key"
  if (Test-Path -LiteralPath $keyFile) {
    $env:TAURI_SIGNING_PRIVATE_KEY = $keyFile
    if (Test-Path -LiteralPath "$keyFile.password") { $env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD = (Get-Content -LiteralPath "$keyFile.password" -Raw).Trim() }
    Write-Output "updater signing: the key at $keyFile"
  } else {
    throw "No updater signing key: set TAURI_SIGNING_PRIVATE_KEY (and _PASSWORD), or run `npm run tauri signer generate -- -w ~\.tauri\bluxtech-studio.key` in desktop/ (see README, Updates)."
  }
}

foreach ($tool in @("npm", "cargo", "rustc")) {
  if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
    throw "$tool is not on PATH. Install Node.js and Rust (winget install Rustlang.Rustup; then the VS C++ Build Tools: winget install Microsoft.VisualStudio.2022.BuildTools --override '--wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended')."
  }
}

Push-Location -LiteralPath $desktop
try {
  if (-not (Test-Path "node_modules")) { npm ci --no-audit --no-fund; if ($LASTEXITCODE -ne 0) { throw "npm ci failed" } }
  if (-not (Test-Path "src-tauri\icons\icon.ico")) {
    python (Join-Path $studio "installer\make_icon.py")
    npm run tauri -- icon app-icon.png
    if ($LASTEXITCODE -ne 0) { throw "tauri icon failed" }
  }
  npm run build
  if ($LASTEXITCODE -ne 0) { throw "UI build failed" }
} finally { Pop-Location }

if (-not $SkipRuntime) { & (Join-Path $studio "installer\build_runtime.ps1") }
else { & (Join-Path $studio "installer\build_runtime.ps1") -SkipDownloads }

Push-Location -LiteralPath $desktop
try {
  if ($LocalTest) { npm run tauri -- build --config src-tauri/tauri.localtest.conf.json } else { npm run tauri -- build }
  if ($LASTEXITCODE -ne 0) { throw "tauri build failed" }
} finally { Pop-Location }

$out = Get-ChildItem -LiteralPath (Join-Path $desktop "src-tauri\target\release\bundle\nsis") -Filter "*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not (Test-Path -LiteralPath "$($out.FullName).sig")) { throw "the installer was not signed: no $($out.Name).sig" }
$version = (Get-Content -LiteralPath (Join-Path $desktop "src-tauri\tauri.conf.json") -Raw | ConvertFrom-Json).version
if (-not $Tag) { $Tag = "v$version" }
& (Join-Path $studio "installer\make_update_manifest.ps1") -Tag $Tag
Write-Output ""
Write-Output "Installer: $($out.FullName)  ($([math]::Round($out.Length / 1MB)) MB), signed; update manifest latest.json beside it (release $Tag)"
