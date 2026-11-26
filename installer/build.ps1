# One command to a Windows installer:  .\installer\build.ps1
# Needs on the build machine: Node.js, Rust (rustup, MSVC toolchain) and the Visual Studio C++ Build Tools,
# python on PATH (for make_icon.py), internet for the runtime downloads. The customer's PC needs none of these.
param(
  [switch]$SkipRuntime,
  [string]$LibraryDir = ""   # the illustration library to ship (default: the GPT asset tool's folder, else assets-library/)
)
$ErrorActionPreference = "Stop"
$studio = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$desktop = Join-Path $studio "desktop"

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

$rt = @{}
if ($LibraryDir) { $rt.LibraryDir = $LibraryDir }
if (-not $SkipRuntime) { & (Join-Path $studio "installer\build_runtime.ps1") @rt }
else { & (Join-Path $studio "installer\build_runtime.ps1") -SkipDownloads @rt }

Push-Location -LiteralPath $desktop
try {
  npm run tauri -- build
  if ($LASTEXITCODE -ne 0) { throw "tauri build failed" }
} finally { Pop-Location }

$out = Get-ChildItem -LiteralPath (Join-Path $desktop "src-tauri\target\release\bundle\nsis") -Filter "*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Write-Output ""
Write-Output "Installer: $($out.FullName)  ($([math]::Round($out.Length / 1MB)) MB)"
